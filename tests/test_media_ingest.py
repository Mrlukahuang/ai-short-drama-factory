"""Offline provider-media ingress: clipping, normalization, caching and rejection."""
from pathlib import Path
import shutil
import subprocess

import pytest

from drama_factory.pipeline.media_ingest import (
    MediaIngressError, inspect_source, normalize_local_video,
)
from drama_factory.pipeline.offline_render import inspect_mp4, render_approved_preview


ffmpeg_only = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe required",
)


def make_source(path: Path, duration: int = 2, pattern: str = "testsrc2"):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"{pattern}=size=640x360:rate=24",
        "-t", str(duration), "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(path),
    ], capture_output=True, text=True, check=True, timeout=90)
    return path


def make_ready_run(client):
    sid = client.post("/api/v1/projects", json={
        "title": "Mixed footage", "premise": "Replace one offline storyboard shot",
    }).json()["series_id"]
    ep = client.post(f"/api/v1/projects/{sid}/episodes", json={
        "title": "Pilot", "episode_number": 1, "target_duration_seconds": 4,
        "shots": [
            {"shot_id": "S1", "duration_seconds": 2,
             "visual_description": "Actor walks", "dialogue": ["Hello"]},
            {"shot_id": "S2", "duration_seconds": 2,
             "visual_description": "Actor waits", "dialogue": ["Wait"]},
        ],
    }).json()["episode_id"]
    run = client.post(f"/api/v1/episodes/{ep}/productions").json()["production_id"]
    assert client.post(f"/api/v1/productions/{run}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code == 200
    return run


@ffmpeg_only
def test_import_video_normalizes_orientation_audio_and_duration(tmp_path):
    src = make_source(tmp_path / "source.mp4")
    original = inspect_source(src, 2)
    assert original["has_audio"] is False
    result = tmp_path / "normalized.mp4"
    normalize_local_video(original, 2, result)
    inspection = inspect_mp4(result, 2)
    assert inspection["width"] == 360 and inspection["height"] == 640
    assert inspection["video_codec"] == "h264"
    assert inspection["audio_codec"] == "aac"


@ffmpeg_only
def test_single_shot_source_replacement_preserves_other_shot_cache(client, tmp_path):
    run = make_ready_run(client)
    root = tmp_path / "outputs"
    first = render_approved_preview(client.app.state.db, run, root)
    assert [x["cached"] for x in first["shots"]] == [False, False]
    motion = make_source(tmp_path / "moving.mp4")
    second = render_approved_preview(
        client.app.state.db, run, root, source_clips={"S1": motion},
    )
    assert [x["cached"] for x in second["shots"]] == [False, True]
    assert [x["media_source"] for x in second["shots"]] == [
        "provided_local_clip", "placeholder",
    ]
    assert second["supplied_local_clips"] == 1
    assert second["mp4_sha256"] != first["mp4_sha256"]
    assert inspect_mp4(Path(second["mp4_path"]), 4)["subtitle_codec"] == "mov_text"
    third = render_approved_preview(
        client.app.state.db, run, root, source_clips={"S1": motion},
    )
    assert [x["cached"] for x in third["shots"]] == [True, True]


@ffmpeg_only
def test_reject_non_video_early_without_marking_run_done(client, tmp_path):
    run = make_ready_run(client)
    bad_file = tmp_path / "broken.mp4"
    bad_file.write_bytes(b"not a video" * 200)
    root = tmp_path / "out"
    with pytest.raises(MediaIngressError):
        render_approved_preview(
            client.app.state.db, run, root, source_clips={"S1": bad_file},
        )
    with pytest.raises(Exception, match="unknown shot"):
        render_approved_preview(
            client.app.state.db, run, root, source_clips={"S99": bad_file},
        )
    too_short = make_source(tmp_path / "short.mp4", duration=1)
    with pytest.raises(MediaIngressError, match="enough footage"):
        render_approved_preview(
            client.app.state.db, run, root, source_clips={"S1": too_short},
        )
    assert client.app.state.db.one(
        "SELECT status FROM productions WHERE id=?", (run,)
    )["status"] == "ready_for_video_generation"
    assert not root.exists()
