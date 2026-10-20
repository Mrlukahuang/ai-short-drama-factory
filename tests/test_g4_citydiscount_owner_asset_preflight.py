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
    candidate, assets = _docs()
    p1 = tmp_path / "mascot_character_sheet.png"
    p2 = tmp_path / "citydiscount_logo.png"
    p1.write_bytes(b"synthetic test mascot png placeholder bytes; no real likeness" * 4)
    p2.write_bytes(b"synthetic test logo png placeholder bytes; no real logo" * 5)
    newsha = {
        "citydiscount-mascot-v1": hashlib.sha256(p1.read_bytes()).hexdigest(),
        "citydiscount-logo-v1": hashlib.sha256(p2.read_bytes()).hexdigest(),
    }
    candidate["style"]["mascot_source_sha256"] = newsha["citydiscount-mascot-v1"]
    candidate["style"]["logo_source_sha256"] = newsha["citydiscount-logo-v1"]
    for shot in candidate["shots"]:
        shot["character_reference_sha256"] = newsha["citydiscount-mascot-v1"]
        shot["brand_logo_reference_sha256"] = newsha["citydiscount-logo-v1"]
    for asset in assets["assets"]:
        asset["sha256"] = newsha[asset["asset_id"]]
        asset["size_bytes"] = (p1 if asset["kind"]=="actor" else p2).stat().st_size
    return candidate, assets


def test_first_pilot_uses_owner_felt_assets_not_old_flat_style():
    candidate, assets = _docs()
    assert candidate["style"]["id"] == "citydiscount_needle_felt_mascot_v1"
    assert candidate["style"]["owner_confirmed_felt_style"] is True
    assert candidate["style"]["mascot_source_sha256"] == assets["assets"][0]["sha256"]
    assert candidate["style"]["logo_source_sha256"] == assets["assets"][1]["sha256"]
    assert assets["github_original_binary_upload_status"] == "NOT_VERIFIED_NOT_COMMITTED"
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
    (tmp_path/"mascot_character_sheet.png").write_bytes(b"tampered original")
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
