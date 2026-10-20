"""Local owner inventory only: do not claim binary or model authorization."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "assets/citydiscount/v1"

def test_unuploaded_ten_image_inventory_is_complete_but_not_approved():
    m = json.loads((FOLDER / "character_views_inventory.json").read_text("utf-8"))
    assert m["schema"] == "g4-local-operator-image-inventory.v1"
    assert m["binary_bytes_committed"] is False
    assert m["images_content_verified_by_ci"] is False
    assert m["model_submission_allowed"] is False
    assert m["operator_approved_for_model"] is False
    assert m["rights_independently_verified"] is False
    assert len(m["images"]) == 10
    assert len({i["filename"] for i in m["images"]}) == 10
    assert len({i["source_sha256"] for i in m["images"]}) == 10
    assert {i["role"] for i in m["images"]} == {
        "front","side","back","three_quarter",
        "happy","wink","sparkle","jump","thumbsup","coin",
    }
    for image in m["images"]:
        assert re.fullmatch(r"[a-f0-9]{64}", image["source_sha256"])
        assert image["format"] == "PNG" and image["mode"] == "RGBA"
        assert 1 <= image["width"] <= 4096 and 1 <= image["height"] <= 4096
        assert image["filename"].startswith("mascot_")
        assert image["filename"].endswith("_derived.png")
        assert image["verification"] == "owner_local_pillow_and_sha_report_only"
