"""Two unrelated casts share the same Screenplay -> W2 -> FND01 bridge."""
from __future__ import annotations

import copy

import pytest

from drama_factory.pipeline.screenplay import Screenplay
from drama_factory.pipeline.screenplay_visual_bridge import plan_screenplay_visual_references
from drama_factory.pipeline.visual_production_plan import VisualPlanError
from test_g4_visual_production_plan import _data


def _inputs(actor_count: int, shot_count: int):
    manifest, _, gallery = _data(count=shot_count)
    if actor_count == 1:
        # No business name in the production bridge; a single-mascot production.
        manifest["shots"] = [
            {**entry, "characters": entry["characters"][:1],
             "character_ids": entry["character_ids"][:1]}
            for entry in manifest["shots"]
        ]
        gallery = [item for item in gallery if item["asset_id"] != "actor_b"]
    cards = [
        dict(
            shot_id=entry["shot_id"], duration_seconds=5,
            action="虚构故事占位；不声称模型生成", camera="中景",
            character_ids=entry["character_ids"], scene_id=entry["scene_id"],
            continuity_start=f"{i} start", continuity_end=f"{i} end",
        )
        for i, entry in enumerate(manifest["shots"])
    ]
    screenplay = Screenplay.model_validate(dict(
        series_id=manifest["series_id"], story_bible_id="bible_example",
        episode_number=1, episode_title="unrelated story fixture",
        target_duration_seconds=shot_count * 5, shots=cards,
    ))
    views = {
        shot["shot_id"]: {
            name: "front" if idx % 2 == 0 else "side"
            for name in shot["character_ids"]
        } for idx, shot in enumerate(manifest["shots"])
    }
    props = {sid: [] for sid in manifest["selected_shot_ids"]}
    return screenplay, manifest, gallery, views, props


@pytest.mark.parametrize("cast,shots", [(1,12),(2,6)])
def test_single_and_dual_actor_storyboards_use_same_existing_reference_plan(cast,shots):
    screenplay, manifest, gallery, views, props = _inputs(cast,shots)
    plan = plan_screenplay_visual_references(
        screenplay, manifest, gallery, actor_views=views, prop_pins=props,
    )
    assert len(plan["shots"]) == shots
    assert plan["model_submission_allowed"] is False
    assert plan["provider_reference_applied"] is False
    assert plan["production_assets_verified"] is False
    assert plan["new_paid_model_calls"] == 0
    assert plan["shots"][0]["depends_on"] == []
    assert plan["shots"][1]["depends_on"] == ["s01"]
    assert plan["shots"][0]["candidate_image_count"] == cast + 1
    assert plan_screenplay_visual_references(
        screenplay, manifest, gallery, actor_views=views, prop_pins=props,
    ) == plan


def test_foreign_actor_and_wrong_version_do_not_cross_bridge():
    screenplay, manifest, gallery, views, props = _inputs(1,12)
    bad = copy.deepcopy(manifest)
    bad["shots"][0]["character_ids"] = ["other_person"]
    with pytest.raises(VisualPlanError, match="cast"):
        plan_screenplay_visual_references(
            screenplay,bad,gallery,actor_views=views,prop_pins=props,
        )
    bad = copy.deepcopy(manifest)
    bad["shots"][0]["characters"][0]["version"] = 9
    with pytest.raises(VisualPlanError, match="unavailable"):
        plan_screenplay_visual_references(
            screenplay,bad,gallery,actor_views=views,prop_pins=props,
        )


def test_missing_back_reference_is_not_implicitly_approved():
    screenplay, manifest, gallery, views, props = _inputs(1,12)
    gallery = [g for g in gallery
               if not (g["asset_id"] == "actor_a" and g["view"] == "back")]
    with pytest.raises(VisualPlanError, match="unavailable"):
        plan_screenplay_visual_references(
            screenplay,manifest,gallery,actor_views=views,prop_pins=props,
        )


def test_unapproved_gallery_cannot_create_real_media_grant():
    screenplay, manifest, gallery, views, props = _inputs(2,6)
    gallery[0]["operator_approved_for_model"] = False
    with pytest.raises(VisualPlanError, match="unapproved"):
        plan_screenplay_visual_references(
            screenplay,manifest,gallery,actor_views=views,prop_pins=props,
        )
