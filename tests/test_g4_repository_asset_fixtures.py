"""G4/R4.4 repository fixtures: verify ORIGINAL checked-out bytes, not names.

This checks the user's selected V1 images independently of creative/model
provider code and works with any correctly scoped repo asset fixture manifest.
No image is uploaded, submitted to a provider or put in generated output.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "assets" / "citydiscount" / "v1"


def _verify_source(data: bytes, *, expected_blob: str, expected_size: int,
                   expected_sha256: str | None = None) -> str:
    if len(data) != expected_size:
        raise ValueError("Checked-out fixture size mismatch")
    blob_sha = hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()
    if blob_sha != expected_blob:
        raise ValueError("Checked-out fixture differs from uploaded Git blob")
    actual_sha = hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None and actual_sha != expected_sha256:
        raise ValueError("Source SHA256 mismatch")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or image.width <= 0 or image.height <= 0:
            raise ValueError("Original source is not a supported PNG")
        if image.width * image.height > 12_000_000:
            raise ValueError("Oversized source image")
        image.verify()
    return actual_sha


def test_owner_uploaded_github_assets_are_byte_exact_and_new_mascot():
    manifest = json.loads((DIR / "asset_manifest.json").read_text("utf-8"))
    assert manifest["schema"] == "g4-repository-reference-fixtures.v1"
    assert manifest["scope"] == "local_engineering_fixture_only"
    assert manifest["model_submission_allowed"] is False
    assert manifest["publish_approved"] is False
    assert manifest["media_rights_independently_verified"] is False
    assert len(manifest["assets"]) == 2
    checked = {}
    for row in manifest["assets"]:
        name = row["relative_file"]
        assert name in ("mascot_character_sheet_v1.png", "citydiscount_logo_v1.png")
        path = DIR / name
        assert not path.is_symlink()
        checked[row["asset_id"]] = _verify_source(
            path.read_bytes(), expected_blob=row["git_blob_sha1"],
            expected_size=row["size_bytes"],
            expected_sha256=row.get("source_sha256"),
        )
    assert checked["citydiscount-mascot-v1"] == (
        "9706eb126398d703e3750c4ac0ca0d296e618ae548ca05d5b1f9a3d99633bf92"
    )
    assert checked["citydiscount-logo-v1"] == (
        "19a6202331db9853d384ddabd30fbdf738f139fd8721638eed54fde193011651"
    )


def test_generic_file_byte_gate_rejects_corruption():
    for source in (b"wrong", b"\x89PNG\r\n\x1a\nnot a PNG"):
        with pytest.raises(ValueError):
            _verify_source(source, expected_blob="0" * 40, expected_size=len(source))


def test_generic_file_byte_gate_rejects_wrong_expected_sha(tmp_path):
    img = Image.new("RGB", (16, 16), (12, 45, 67))
    mem = io.BytesIO()
    img.save(mem, format="PNG")
    data = mem.getvalue()
    blob = hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()
    assert _verify_source(data, expected_blob=blob,
                          expected_size=len(data)) == hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError, match="SHA256"):
        _verify_source(data, expected_blob=blob,
                       expected_size=len(data), expected_sha256="0"*64)
