"""Local screenplay UI helpers + real API approval path to playable MP4.

Tests use original synthetic data and only local FFmpeg (zero model calls).
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from drama_factory.pipeline.offline_render import PreviewError, render_approved_preview
from drama_factory.pipeline.offline_review import load_local_offline_review
from drama_factory.pipeline.local_story_workflow import (
    LocalStoryWizardError,
    canonical_screenplay_digest,
    make_storyboard_template,
    validated_draft_still_matches,
)
from test_screenplay import setup_series


def _template(client, series_id, bible, actor, scene, *, episode=1):
    return make_storyboard_template(
        series_id, bible, [actor], scene, episode_number=episode,
        shot_count=2, seconds_per_shot=3,
    )


def test_wizard_template_uses_selected_scope_and_correct_shot_timeline(client):
    sid, bible, actor, scene = setup_series(client, "Local storyboard")
    document = _template(client, sid, bible, actor, scene)
    assert document["series_id"] == sid
    assert document["story_bible_id"] == bible
    assert document["target_duration_seconds"] == 6
    assert [x["shot_id"] for x in document["shots"]] == ["S001", "S002"]
    assert [x["duration_seconds"] for x in document["shots"]] == [3, 3]
    assert all(s["character_ids"] == [actor] and s["scene_id"] == scene for s in document["shots"])
    assert "请编写" in document["shots"][0]["action"]
    res = client.post(f"/api/v1/series/{sid}/screenplays/validate", json=document)
    assert res.status_code == 200, res.text
    assert res.json()["review_required"] is True
    assert res.json()["paid_api_calls"] == 0
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []


@pytest.mark.parametrize("change", [
    {"shot_count": 13}, {"shot_count": 0}, {"seconds_per_shot": 31},
    {"shot_count": 4, "seconds_per_shot": 24},
    {"episode_number": True}, {"seconds_per_shot": "20"},
])
def test_bad_template_bounds_fail_before_io(client, change):
    sid, bible, actor, scene = setup_series(client, "Bounds")
    with pytest.raises(LocalStoryWizardError):
        make_storyboard_template(sid, bible, [actor], scene, **change)
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []


def test_template_rejects_unscoped_syntax_empty_or_duplicate_actors(client):
    sid, bible, actor, scene = setup_series(client, "Refs")
    for series, bible_id, actors, target_scene in (
        ("../" + sid, bible, [actor], scene),
        (sid, "fake-bible-id", [actor], scene),
        (sid, bible, [], scene),
        (sid, bible, [actor, actor], scene),
        (sid, bible, [actor], "../../etc/passwd"),
    ):
        with pytest.raises(LocalStoryWizardError):
            make_storyboard_template(series, bible_id, actors, target_scene)


def test_cross_series_asset_still_rejected_by_real_api(client):
    sid, bible, actor, scene = setup_series(client, "Origin")
    foreign, _, foreign_actor, _ = setup_series(client, "Foreign")
    draft = make_storyboard_template(sid, bible, [foreign_actor], scene, shot_count=1)
    result = client.post(f"/api/v1/series/{sid}/screenplays/validate", json=draft)
    assert result.status_code == 422
    assert foreign != sid


def test_validation_fingerprint_is_stale_after_any_editor_mutation(client):
    sid, bible, actor, scene = setup_series(client, "Review digest")
    draft = _template(client, sid, bible, actor, scene)
    valid = client.post(f"/api/v1/series/{sid}/screenplays/validate", json=draft)
    assert valid.status_code == 200
    token = {
        "series_id": sid, "valid": True, "review_required": True,
        "paid_api_calls": valid.json()["paid_api_calls"],
        "fingerprint": canonical_screenplay_digest(draft),
    }
    assert validated_draft_still_matches(draft, token, sid)
    edited = deepcopy(draft)
    edited["shots"][0]["action"] = "Changed after operator validation"
    assert not validated_draft_still_matches(edited, token, sid)
    edited = deepcopy(draft)
    edited["shots"][0]["dialogue"] = [{
        "speaker_actor_id": actor, "text": "不同的台词",
    }]
    assert not validated_draft_still_matches(edited, token, sid)
    assert not validated_draft_still_matches(draft, token, "proj_" + "0"*14)
    assert not validated_draft_still_matches(draft, {**token, "review_required": False}, sid)
    assert not validated_draft_still_matches(draft, {**token, "paid_api_calls": 1}, sid)
    assert not validated_draft_still_matches(draft, None, sid)
    assert not validated_draft_still_matches([], token, sid)
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []


def test_draft_digest_normalized_whitespace_and_key_order(client):
    sid, bible, actor, scene = setup_series(client, "Normalized JSON")
    first = _template(client, sid, bible, actor, scene)
    reordered = dict(reversed(list(first.items())))
    assert canonical_screenplay_digest(first) == canonical_screenplay_digest(reordered)


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Full local MP4 integration requires FFmpeg",
)
def test_human_screenplay_to_two_approvals_real_mp4_and_readonly_review(client, tmp_path):
    sid, bible, actor, scene = setup_series(client, "Local full chain")
    draft = _template(client, sid, bible, actor, scene)
    draft["episode_title"] = "一段原创故事"
    draft["shots"][0]["action"] = "虚构人物走向房门"
    draft["shots"][1]["action"] = "房门缓缓开启"
    fingerprint = canonical_screenplay_digest(draft)
    validated = client.post(f"/api/v1/series/{sid}/screenplays/validate", json=draft)
    assert validated.status_code == 200, validated.text
    token = {
        "series_id": sid, "valid": True, "review_required": True,
        "paid_api_calls": 0, "fingerprint": fingerprint,
    }
    assert validated_draft_still_matches(draft, token, sid)
    commit_url = f"/api/v1/series/{sid}/screenplays/commit"
    assert client.post(commit_url, json={
        "screenplay": draft, "reviewed_by_operator": False,
    }).status_code == 422
    committed = client.post(commit_url, json={
        "screenplay": draft, "reviewed_by_operator": True,
    })
    assert committed.status_code == 201, committed.text
    episode = committed.json()["episode_id"]
    assert committed.json()["production_created"] is False
    assert client.post(commit_url, json={
        "screenplay": draft, "reviewed_by_operator": True,
    }).status_code == 409
    production = client.post(f"/api/v1/episodes/{episode}/productions")
    assert production.status_code == 201, production.text
    run = production.json()["production_id"]
    root = tmp_path / "local-reviews"
    with pytest.raises(PreviewError, match="approvals"):
        render_approved_preview(client.app.state.db, run, root)
    first = client.post(f"/api/v1/productions/{run}/approve-script")
    assert first.status_code == 200
    with pytest.raises(PreviewError, match="approvals"):
        render_approved_preview(client.app.state.db, run, root)
    second = client.post(f"/api/v1/productions/{run}/approve-characters")
    assert second.status_code == 200
    delivery = render_approved_preview(client.app.state.db, run, root)
    report = load_local_offline_review(
        client.app.state.db, run, root, series_id=sid,
    )
    assert report["technical_qa_passed"] is True
    assert report["paid_model_requests_by_review"] == 0
    assert report["publish_approved"] is False
    assert delivery["paid_api_calls"] == 0
    assert Path(report["preview_path"]).is_file()
    assert len(report["shots"]) == 2
    assert delivery["media"]["subtitle_codec"] == "mov_text"
    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code == 409


def test_frontend_local_workbench_python_syntax_is_valid():
    # CI normally installs the backend without Streamlit; still compile the UI.
    import ast
    source = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    ast.parse(source.read_text("utf-8"), filename=str(source))
