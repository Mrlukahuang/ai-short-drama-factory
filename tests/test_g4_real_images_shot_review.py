"""Real Owner PNG bytes -> per-shot W2 review candidates; NO model approvals.

Same code is exercised with a second, unrelated two-actor Series using
synthetic image bytes (not copies of the Owner's reference images).
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from drama_factory.pipeline.local_reference_views import (
    build_unapproved_shot_image_review,
)
from drama_factory.pipeline.visual_production_plan import VisualPlanError
from test_g4_visual_production_plan import _data

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "citydiscount" / "v1"
VIEW_FOLDER = ASSETS / "character_views"
ACTOR_VIEWS = ("front", "side", "back", "three_quarter")


def _w2(count, cast):
    manifest, _, _ = _data(count=count)
    manifest["series_id"] = f"proj_{cast:014x}"
    if cast == 1:
        for shot in manifest["shots"]:
            shot["characters"] = shot["characters"][:1]
            shot["character_ids"] = shot["character_ids"][:1]
    for shot in manifest["shots"]:
        for actor in shot["characters"]:
            actor["specification_sha256"] = hashlib.sha256(
                (manifest["series_id"] + actor["asset_id"]).encode()
            ).hexdigest()
        shot["scene_asset"]["specification_sha256"] = hashlib.sha256(
            (manifest["series_id"] + shot["scene_id"]).encode()
        ).hexdigest()
    return manifest


def _inputs(count, cast, tmp_path):
    manifest = _w2(count, cast)
    actor_ids = manifest["shots"][0]["character_ids"]
    inventories = {}
    folders = {}
    if cast == 1:
        inventories[actor_ids[0]] = json.loads(
            (ASSETS / "character_views_inventory.json").read_text("utf-8")
        )
        folders[actor_ids[0]] = VIEW_FOLDER
    else:
        for actor_num, actor in enumerate(actor_ids):
            folder = tmp_path / actor
            folder.mkdir()
            images = []
            for view_num, role in enumerate(ACTOR_VIEWS[:3]):
                out = io.BytesIO()
                Image.new(
                    "RGBA", (48, 48),
                    (actor_num * 80 + view_num * 25, 20 + view_num * 55, 160, 255),
                ).save(out, "PNG")
                name = f"{actor}_{role}.png"
                (folder / name).write_bytes(out.getvalue())
                images.append({
                    "role": role, "filename": name,
                    "source_sha256": hashlib.sha256(out.getvalue()).hexdigest(),
                })
            inventories[actor] = {
                "schema": "g4-local-operator-image-inventory.v1",
                "images": images,
                "model_submission_allowed": False,
                "operator_approved_for_model": False,
                "rights_independently_verified": False,
            }
            folders[actor] = folder
    choices = {
        sid: {aid: ACTOR_VIEWS[index % (4 if cast == 1 else 3)]
              for aid in actor_ids}
        for index, sid in enumerate(manifest["selected_shot_ids"])
    }
    return manifest, inventories, folders, choices


def _review(inputs):
    return build_unapproved_shot_image_review(*inputs)


def test_actual_ten_image_inventory_pins_per_shot_and_keeps_rights_closed(tmp_path):
    inputs = _inputs(12, 1, tmp_path)
    result = _review(inputs)
    assert result == _review(inputs)
    assert result["shot_count"] == 12
    assert result["actual_png_bytes_checked"] is True
    assert result["angle_semantics_human_verified"] is False
    assert result["model_submission_allowed"] is False
    assert result["provider_reference_applied"] is False
    assert result["new_paid_model_calls"] == 0
    rows = result["shots"]
    assert [rows[i]["actor_image_candidates"][0]["view"] for i in range(4)] == list(ACTOR_VIEWS)
    lookup = {x["role"]: x for x in inputs[1]["actor_a"]["images"]}
    for row in rows:
        assert len(row["actor_image_candidates"]) == 1
        assert len(row["blockers"]) == 3
        media = row["actor_image_candidates"][0]
        assert media["source_sha256"] == lookup[media["view"]]["source_sha256"]
        assert media["png_sha256"] != media["source_sha256"]
        assert media["asset_id"] == "actor_a"
        assert media["asset_version"] == 1
        assert media["specification_sha256"] == inputs[0]["shots"][0]["characters"][0]["specification_sha256"]
        assert media["rights_independently_verified"] is False
        assert media["operator_approved_for_model"] is False
    assert not any("happy" in str(s) or "jump" in str(s) for s in rows)
    assert str(VIEW_FOLDER) not in json.dumps(result)
    assert "data" not in result
    assert result["review_sha256"]


def test_second_unrelated_series_two_actors_uses_same_byte_pipeline(tmp_path):
    inputs = _inputs(6, 2, tmp_path)
    result = _review(inputs)
    assert result["shot_count"] == 6
    assert result["series_id"] != _review(_inputs(12, 1, tmp_path))["series_id"]
    assert all(len(row["actor_image_candidates"]) == 2 for row in result["shots"])
    assert len({m["source_sha256"] for row in result["shots"]
                for m in row["actor_image_candidates"]}) == 6
    assert result["model_submission_allowed"] is False


def test_missing_version_and_foreign_cast_cannot_rebind_real_png(tmp_path):
    inputs = _inputs(12, 1, tmp_path)
    manifest = copy.deepcopy(inputs[0])
    manifest["shots"][0]["characters"][0]["specification_sha256"] = None
    with pytest.raises(VisualPlanError, match="Unpinned"):
        _review((manifest, *inputs[1:]))
    manifest = copy.deepcopy(inputs[0])
    manifest["shots"][0]["characters"][0]["version"] = 9
    with pytest.raises(VisualPlanError, match="version"):
        _review((manifest, *inputs[1:]))
    foreign = dict(inputs[1])
    foreign["foreign_actor"] = foreign.pop("actor_a")
    with pytest.raises(VisualPlanError, match="foreign"):
        _review((inputs[0], foreign, *inputs[2:]))


def test_false_rights_approval_and_source_byte_swap_block_review(tmp_path):
    inputs = _inputs(12, 1, tmp_path)
    forged = copy.deepcopy(inputs[1])
    forged["actor_a"]["operator_approved_for_model"] = True
    with pytest.raises(VisualPlanError, match="approval"):
        _review((inputs[0], forged, *inputs[2:]))

    # Never change checked-in Owner assets; tamper with independent local copies.
    folder = tmp_path / "tamper"
    folder.mkdir()
    for image in inputs[1]["actor_a"]["images"]:
        if image["role"] in ACTOR_VIEWS:
            (folder / image["filename"]).write_bytes(
                (VIEW_FOLDER / image["filename"]).read_bytes()
            )
    changed = next(x for x in inputs[1]["actor_a"]["images"] if x["role"] == "front")
    path = folder / changed["filename"]
    path.write_bytes(path.read_bytes() + b"modified")
    with pytest.raises(VisualPlanError, match="SHA"):
        _review((inputs[0], inputs[1], {"actor_a": folder}, inputs[3]))


def test_camera_angle_alias_and_missing_required_view_are_not_accepted(tmp_path):
    inputs = _inputs(12, 1, tmp_path)
    selections = copy.deepcopy(inputs[3])
    selections["s01"]["actor_a"] = "happy"
    with pytest.raises(VisualPlanError, match="view"):
        _review((*inputs[:3], selections))
    invent = copy.deepcopy(inputs[1])
    invent["actor_a"]["images"] = [
        item for item in invent["actor_a"]["images"] if item["role"] != "back"
    ]
    with pytest.raises(VisualPlanError, match="front/side/back"):
        _review((inputs[0], invent, *inputs[2:]))
