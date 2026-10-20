"""G4: real SQLite W2 pins -> actual local image byte review; zero model use.

Read-only verification of REAL existing DB rows, with synthetic local PNG
data to avoid attributing Owner's mascot to a different fictional cast.
"""
from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image

from drama_factory.db import Database
from drama_factory.pipeline.local_reference_views import (
    build_unapproved_shot_image_review,
)
from drama_factory.pipeline.visual_production_plan import VisualPlanError
from test_w2_shot_asset_binding import sample, bound


def _local_views(sample, tmp_path):
    manifest = bound(sample)["manifest"]  # Calls the REAL existing W2/DB builder.
    actors = sorted({a for shot in manifest["shots"]
                     for a in shot["character_ids"]})
    inventories, folders = {}, {}
    for actor_index, actor in enumerate(actors):
        folder = tmp_path / ("images_" + actor)
        folder.mkdir()
        rows = []
        for view_index, role in enumerate(("front", "side", "back")):
            buffer = io.BytesIO()
            Image.new(
                "RGBA", (56, 56),
                (actor_index * 100 + view_index * 30, 10, 170, 255),
            ).save(buffer, format="PNG")
            file = folder / ("img_" + role + ".png")
            file.write_bytes(buffer.getvalue())
            rows.append({
                "role": role, "filename": file.name,
                "source_sha256": hashlib.sha256(buffer.getvalue()).hexdigest(),
            })
        inventories[actor] = {
            "schema": "g4-local-operator-image-inventory.v1",
            "images": rows,
            "rights_independently_verified": False,
            "operator_approved_for_model": False,
            "model_submission_allowed": False,
        }
        folders[actor] = folder
    selections = {}
    for i, shot in enumerate(manifest["shots"]):
        selections[shot["shot_id"]] = {
            aid: ("front", "side", "back")[i % 3]
            for aid in shot["character_ids"]
        }
    return manifest, inventories, folders, selections


def _verify(sample, inputs):
    return build_unapproved_shot_image_review(*inputs, db=sample[0])


def test_real_w2_sqlite_rows_and_synthetic_pngs_make_scoped_review(sample, tmp_path):
    inputs = _local_views(sample, tmp_path)
    doc = _verify(sample, inputs)
    assert doc == _verify(sample, inputs)
    assert doc["shot_count"] == 6
    assert doc["series_asset_sqlite_pins_verified"] is True
    assert doc["actual_png_bytes_checked"] is True
    assert doc["angle_semantics_human_verified"] is False
    assert doc["model_submission_allowed"] is False
    assert doc["provider_reference_applied"] is False
    assert doc["new_paid_model_calls"] == 0
    assert doc["w2_manifest_sha256"]
    assert all(len(s["actor_image_candidates"]) == 2 for s in doc["shots"])
    assert all(m["asset_version"] == 3 and len(m["specification_sha256"]) == 64
               for s in doc["shots"] for m in s["actor_image_candidates"])
    assert all(len(s["blockers"]) == 3 for s in doc["shots"])


def test_without_db_remains_unverified_instead_of_claiming_sqlite(sample, tmp_path):
    doc = build_unapproved_shot_image_review(*_local_views(sample, tmp_path))
    assert doc["series_asset_sqlite_pins_verified"] is False
    assert doc["model_submission_allowed"] is False
    assert doc["review_sha256"]


@pytest.mark.parametrize("corruption", ["actor_version", "actor_spec", "actor_kind",
                                         "scene_version", "scene_spec"])
def test_changed_real_sqlite_rows_block_stale_w2_before_image_read(
    sample, tmp_path, corruption,
):
    inputs = _local_views(sample, tmp_path)
    db = sample[0]
    row_id = "cafe" if corruption.startswith("scene") else "a-jie"
    if corruption.endswith("version"):
        db.exec("UPDATE series_assets SET version=version+1 WHERE id=?", (row_id,))
    elif corruption.endswith("kind"):
        db.exec("UPDATE series_assets SET kind='prop' WHERE id=?", (row_id,))
    else:
        db.exec("UPDATE series_assets SET specification_json='{}' WHERE id=?", (row_id,))
    # If any image read happens first, this missing image will fail with a
    # different error. Stale DB identity MUST fail early and stay private.
    (inputs[2]["a-jie"] / "img_front.png").unlink()
    with pytest.raises(VisualPlanError, match="SeriesAsset SQLite"):
        _verify(sample, inputs)


def test_foreign_sqlite_has_no_authority_to_validate_another_series(sample, tmp_path):
    inputs = _local_views(sample, tmp_path)
    unrelated_db = Database(tmp_path / "foreign.sqlite")
    with pytest.raises(VisualPlanError, match="SeriesAsset SQLite"):
        build_unapproved_shot_image_review(*inputs, db=unrelated_db)


def test_wrong_declared_w2_asset_version_also_rejected(sample, tmp_path):
    inputs = _local_views(sample, tmp_path)
    inputs[0]["shots"][0]["characters"][0]["version"] += 1
    with pytest.raises(VisualPlanError, match="Actor changes version|SeriesAsset SQLite"):
        _verify(sample, inputs)
