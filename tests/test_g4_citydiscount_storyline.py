"""G4 CityDiscount first-film storyline is a usable 12-shot production proposal.

No model, no narration synthesis, no image transmission. Creative approval and
brand/governance/media rights remain explicitly separate decisions.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from drama_factory.pipeline.promo_motion_graphics import (
    PromoPlanError, build_offline_citydiscount_promo_plan,
)

SOURCE = (Path(__file__).resolve().parents[1] /
          "config/pilots/citydiscount_first_promo_v1.json")
INVENTORY = (Path(__file__).resolve().parents[1] /
             "assets/citydiscount/v1/character_views_inventory.json")


def _draft():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def test_real_story_reaches_existing_offline_plan_with_drama_arc():
    source = _draft()
    result = build_offline_citydiscount_promo_plan(source)
    assert result["shot_count"] == 12
    assert result["duration_seconds"] == 60
    assert result["story_title_zh"] == "小羊差点买错了"
    assert result["script_reviewed_by_owner"] is False
    assert [s["storybeat"] for s in result["shots"] if s["storybeat"] in {
        "hook", "reversal", "resolution", "cta"}] == [
            "hook", "reversal", "resolution", "cta"]
    assert result["shots"][3]["storybeat"] == "reversal"
    assert result["shots"][3]["shot_id"] == "s04"
    assert all(s["video_background_prompt"] and s["audio_narration_expected"]
               and s["postproduction_overlay_text"] for s in result["shots"])
    assert all(s["camera_direction_zh"] and s["continuity_instruction_zh"]
               for s in result["shots"])
    assert all(s["media_pending_approval"] is True for s in result["shots"])
    assert all(len(s["audio_narration_expected"]) <= 30
               for s in result["shots"])


def test_story_views_and_actions_only_reference_real_inventory_roles():
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    roles = {image["role"] for image in inventory["images"]}
    out = build_offline_citydiscount_promo_plan(_draft())
    assert len(roles) == 10
    assert {x["mascot_camera_view"] for x in out["shots"]} == {
        "front", "side", "back", "three_quarter"}
    assert all(x["mascot_camera_view"] in roles
               and x["mascot_expression_or_action_hint"] in roles
               for x in out["shots"])
    assert out["model_submission_allowed"] is False
    assert out["provider_reference_applied"] is False
    assert out["video_generated"] is False
    assert out["model_calls"] == 0
    assert out["actual_fee_usd"] is None
    assert out["publish_approved"] is False


@pytest.mark.parametrize("change", ["delete_reversal", "fake_view",
                                    "missing_camera", "forced_approval"])
def test_story_cannot_silently_lose_continuity_or_approve_media(change):
    j = copy.deepcopy(_draft())
    if change == "delete_reversal":
        j["shots"][3]["storybeat"] = "value_demonstration"
    elif change == "fake_view":
        j["shots"][4]["mascot_camera_view"] = "fake_angle"
    elif change == "missing_camera":
        j["shots"][6]["camera_direction_zh"] = ""
    elif change == "forced_approval":
        j["storyline"]["script_reviewed_by_owner"] = True
    with pytest.raises(PromoPlanError):
        build_offline_citydiscount_promo_plan(j)


def test_creative_rewrite_invalidates_previous_approved_plan_hash():
    original = _draft()
    a = build_offline_citydiscount_promo_plan(original)
    changed = copy.deepcopy(original)
    changed["shots"][2]["voiceover_zh"] += "啊"
    b = build_offline_citydiscount_promo_plan(changed)
    assert a["source_sha256"] != b["source_sha256"]
    assert a["offline_plan_sha256"] != b["offline_plan_sha256"]
    assert a["model_submission_allowed"] is False
