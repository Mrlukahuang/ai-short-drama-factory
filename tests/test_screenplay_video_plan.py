"""Offline request preparation only; no credentials or generation."""
from copy import deepcopy
import json
import socket

import pytest

from drama_factory.pipeline.screenplay import Screenplay
from drama_factory.pipeline.screenplay_video_plan import build_screenplay_video_plan
from drama_factory.pipeline.text import ScriptContext
from test_writer_execution_prep import prepared, screenplay


def plan(raw=None, **kwargs):
    context = ScriptContext.model_validate_json(prepared().context_json)
    return build_screenplay_video_plan(Screenplay.model_validate(raw or screenplay()), context,
        style_prompt="Handmade needle-felted miniature diorama",
        actor_descriptions=context.story_bible_json["characters"], **kwargs)


def test_preserves_dialogue_actions_timing_and_continuity_without_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")
    monkeypatch.setattr(socket, "socket", forbidden)
    result = plan()
    assert result["paid_api_calls"] == 0 and result["paid_execution_authorized"] is False
    assert result["production_assets_verified"] is False
    assert result["total_estimated_usd"] is None and result["total_budget_verified"] is False
    for src, dst in zip(screenplay()["shots"], result["shots"]):
        data = json.loads(dst["prompt"].split('\n', 1)[1])
        assert data["shot"] == src
        assert set(data["actors"]) == set(src["character_ids"])
        assert dst["request_preview"]["input"] == dst["prompt"]
        assert dst["exact_duration_enforced"] is False


def test_contiguous_three_shot_pilot_retains_ids_and_does_not_approve_budget():
    result = plan(shot_ids=["0", "1", "2"])
    assert result["full_episode"] is False and result["selected_target_seconds"] == 30
    assert result["output_only_10s_per_shot_estimated_usd"] == "1.0137750"
    assert result["total_budget_verified"] is False
    assert result["paid_execution_authorized"] is False


@pytest.mark.parametrize("ids", [[], ["0", "0"], ["2", "1"], ["0", "2"], ["missing"]])
def test_invalid_selection_rejected(ids):
    with pytest.raises(ValueError):
        plan(shot_ids=ids)


def test_twelve_shots_are_costed_as_twelve_not_old_six():
    raw = screenplay()
    raw["shots"] = [deepcopy(raw["shots"][0]) for _ in range(12)]
    for i, shot in enumerate(raw["shots"]):
        shot["shot_id"] = str(i)
        shot["duration_seconds"] = 5
    result = plan(raw)
    assert len(result["shots"]) == 12
    assert result["selected_target_seconds"] == 60
    assert result["output_only_target_estimated_usd"] == "2.0275500"
    assert result["output_only_10s_per_shot_estimated_usd"] == "4.0551000"
    assert result["requires_above_usd2_on_output_estimate_alone"] is True


@pytest.mark.parametrize("fault", ["series", "actor", "scene", "duration"])
def test_scope_and_supported_duration_rejected(fault):
    raw = screenplay()
    if fault == "series": raw["series_id"] = "foreign"
    if fault == "actor":
        raw["shots"][0]["character_ids"] = ["foreign", "a-jie"]
    if fault == "scene": raw["shots"][0]["scene_id"] = "foreign"
    if fault == "duration":
        raw["shots"][0]["duration_seconds"] = 11
        raw["target_duration_seconds"] = 61
    with pytest.raises(ValueError):
        plan(raw)



def test_missing_appearance_anchor_rejected():
    context = ScriptContext.model_validate_json(prepared().context_json)
    with pytest.raises(ValueError, match="appearance anchor"):
        build_screenplay_video_plan(Screenplay.model_validate(screenplay()), context,
            style_prompt="felt", actor_descriptions={})
