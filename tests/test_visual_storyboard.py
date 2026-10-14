"""Visual shot editor pure transformations, preserving review and provenance gates."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from drama_factory.pipeline.local_story_workflow import (
    LocalStoryWizardError, apply_visual_storyboard,
    canonical_screenplay_digest, make_storyboard_template,
    validated_draft_still_matches,
)
from test_screenplay import setup_series


def _draft(client, *, seconds=5):
    sid, bible, actor, scene = setup_series(client, "Visual UI")
    draft = make_storyboard_template(
        sid, bible, [actor], scene,
        shot_count=2, seconds_per_shot=seconds,
    )
    return sid, actor, scene, draft


def _fields(draft):
    return [{
        "shot_id": shot["shot_id"],
        "duration_seconds": shot["duration_seconds"],
        "action": shot["action"], "camera": shot["camera"],
        "character_ids": list(shot["character_ids"]), "scene_id": shot["scene_id"],
        "continuity_start": shot["continuity_start"],
        "continuity_end": shot["continuity_end"],
        "dialogue": deepcopy(shot["dialogue"]),
    } for shot in draft["shots"]]


def _apply(draft, shots, *, actor, scene):
    return apply_visual_storyboard(
        draft, episode_number=1, episode_title="原创虚构试片",
        hook="三秒钩子", ending_cliffhanger="结尾悬念",
        edited_shots=shots, allowed_actor_ids=[actor],
        allowed_scene_ids=[scene],
    )


def test_visual_edits_keep_ids_update_totals_and_use_existing_server_validation(client):
    sid, actor, scene, draft = _draft(client)
    shots = _fields(draft)
    shots[0]["duration_seconds"] = 4
    shots[1]["duration_seconds"] = 6
    shots[0]["action"] = "主角轻声敲门"
    shots[0]["camera"] = "中景跟拍"
    shots[0]["continuity_end"] = "右手握住把手"
    shots[1]["continuity_start"] = "右手握住把手"
    shots[0]["dialogue"] = [
        {"speaker_actor_id": actor, "text": "有人吗？",
         "start_second": 0, "end_second": 2},
        {"speaker_actor_id": actor, "text": "我进来了",
         "start_second": 2, "end_second": 4},
    ]
    result = _apply(draft, shots, actor=actor, scene=scene)
    assert result["target_duration_seconds"] == 10
    assert [x["shot_id"] for x in result["shots"]] == ["S001", "S002"]
    assert result["shots"][0]["dialogue"] == shots[0]["dialogue"]
    assert result["shots"][1]["continuity_start"] == "右手握住把手"
    assert result["shots"][0]["scene_id"] == scene
    assert result["shots"][0]["character_ids"] == [actor]
    api = client.post(f"/api/v1/series/{sid}/screenplays/validate", json=result)
    assert api.status_code == 200, api.text
    assert api.json()["review_required"] is True
    assert api.json()["paid_api_calls"] == 0
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []


def test_visual_changes_invalidate_previous_human_review_fingerprint(client):
    sid, actor, scene, draft = _draft(client)
    validated = client.post(f"/api/v1/series/{sid}/screenplays/validate", json=draft)
    assert validated.status_code == 200
    previous = {
        "series_id": sid, "fingerprint": canonical_screenplay_digest(draft),
        "valid": True, "review_required": True, "paid_api_calls": 0,
    }
    edits = _fields(draft)
    edits[0]["action"] = "修改后的镜头必须重新审核"
    updated = _apply(draft, edits, actor=actor, scene=scene)
    assert not validated_draft_still_matches(updated, previous, sid)
    assert validated_draft_still_matches(draft, previous, sid)


@pytest.mark.parametrize("mutate", [
    lambda shots: shots.pop(),
    lambda shots: shots.reverse(),
    lambda shots: shots[0].update(shot_id="S999"),
    lambda shots: shots[0].update(character_ids=["asset_" + "0"*14]),
    lambda shots: shots[0].update(character_ids=["asset_" + "0"*14, "asset_" + "0"*14]),
    lambda shots: shots[0].update(scene_id="asset_" + "0"*14),
    lambda shots: shots[0].update(duration_seconds=31),
    lambda shots: shots[0].update(action=""),
    lambda shots: shots[0].update(continuity_start=""),
    lambda shots: shots[0].update(dialogue=[{
        "speaker_actor_id": None, "text": "不能自动补说话人",
        "start_second": None, "end_second": None,
    }]),
    lambda shots: shots[0].update(dialogue=[{
        "speaker_actor_id": shots[0]["character_ids"][0], "text": "",
        "start_second": None, "end_second": None,
    }]),
    lambda shots: shots[0].update(dialogue=[{
        "speaker_actor_id": shots[0]["character_ids"][0], "text": "时槽填写一半",
        "start_second": 1, "end_second": None,
    }]),
    lambda shots: shots[0].update(dialogue=[{
        "speaker_actor_id": shots[0]["character_ids"][0], "text": "越界",
        "start_second": 4, "end_second": 6,
    }]),
    lambda shots: shots[0].update(dialogue=[{
        "speaker_actor_id": shots[0]["character_ids"][0], "text": "顺序一",
        "start_second": 0, "end_second": 3,
    }, {
        "speaker_actor_id": shots[0]["character_ids"][0], "text": "时间重叠",
        "start_second": 2, "end_second": 4,
    }]),
])
def test_visual_invalid_edits_fail_closed_without_mutating_source(client, mutate):
    sid, actor, scene, draft = _draft(client)
    original = deepcopy(draft)
    edits = _fields(draft)
    mutate(edits)
    with pytest.raises(LocalStoryWizardError):
        _apply(draft, edits, actor=actor, scene=scene)
    assert draft == original
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []


def test_visual_editor_allows_untimed_and_silent_shots(client):
    _, actor, scene, draft = _draft(client)
    shots = _fields(draft)
    shots[0]["dialogue"] = [{
        "speaker_actor_id": actor, "text": "无指定时槽",
        "start_second": None, "end_second": None,
    }]
    edited = _apply(draft, shots, actor=actor, scene=scene)
    assert edited["shots"][0]["dialogue"][0]["start_second"] is None
    assert edited["shots"][1]["dialogue"] == []


def test_visually_edited_audio_speaker_must_be_on_screen(client):
    _, actor, scene, draft = _draft(client)
    shots = _fields(draft)
    shots[0]["character_ids"] = []
    shots[0]["dialogue"] = [{
        "speaker_actor_id": actor, "text": "人不在画面里",
        "start_second": None, "end_second": None,
    }]
    with pytest.raises(LocalStoryWizardError):
        _apply(draft, shots, actor=actor, scene=scene)


def test_visual_form_source_and_main_app_compile_in_backend_only_ci():
    folder = Path(__file__).resolve().parents[1] / "frontend"
    for name in ("app.py", "visual_editor.py"):
        path = folder / name
        ast.parse(path.read_text("utf-8"), filename=str(path))
