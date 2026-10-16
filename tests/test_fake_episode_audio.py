"""P5 pure local FFmpeg integration: synthetic tone, caption index, music."""
import hashlib
import shutil
from pathlib import Path

import pytest

from drama_factory.pipeline.fake_episode_audio import (
    FakeAudioStageError, build_fake_episode_audio,
)
from drama_factory.pipeline.fake_shot_manifest import build_fake_shot_manifest
from drama_factory.pipeline.offline_render import inspect_mp4
from test_fake_shot_manifest import _setup

needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="Local FFmpeg needed",
)


@needs_ffmpeg
def test_p5_synthetic_cue_music_subtitle_bridge_and_mixed_mp4(client, tmp_path):
    series, pid = _setup(client, tmp_path)
    db = client.app.state.db
    media = tmp_path / "renders"
    shot_manifest = build_fake_shot_manifest(db, series, pid, media)
    voice, subs, music = build_fake_episode_audio(
        db, series, pid, shot_manifest, media, tmp_path / "audio",
    )
    assert (voice["step"], subs["step"], music["step"]) == (
        "06_dialogue", "07_subtitles", "08_music",
    )
    assert voice["synthetic_non_speech"] is True
    assert music["synthetic_music_only"] is True
    assert len(subs["subtitle_cues"]) == 7  # two actors in S001, one thereafter
    assert all(x["fake_only"] and x["paid_provider_calls"] == 0
               and x["actual_fee_usd"] is None
               and x["publish_approved"] is False for x in (voice, subs, music))
    for name, digest in (
        (voice["wav_name"], voice["wav_sha256"]),
        (music["wav_name"], music["wav_sha256"]),
        (music["mixed_mp4_name"], music["mixed_mp4_sha256"]),
    ):
        data = (tmp_path / "audio" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
    assert inspect_mp4(
        tmp_path / "audio" / music["mixed_mp4_name"], 60,
    )["subtitle_codec"] == "mov_text"
    assert music["mix"]["real_tts_generated"] is False


@needs_ffmpeg
def test_p5_rejects_forged_manifest_and_corrupt_preview(client, tmp_path):
    series, pid = _setup(client, tmp_path)
    db = client.app.state.db
    media = tmp_path / "renders"
    manifest = build_fake_shot_manifest(db, series, pid, media)
    with pytest.raises(FakeAudioStageError, match="Verified P4"):
        build_fake_episode_audio(
            db, series, pid, {**manifest, "paid_provider_calls": 1},
            media, tmp_path / "bad",
        )
    with pytest.raises(FakeAudioStageError, match="hash mismatch"):
        build_fake_episode_audio(
            db, series, pid, {**manifest, "technical_episode_mp4_sha256": "0" * 64},
            media, tmp_path / "bad",
        )
    assert not (tmp_path / "bad").exists()


@needs_ffmpeg
def test_p5_rejects_cross_series_and_fake_speaker_does_not_grant_voice_rights(
    client, tmp_path,
):
    series, pid = _setup(client, tmp_path)
    db = client.app.state.db
    media = tmp_path / "renders"
    manifest = build_fake_shot_manifest(db, series, pid, media)
    with pytest.raises(FakeAudioStageError):
        build_fake_episode_audio(
            db, "proj_" + "0" * 14, pid, manifest,
            media, tmp_path / "bad",
        )
    voice = db.one(
        "SELECT specification_json FROM series_assets WHERE series_id=? AND kind='voice'",
        (series,),
    )
    assert '"source_consent_reference":""' in voice["specification_json"]
