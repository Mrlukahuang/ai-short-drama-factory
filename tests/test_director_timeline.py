"""Director timeline: integer edit positions and honest, read-only review prompts."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pytest

from drama_factory.pipeline.director_timeline import (
    DirectorTimelineError, director_timeline,
)
from drama_factory.pipeline.local_story_workflow import (
    make_storyboard_template, canonical_screenplay_digest,
)
from test_screenplay import setup_series


def _story(client, *, count=3, seconds=4):
    sid, bible, actor, scene = setup_series(client, "Director timeline test")
    draft = make_storyboard_template(
        sid, bible, [actor], scene, shot_count=count,
        seconds_per_shot=seconds,
    )
    for i, shot in enumerate(draft["shots"]):
        shot["continuity_start"] = f"房门位置 {i}"
        shot["continuity_end"] = f"房门位置 {i+1}"
    return sid, actor, scene, draft


def test_precise_shot_boundaries_and_readonly_disclosures(client):
    sid, actor, scene, draft = _story(client)
    previous = deepcopy(draft)
    fingerprint = canonical_screenplay_digest(draft)
    result = director_timeline(
        draft, actor_names={actor: "原创主角"},
        scene_names={scene: "虚构公寓"},
    )
    assert result["duration_seconds"] == 12
    assert result["shot_count"] == 3
    assert [(x["start_second"], x["end_second"]) for x in result["shots"]] == [
        (0, 4), (4, 8), (8, 12),
    ]
    assert all(x["scene_label"] == "虚构公寓" for x in result["shots"])
    assert len(result["review_prompts"]) == 0
    assert result["read_only"] is True
    assert result["approval_granted"] is False
    assert result["publish_approved"] is False
    assert result["human_continuity_review_required"] is True
    assert result["paid_api_calls"] == 0
    assert draft == previous
    assert canonical_screenplay_digest(draft) == fingerprint
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []


def test_continuity_mismatch_and_placeholder_are_only_review_prompts(client):
    _, actor, scene, draft = _story(client)
    draft["shots"][1]["continuity_start"] = "左手提着箱子"
    draft["shots"][2]["continuity_start"] = "请核对道具状态"
    result = director_timeline(draft)
    assert [(x["kind"], x["boundary_second"]) for x in result["review_prompts"]] == [
        ("continuity_text_diff", 4), ("continuity_unfinished", 8),
    ]
    assert result["approval_granted"] is False
    assert result["review_prompt_count"] == 2


def test_semantically_unverified_but_whitespace_normalized_notes(client):
    _, _, _, draft = _story(client, count=2)
    draft["shots"][0]["continuity_end"] = "门口   RIGHT hand  "
    draft["shots"][1]["continuity_start"] = "门口 right   hand"
    result = director_timeline(draft)
    assert result["review_prompts"] == []
    assert result["human_continuity_review_required"] is True


def test_scene_and_cast_transitions_are_review_cues_not_false_failures(client):
    sid, actor, scene, draft = _story(client, count=2)
    second = client.post(f"/api/v1/series/{sid}/assets", json={
        "kind": "actor", "key": "second", "specification": {
            "name": "另一虚构人物", "appearance": "黑色外套",
            "identity_anchors": ["圆形眼镜"],
        },
    })
    assert second.status_code == 201, second.text
    actor2 = second.json()["asset_id"]
    draft["shots"][1]["character_ids"] = [actor2]
    draft["shots"][1]["scene_id"] = None
    prompts = director_timeline(draft)["review_prompts"]
    assert [i["kind"] for i in prompts] == ["scene_transition", "cast_transition"]
    assert all("可能" in i["message"] for i in prompts)


def test_original_and_assigned_cue_slots_use_same_offline_integer_math(client):
    _, actor, _, draft = _story(client, count=2, seconds=5)
    draft["shots"][0]["dialogue"] = [
        {"speaker_actor_id": actor, "text": text,
         "start_second": None, "end_second": None}
        for text in ("一", "二", "三")
    ]
    draft["shots"][1]["dialogue"] = [
        {"speaker_actor_id": actor, "text": "导演指定",
         "start_second": 2, "end_second": 4},
    ]
    report = director_timeline(draft, actor_names={actor: "虚构主演"})
    assert [(s["start_second"], s["end_second"]) for s in report["dialogue_cues"]] == [
        (0, 2), (2, 4), (4, 5), (7, 9),
    ]
    assert [c["timing_source"] for c in report["dialogue_cues"]] == [
        "离线技术均分（未经导演批准）",
        "离线技术均分（未经导演批准）",
        "离线技术均分（未经导演批准）",
        "导演明确填写",
    ]
    assert report["dialogue_cues"][0]["speaker_label"] == "虚构主演"
    assert report["dialogue_cues"][3]["text"] == "导演指定"


def test_overflow_untimed_cues_generates_warning_without_dropping_lines(client):
    _, actor, _, draft = _story(client, count=1, seconds=2)
    draft["shots"][0]["dialogue"] = [
        {"speaker_actor_id": actor, "text": f"声道 {i}",
         "start_second": None, "end_second": None}
        for i in range(3)
    ]
    report = director_timeline(draft)
    assert [i["kind"] for i in report["review_prompts"]] == ["untimed_cue_overflow"]
    assert len(report["dialogue_cues"]) == 3
    assert report["dialogue_cues"][-1]["start_second"] == 2
    assert report["dialogue_cues"][-1]["end_second"] == 2
    assert report["approval_granted"] is False


@pytest.mark.parametrize("change", [
    lambda d: d.update(target_duration_seconds=30),
    lambda d: d["shots"][0].update(duration_seconds=0),
    lambda d: d["shots"][0].update(continuity_start=""),
    lambda d: d["shots"][0].update(dialogue=[{
        "speaker_actor_id": "unlisted", "text": "非法对白",
    }]),
])
def test_invalid_screenplay_refused_without_side_effect(client, change):
    sid, _, _, draft = _story(client)
    change(draft)
    with pytest.raises(DirectorTimelineError):
        director_timeline(draft)
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []


def test_timeline_refuses_oversized_preview_and_invalid_actor_inventory(client):
    _, _, _, draft = _story(client)
    long = deepcopy(draft)
    long["shots"] *= 8  # duplicate ID also invalid; must reject.
    long["target_duration_seconds"] *= 8
    with pytest.raises(DirectorTimelineError):
        director_timeline(long)
    with pytest.raises(DirectorTimelineError):
        director_timeline(draft, actor_names={"x": 1})
    with pytest.raises(DirectorTimelineError):
        director_timeline([])


def test_streamlit_director_timeline_source_compiles():
    root = Path(__file__).resolve().parents[1]
    for item in ("frontend/app.py", "frontend/visual_editor.py"):
        ast.parse((root / item).read_text("utf-8"), filename=item)
