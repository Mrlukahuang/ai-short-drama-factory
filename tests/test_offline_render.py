"""Real local FFmpeg smoke tests; never call external model providers."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from drama_factory.pipeline.offline_demo import build_offline_demo
from drama_factory.pipeline.offline_render import (
    PreviewError, inspect_mp4, render_approved_preview,
)


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe required for media integration",
)


def make_production(client, *, valid_duration=True):
    series = client.post("/api/v1/projects", json={
        "title": "End-to-end test series", "premise": "Test safe local preview",
    }).json()["series_id"]
    episode = client.post(f"/api/v1/projects/{series}/episodes", json={
        "title": "Episode one", "episode_number": 1,
        "target_duration_seconds": 2 if valid_duration else 3,
        "shots": [
            {"shot_id": "shot-1", "duration_seconds": 1,
             "visual_description": "Lead hears a knock", "dialogue": ["Who is there?"]},
            {"shot_id": "shot-2", "duration_seconds": 1,
             "visual_description": "Door opens", "dialogue": ["Hello"]},
        ],
    })
    assert episode.status_code == 201
    production = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
    ).json()["production_id"]
    return series, production


@requires_ffmpeg
def test_offline_preview_requires_existing_approval_gates(client, tmp_path):
    _, run = make_production(client)
    with pytest.raises(PreviewError, match="approvals"):
        render_approved_preview(client.app.state.db, run, tmp_path / "outputs")
    assert not (tmp_path / "outputs").exists()
    client.post(f"/api/v1/productions/{run}/approve-script")
    with pytest.raises(PreviewError, match="approvals"):
        render_approved_preview(client.app.state.db, run, tmp_path / "outputs")
    client.post(f"/api/v1/productions/{run}/approve-characters")
    manifest = render_approved_preview(client.app.state.db, run, tmp_path / "outputs")
    assert manifest["paid_api_calls"] == 0
    assert manifest["placeholder_visuals"] is True
    assert manifest["spoken_dialogue_generated"] is False
    assert manifest["has_subtitle_track"] is True
    assert manifest["media"]["subtitle_codec"] == "mov_text"
    assert all(not shot["cached"] for shot in manifest["shots"])
    assert Path(manifest["mp4_path"]).is_file()
    assert inspect_mp4(Path(manifest["mp4_path"]), 2)["audio_codec"] == "aac"
    record = client.app.state.db.one("SELECT status FROM productions WHERE id=?", (run,))
    assert record["status"] == "offline_preview_finished"


@requires_ffmpeg
def test_shot_level_reuse_and_targeted_corruption_repair(client, tmp_path):
    _, run = make_production(client)
    client.post(f"/api/v1/productions/{run}/approve-script")
    client.post(f"/api/v1/productions/{run}/approve-characters")
    folder = tmp_path / "deliver"
    initial = render_approved_preview(client.app.state.db, run, folder)
    again = render_approved_preview(client.app.state.db, run, folder)
    assert [x["cached"] for x in again["shots"]] == [True, True]
    assert initial["mp4_sha256"] == again["mp4_sha256"]
    working = Path(initial["mp4_path"]).parent
    first_clip = working / "clips" / initial["shots"][0]["clip_name"]
    first_clip.write_bytes(b"corrupt")
    repaired = render_approved_preview(client.app.state.db, run, folder)
    assert [x["cached"] for x in repaired["shots"]] == [False, True]
    assert repaired["mp4_sha256"] == initial["mp4_sha256"]
    assert json.loads((working / "manifest.json").read_text())["paid_api_calls"] == 0


@requires_ffmpeg
def test_timeline_mismatch_fails_without_claiming_render_success(client, tmp_path):
    _, run = make_production(client, valid_duration=False)
    client.post(f"/api/v1/productions/{run}/approve-script")
    client.post(f"/api/v1/productions/{run}/approve-characters")
    with pytest.raises(PreviewError, match="Shot durations"):
        render_approved_preview(client.app.state.db, run, tmp_path / "out")
    db_row = client.app.state.db.one("SELECT status,result_json FROM productions WHERE id=?", (run,))
    assert db_row["status"] == "ready_for_video_generation"
    assert db_row["result_json"] is None


@requires_ffmpeg
def test_entire_real_api_to_mp4_demo(tmp_path):
    report = build_offline_demo(tmp_path / "demo")
    out = tmp_path / "demo"
    assert (out / "demo.mp4").is_file()
    assert (out / "manifest.json").is_file()
    assert report["media"]["subtitle_codec"] == "mov_text"
    assert report["media"]["width"] == 360 and report["media"]["height"] == 640
    assert len(report["shots"]) == 3
    assert report["paid_api_calls"] == 0
    assert report["media"]["duration_seconds"] == pytest.approx(6, abs=0.6)
