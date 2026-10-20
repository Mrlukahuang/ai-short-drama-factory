"""G4/R4.4: validate ACTUAL owner-uploaded image bytes, not just a manifest.

These are public engineering fixtures, never an operator-signed rights grant.
No model/network calls or modification to existing pictures.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path

from PIL import Image

from drama_factory.pipeline.local_asset_references import _canonical_png
from drama_factory.pipeline.visual_media_admission import verify_png

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "assets" / "citydiscount" / "v1"
VIEWS = FOLDER / "character_views"
ROLES = {
    "front", "side", "back", "three_quarter",
    "happy", "wink", "sparkle", "jump", "thumbsup", "coin",
}


def _inventory() -> dict:
    return json.loads((FOLDER / "character_views_inventory.json").read_text("utf-8"))


def test_committed_ten_image_inventory_is_complete_but_not_model_approved():
    m = _inventory()
    assert m["schema"] == "g4-local-operator-image-inventory.v1"
    assert m["binary_bytes_committed"] is True
    assert m["images_content_verified_by_ci"] is True  # Enforced by test below.
    assert m["model_submission_allowed"] is False
    assert m["operator_approved_for_model"] is False
    assert m["rights_independently_verified"] is False
    assert len(m["images"]) == 10
    assert len({i["filename"] for i in m["images"]}) == 10
    assert len({i["source_sha256"] for i in m["images"]}) == 10
    assert {i["role"] for i in m["images"]} == ROLES
    assert set(m["roles"]) == ROLES
    for image in m["images"]:
        assert re.fullmatch(r"[a-f0-9]{64}", image["source_sha256"])
        assert image["format"] == "PNG" and image["mode"] == "RGBA"
        assert 1 <= image["width"] <= 4096 and 1 <= image["height"] <= 4096
        assert image["filename"] == f"mascot_{image['role']}_derived.png"
        assert image["verification"] == "repo_checked_out_png_bytes_sha256_and_pillow_ci"


def test_ten_real_png_bytes_and_normalized_fnd02_media_gate(tmp_path):
    manifest = _inventory()
    records = manifest["images"]
    assert {p.name for p in VIEWS.glob("*.png")} == {i["filename"] for i in records}
    for item in records:
        path = VIEWS / item["filename"]
        assert path.is_file() and not path.is_symlink()
        source = path.read_bytes()
        assert 100 <= len(source) <= 8 * 1024 * 1024
        assert hashlib.sha256(source).hexdigest() == item["source_sha256"]
        with Image.open(io.BytesIO(source)) as img:
            assert img.format == item["format"]
            assert img.mode == item["mode"]
            assert img.size == (item["width"], item["height"])
            assert getattr(img, "n_frames", 1) == 1
            img.verify()
        # Existing generic intake handles PNG alpha correctly; FND-02 only accepts
        # sanitized RGB PNG. The normalized bytes are a *derived* digest, not a
        # replacement for the source_sha256 anchored above.
        normalized, width, height, kind = _canonical_png(source)
        assert kind == "PNG"
        assert max(width, height) <= 1024
        with Image.open(io.BytesIO(normalized)) as image:
            assert image.mode == "RGB" and image.format == "PNG"
            assert image.size == (width, height)
            image.verify()
        normalized_path = tmp_path / (item["filename"] + ".normalized.png")
        normalized_path.write_bytes(normalized)
        assert verify_png(normalized_path, hashlib.sha256(normalized).hexdigest()) == normalized
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["source_sha256"]
