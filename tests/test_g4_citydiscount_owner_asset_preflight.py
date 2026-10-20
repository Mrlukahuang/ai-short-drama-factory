"""Repo-side CityDiscount felt mascot and Logo version/approval preflight."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/citydiscount_pilot_preflight.py"
spec = importlib.util.spec_from_file_location("citydiscount_pilot_preflight", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _docs():
    candidate = json.loads((ROOT/"config/pilots/citydiscount_first_promo_v1.json").read_text("utf-8"))
    assets = json.loads((ROOT/"config/pilots/citydiscount_owner_asset_manifest_v1.json").read_text("utf-8"))
    return candidate, assets


def _fake_local_images(tmp_path):
    from PIL import Image
    candidate, assets = _docs()
    p1 = tmp_path / "mascot_character_sheet_v1.png"
    p2 = tmp_path / "citydiscount_logo_v1.png"
    Image.new("RGB", (32, 32), (246, 228, 203)).save(p1, "PNG")
    Image.new("RGB", (24, 24), (32, 88, 41)).save(p2, "PNG")
    raw = {
        "citydiscount-mascot-v1": p1.read_bytes(),
        "citydiscount-logo-v1": p2.read_bytes(),
    }
    shas = {key: hashlib.sha256(data).hexdigest() for key,data in raw.items()}
    git_sha = {key: hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest() for key,data in raw.items()}
    candidate["style"]["mascot_source_sha256"] = None
    candidate["style"]["mascot_git_blob_sha1"] = git_sha["citydiscount-mascot-v1"]
    candidate["style"]["logo_source_sha256"] = shas["citydiscount-logo-v1"]
    for shot in candidate["shots"]:
        shot["character_reference_sha256"] = None
        shot["character_reference_git_blob_sha1"] = git_sha["citydiscount-mascot-v1"]
        shot["brand_logo_reference_sha256"] = shas["citydiscount-logo-v1"]
    for asset in assets["assets"]:
        aid = asset["asset_id"]
        asset["sha256"] = None if aid == "citydiscount-mascot-v1" else shas[aid]
        asset["github_blob_sha1"] = git_sha[aid]
        asset["size_bytes"] = len(raw[aid])
        asset["pixel_width"] = 32 if aid == "citydiscount-mascot-v1" else 24
        asset["pixel_height"] = 32 if aid == "citydiscount-mascot-v1" else 24
    return candidate, assets


def test_first_pilot_uses_owner_felt_assets_not_old_flat_style():
    candidate, assets = _docs()
    assert candidate["style"]["id"] == "citydiscount_needle_felt_mascot_v1"
    assert candidate["style"]["owner_confirmed_felt_style"] is True
    assert candidate["style"]["mascot_source_sha256"] == assets["assets"][0]["sha256"]
    assert candidate["style"]["logo_source_sha256"] == assets["assets"][1]["sha256"]
    assert assets["github_original_binary_upload_status"] == "UPLOADED_TO_PR_BRANCH_SHA256_PENDING_LOCAL_READBACK"
    assert assets["assets"][0]["github_blob_sha1"] == "a5665b80a8484d5124fb874576ff40372f5a7c06"
    assert assets["assets"][0]["sha256"] is None
    assert assets["remote_model_use_granted"] is False
    assert all(s["character_id"]=="citydiscount-mascot-v1" for s in candidate["shots"])


def test_refuse_when_original_binaries_not_locally_present(tmp_path):
    c, a = _docs()
    with pytest.raises(mod.CityDiscountPilotGateError, match="unavailable"):
        mod.preflight(c, a, tmp_path)


def test_local_rehearsal_preflight_writes_all_eleven_truthful_stages(tmp_path):
    c, a = _fake_local_images(tmp_path)
    out = tmp_path / "run"
    report = mod.run(c, a, tmp_path, out)
    assert len([p for p in out.iterdir() if p.is_dir()]) == 11
    assert report["shot_count"] == 12
    assert len(report["assets"]) == 2
    assert report["model_submission_allowed"] is False
    assert report["real_model_generated_shots"] == 0
    assert report["video_provider_receipt"] is None
    assert report["publish_approved"] is False
    assert json.loads((out / "09_render" / "receipt.json").read_text())["payload"]["video"] == "not_run"
    assert json.loads((out / "10_qa" / "receipt.json").read_text())["payload"]["real_ai_content_qa"] == "not_run"
    with pytest.raises(mod.CityDiscountPilotGateError, match="new"):
        mod.run(c, a, tmp_path, out)


def test_tampered_original_image_and_replaced_logo_hash_fail(tmp_path):
    c, a = _fake_local_images(tmp_path)
    (tmp_path/"mascot_character_sheet_v1.png").write_bytes(b"tampered original")
    with pytest.raises(mod.CityDiscountPilotGateError, match="mutated"):
        mod.preflight(c, a, tmp_path)
    c, a = _fake_local_images(tmp_path)
    c["shots"][8]["brand_logo_reference_sha256"] = "0"*64
    with pytest.raises(mod.CityDiscountPilotGateError, match="pinned"):
        mod.preflight(c, a, tmp_path)


def test_false_remote_approval_rejected(tmp_path):
    c, a = _fake_local_images(tmp_path)
    a["remote_model_use_granted"] = True
    with pytest.raises(mod.CityDiscountPilotGateError):
        mod.preflight(c, a, tmp_path)

def test_git_uploaded_new_canonical_mascot_is_verified_not_old(tmp_path):
    """Runs only against the *checked-out PR branch's* binary upload."""
    candidate, assets = _docs()
    fixture_dir = ROOT / "assets" / "citydiscount" / "v1"
    report = mod.preflight(candidate, assets, fixture_dir)
    by_id = {entry["asset_id"]: entry for entry in report["assets"]}
    assert by_id["citydiscount-mascot-v1"]["git_blob_sha1"] == (
        "a5665b80a8484d5124fb874576ff40372f5a7c06"
    )
    assert by_id["citydiscount-mascot-v1"]["sha256"] != (
        "79e653ff555185df85df52b642fa3a606f92b688a2b83b6cb15d8dc4521602cb"
    )
    assert by_id["citydiscount-logo-v1"]["sha256"] == (
        "19a6202331db9853d384ddabd30fbdf738f139fd8721638eed54fde193011651"
    )
    assert report["real_model_generated_shots"] == 0
