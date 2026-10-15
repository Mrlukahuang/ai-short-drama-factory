"""P4 live SQLite/FFmpeg technical test using wholly synthetic P1–P3 assets."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from drama_factory.pipeline.fake_story_bible import build_fake_story_bible
from drama_factory.pipeline.fake_episode_screenplay import build_fake_episode_screenplay
from drama_factory.pipeline.fake_cast_assets import bind_fake_cast_assets
from drama_factory.pipeline.fake_shot_manifest import (
    FakeShotManifestError, build_fake_shot_manifest,
)
from drama_factory.pipeline.offline_render import inspect_mp4
from drama_factory.pipeline.screenplay import Screenplay

needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="actual local FFmpeg / ffprobe binaries required",
)


def _setup(client, tmp_path, *, approve=True, label="one"):
    source = tmp_path / f"{label}.txt"
    source.write_text(
        f"两个虚构朋友在雨夜旧车站寻找一张古老地图。{label}，完全为合成技术测试。",
        encoding="utf-8",
    )
    b = build_fake_story_bible(source)
    p = build_fake_episode_screenplay(b, target_duration_seconds=60)
    db = client.app.state.db
    bounded = bind_fake_cast_assets(db, b, p)
    screenplay = Screenplay.model_validate(bounded["screenplay"])
    episode = client.post(
        f"/api/v1/projects/{bounded['series_id']}/episodes",
        json=screenplay.to_episode_draft().model_dump(mode="json"),
    )
    assert episode.status_code == 201, episode.text
    run = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions",
    )
    assert run.status_code == 201, run.text
    pid = run.json()["production_id"]
    if approve:
        assert client.post(f"/api/v1/productions/{pid}/approve-script").status_code == 200
        assert client.post(f"/api/v1/productions/{pid}/approve-characters").status_code == 200
    return bounded["series_id"], pid


@needs_ffmpeg
def test_six_real_ffmpeg_fake_clips_and_asset_version_digest_manifest(client, tmp_path):
    series, pid = _setup(client, tmp_path)
    db = client.app.state.db
    media = tmp_path / "renders"
    first = build_fake_shot_manifest(db, series, pid, media)
    assert first["step"] == "05_shots"
    assert first["shot_count"] == 6
    assert first["fake_only"] is True
    assert first["approved_real_content"] is False
    assert first["real_ai_video"] is False
    assert first["paid_provider_calls"] == 0
    assert first["actual_fee_usd"] is None
    assert len(first["technical_episode_mp4_sha256"]) == 64
    assert [x["shot_id"] for x in first["shots"]] == [
        "S001", "S002", "S003", "S004", "S005", "S006",
    ]
    assert all(x["provider"] == "fake" and x["model_calls"] == 0
               and x["video_source"] == "offline_placeholder_not_ai"
               for x in first["shots"])
    assert all(x["asset_versions"] and
               all(a["version"] == 1 and len(a["specification_sha256"]) == 64
                   for a in x["asset_versions"])
               for x in first["shots"])
    assert all(len(x["result_sha256"]) == len(x["input_sha256"]) == 64
               for x in first["shots"])
    rows = db.many(
        "SELECT * FROM shot_jobs WHERE production_id=? ORDER BY shot_id", (pid,),
    )
    assert len(rows) == 6
    assert all(x["status"] == "succeeded" and x["provider"] == "fake"
               and x["actual_vendor_charge_usd"] is None
               and x["generation_intent_recorded"] == 0 for x in rows)
    second = build_fake_shot_manifest(db, series, pid, media)
    assert second["shots_cached"] == 6
    assert second["shots"] == first["shots"]
    mp4 = media / series / pid / "preview.mp4"
    assert mp4.is_file()
    assert inspect_mp4(mp4, 60)["subtitle_codec"] == "mov_text"


@needs_ffmpeg
def test_scope_and_approval_denied_before_media_render(client, tmp_path):
    series, pid = _setup(client, tmp_path, approve=False)
    root = tmp_path / "videos"
    db = client.app.state.db
    with pytest.raises(Exception, match="approval"):
        build_fake_shot_manifest(db, series, pid, root)
    with pytest.raises(FakeShotManifestError, match="belong"):
        build_fake_shot_manifest(db, "proj_" + "0" * 14, pid, root)
    assert not root.exists()
    assert db.one("SELECT COUNT(*) AS n FROM shot_jobs")["n"] == 0
