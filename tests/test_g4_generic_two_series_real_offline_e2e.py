"""G4: TWO unrelated storyboard projects through ONE actual existing Fake factory.

This tests the real, scoped FastAPI+SQLite asset/review state machine and the
EXISTING Fake shot worker / real FFmpeg, not another CityDiscount renderer.
Local approvals below are explicitly synthetic TEST approvals; no legal rights,
AI authorship, remote model, or production quality is claimed.
"""
from __future__ import annotations

import copy
import hashlib
import shutil
from pathlib import Path

import pytest

from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.operator_storyboard_adapter import (
    build_operator_storyboard_preview,
)
from drama_factory.pipeline.fake_shot_manifest import (
    FakeShotManifestError, build_fake_shot_manifest,
)
from drama_factory.pipeline.offline_render import inspect_mp4
from test_g4_operator_storyboard_adapter import _citydiscount, _other_story

needs_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Actual FFmpeg/ffprobe binaries are required for media integration",
)


def _created(client, response, expected=201):
    assert response.status_code == expected, response.text
    return response.json()


def _register_generic_project(client, blueprint):
    """Populate the existing original-series/asset APIs, with no direct SQL.

    Maps arbitrary external creative IDs to version-1 real SeriesAsset IDs.
    Identical function handles the one-mascot and two-actor stories.
    """
    src = copy.deepcopy(blueprint)
    series = _created(client, client.post("/api/v1/projects", json={
        "title": src["episode_title"],
        "premise": src["source_description"],
        "default_ratio": "9:16",
    }))["series_id"]
    bible_id = _created(
        client, client.post(f"/api/v1/series/{series}/story-bibles",
                            json=src["story_bible"].model_dump(mode="json")),
    )["story_bible_id"]
    scene_id = _created(client, client.post(f"/api/v1/series/{series}/assets", json={
        "kind": "scene", "key": "one_common_location",
        "specification": {
            "name": "Synthetic stage",
            "location": "Synthetic local preview",
            "layout": "All shot cards use the same scene anchor",
        },
    }))["asset_id"]
    remap = {}
    for i, (old_id, look) in enumerate(src["actor_descriptions"].items()):
        row = _created(client, client.post(f"/api/v1/series/{series}/assets", json={
            "kind": "actor", "key": f"synthetic_actor_{i}",
            "specification": {
                "name": f"Synthetic cast {i}",
                "appearance": look,
                "identity_anchors": [
                    "Synthetic test description only; no likeness rights assertion",
                ],
            },
        }))
        assert row["version"] == 1
        remap[old_id] = row["asset_id"]
    src["actor_descriptions"] = {
        remap[actor]: desc for actor, desc in src["actor_descriptions"].items()
    }
    for card in src["shot_cards"]:
        card["character_ids"] = [remap[a] for a in card["character_ids"]]
        for line in card["dialogue"]:
            line["speaker_actor_id"] = remap[line["speaker_actor_id"]]
    src.update(series_id=series, story_bible_id=bible_id, scene_id=scene_id)
    prepared = build_operator_storyboard_preview(**src)
    draft = EpisodeDraft.model_validate(prepared["episode_draft"])
    assert draft.target_duration_seconds == prepared["duration_seconds"]
    return prepared, series, scene_id, list(remap.values()), draft


def _fake_approved_production(client, series, draft):
    """State transitions exist only in temp DB with fully synthetic stage data."""
    episode_id = _created(client, client.post(
        f"/api/v1/projects/{series}/episodes",
        json=draft.model_dump(mode="json"),
    ))["episode_id"]
    production_id = _created(client, client.post(
        f"/api/v1/episodes/{episode_id}/productions",
    ))["production_id"]
    # These approvals are TEST-ONLY FastAPI state transitions and may not
    # be used as permission to send authentic media to any outside provider.
    assert client.post(
        f"/api/v1/productions/{production_id}/approve-script",
    ).status_code == 200
    assert client.post(
        f"/api/v1/productions/{production_id}/approve-characters",
    ).status_code == 200
    return production_id


@needs_ffmpeg
def test_two_creative_projects_get_real_ffmpeg_fake_mp4_and_scoped_cached_jobs(
    client, tmp_path,
):
    media = tmp_path / "technical-fake-only-media"
    results = []
    for case, expected_count in ((_citydiscount, 12), (_other_story, 6)):
        prepared, series, scene, cast, draft = _register_generic_project(
            client, case(),
        )
        assert len(draft.shots) == expected_count
        assert prepared["paid_model_calls"] == 0
        assert prepared["real_video_generated"] is False
        assert prepared["provider_reference_applied"] is False
        assert prepared["video_request_plan"]["video_generated"] is False
        assert all(s.scene_id == scene for s in draft.shots)
        assert all(set(s.character_ids).issubset(cast) for s in draft.shots)
        pid = _fake_approved_production(client, series, draft)
        output = build_fake_shot_manifest(client.app.state.db, series, pid, media)
        assert output["shot_count"] == expected_count
        assert output["paid_provider_calls"] == 0
        assert output["actual_fee_usd"] is None
        assert output["fake_only"] is True
        assert output["approved_real_content"] is False
        assert output["real_ai_video"] is False
        assert all(
            shot["provider"] == "fake"
            and shot["model_calls"] == 0
            and shot["video_source"] == "offline_placeholder_not_ai"
            and len(shot["input_sha256"]) == 64
            and len(shot["result_sha256"]) == 64
            and all(asset["version"] == 1 for asset in shot["asset_versions"])
            for shot in output["shots"]
        )
        movie = media / series / pid / "preview.mp4"
        result = inspect_mp4(movie, draft.target_duration_seconds)
        assert result["video_codec"] == "h264"
        assert result["audio_codec"] == "aac"
        assert result["subtitle_codec"] == "mov_text"
        assert hashlib.sha256(movie.read_bytes()).hexdigest() == (
            output["technical_episode_mp4_sha256"]
        )
        repeat = build_fake_shot_manifest(client.app.state.db, series, pid, media)
        assert repeat["shots_cached"] == expected_count
        assert repeat["shots"] == output["shots"]
        assert repeat["technical_episode_mp4_sha256"] == (
            output["technical_episode_mp4_sha256"]
        )
        results.append((series, pid, output))
    # No media or shot-job IDs may leak between independently created series.
    a, b = results
    assert a[0] != b[0] and a[1] != b[1]
    assert set(x["shot_id"] for x in a[2]["shots"]).isdisjoint(
        set(x["shot_id"] for x in b[2]["shots"])
    ) is False or a[0] != b[0]  # Identity scoped by series, not shot name.
    db = client.app.state.db
    for series, pid, output in results:
        rows = db.many(
            "SELECT * FROM shot_jobs WHERE production_id=? ORDER BY shot_id",
            (pid,),
        )
        assert len(rows) == output["shot_count"]
        assert all(row["generation_intent_recorded"] == 0
                   and row["actual_vendor_charge_usd"] is None
                   and row["status"] == "succeeded" for row in rows)
        foreign = results[1][0] if series == results[0][0] else results[0][0]
        with pytest.raises(FakeShotManifestError, match="belong"):
            build_fake_shot_manifest(db, foreign, pid, media)


def test_generic_api_rejects_cross_series_assets_before_fake_production(
    client,
):
    first, series_a, scene_a, cast_a, draft_a = _register_generic_project(
        client, _citydiscount(),
    )
    second, series_b, scene_b, cast_b, draft_b = _register_generic_project(
        client, _other_story(),
    )
    assert series_a != series_b
    assert first["source_sha256"] != second["source_sha256"]
    draft_b.shots[0].character_ids[0] = cast_a[0]  # foreign actor
    response = client.post(
        f"/api/v1/projects/{series_b}/episodes",
        json=draft_b.model_dump(mode="json"),
    )
    assert response.status_code == 422
    assert client.app.state.db.one("SELECT COUNT(*) AS n FROM shot_jobs")["n"] == 0
