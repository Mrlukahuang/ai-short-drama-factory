"""PR-15b: real local PCM dialogue/music mix into the approved MP4 pipeline.

Every sample is generated locally by FFmpeg's sine filter. No voice cloning,
TTS, real person speech, cloud media, drive access or paid provider calls.
"""
from __future__ import annotations

import copy
import shutil
import subprocess
from pathlib import Path

import pytest

from drama_factory.pipeline.offline_audio import (
    OfflineAudioError, inspect_local_wav,
)
from drama_factory.pipeline.offline_render import (
    PreviewError, inspect_mp4, render_approved_preview,
)
from test_offline_render import make_production

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Mandatory offline-video job has pinned FFmpeg/FFprobe",
)


def _tone(path: Path, seconds: float, hz: int):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-y", "-f", "lavfi", "-i",
         f"sine=frequency={hz}:duration={seconds}:sample_rate=48000",
         "-ac", "1", "-c:a", "pcm_s16le", str(path)],
        check=True, capture_output=True, timeout=30,
    )
    return path


def _approved(client):
    _, run = make_production(client)
    assert client.post(f"/api/v1/productions/{run}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code == 200
    return run


@requires_ffmpeg
def test_two_real_wav_tracks_overlay_preserves_mp4_subtitles_and_shot_cache(client, tmp_path):
    run = _approved(client)
    root = tmp_path / "delivery"
    baseline = render_approved_preview(client.app.state.db, run, root)
    dialogue = _tone(tmp_path / "synthetic-dialogue.wav", 1.0, 520)
    music = _tone(tmp_path / "synthetic-music.wav", 2.0, 220)
    mixed = render_approved_preview(
        client.app.state.db, run, root,
        dialogue_audio=dialogue, music_audio=music,
        operator_confirmed_audio_rights=True,
    )
    assert mixed["mp4_sha256"] != baseline["mp4_sha256"]
    assert [s["clip_sha256"] for s in mixed["shots"]] == [
        s["clip_sha256"] for s in baseline["shots"]
    ]
    assert [s["cached"] for s in mixed["shots"]] == [True, True]
    assert mixed["offline_audio_mix"]["subtitle_track_preserved"] is True
    assert mixed["offline_audio_mix"]["locally_supplied_dialogue"] is True
    assert mixed["offline_audio_mix"]["locally_supplied_music"] is True
    assert mixed["audio_rights_self_attested"] is True
    assert mixed["voice_license_independently_verified"] is False
    assert mixed["spoken_dialogue_generated"] is False
    assert mixed["synthetic_tone_audio"] is False
    assert mixed["technical_qa"]["technical_decode_passed"] is True
    assert mixed["technical_qa"]["publish_approved"] is False
    assert mixed["technical_qa"]["production_ready"] is False
    assert mixed["paid_api_calls"] == 0
    assert inspect_mp4(Path(mixed["mp4_path"]), 2)["subtitle_codec"] == "mov_text"
    again = render_approved_preview(
        client.app.state.db, run, root,
        dialogue_audio=dialogue, music_audio=music,
        operator_confirmed_audio_rights=True,
    )
    assert [s["cached"] for s in again["shots"]] == [True, True]
    assert again["mp4_sha256"] == mixed["mp4_sha256"]


@requires_ffmpeg
def test_music_only_keeps_existing_video_audio_under_mix(client, tmp_path):
    run = _approved(client)
    music = _tone(tmp_path / "synthetic-music.wav", 2, 196)
    result = render_approved_preview(
        client.app.state.db, run, tmp_path / "out",
        music_audio=music, operator_confirmed_audio_rights=True,
    )
    assert result["offline_audio_mix"]["locally_supplied_dialogue"] is False
    assert result["offline_audio_mix"]["locally_supplied_music"] is True
    assert result["synthetic_tone_audio"] is True
    assert result["technical_qa"]["muxed_subtitle_track_present"] is True
    assert result["paid_api_calls"] == 0


@requires_ffmpeg
def test_audio_rights_attestation_rejected_before_side_effects(client, tmp_path):
    run = _approved(client)
    source = _tone(tmp_path / "synthetic.wav", 2, 300)
    out = tmp_path / "not-created"
    with pytest.raises(PreviewError, match="rights attestation"):
        render_approved_preview(
            client.app.state.db, run, out, dialogue_audio=source,
        )
    assert not out.exists()
    row = client.app.state.db.one("SELECT status,result_json FROM productions WHERE id=?", (run,))
    assert row["status"] == "ready_for_video_generation"
    assert row["result_json"] is None


@requires_ffmpeg
def test_invalid_or_too_short_audio_is_rejected_before_preview(client, tmp_path):
    run = _approved(client)
    too_short = _tone(tmp_path / "short-music.wav", 0.5, 220)
    out = tmp_path / "no-render"
    with pytest.raises(OfflineAudioError, match="cover episode"):
        render_approved_preview(
            client.app.state.db, run, out, music_audio=too_short,
            operator_confirmed_audio_rights=True,
        )
    assert not out.exists()
    invalid = tmp_path / "not-a-wave.wav"
    invalid.write_bytes(b"not PCM WAV" * 200)
    with pytest.raises(OfflineAudioError):
        render_approved_preview(
            client.app.state.db, run, out, dialogue_audio=invalid,
            operator_confirmed_audio_rights=True,
        )
    assert not out.exists()


@requires_ffmpeg
def test_audio_fingerprint_change_forces_new_mix_but_not_new_video_shots(client, tmp_path):
    run = _approved(client)
    root = tmp_path / "cache"
    voice = _tone(tmp_path / "voice.wav", 1, 440)
    original = render_approved_preview(
        client.app.state.db, run, root, dialogue_audio=voice,
        operator_confirmed_audio_rights=True,
    )
    _tone(voice, 1, 880)
    changed = render_approved_preview(
        client.app.state.db, run, root, dialogue_audio=voice,
        operator_confirmed_audio_rights=True,
    )
    assert changed["mp4_sha256"] != original["mp4_sha256"]
    assert changed["offline_audio_mix"]["dialogue_sha256"] != original["offline_audio_mix"]["dialogue_sha256"]
    assert all(s["cached"] for s in changed["shots"])
    assert changed["technical_qa"]["video_sha256_matches_manifest"] is True


@requires_ffmpeg
def test_unreviewed_real_media_publishing_is_not_authorized(client, tmp_path):
    run = _approved(client)
    voice = _tone(tmp_path / "synthetic.wav", 1, 240)
    result = render_approved_preview(
        client.app.state.db, run, tmp_path / "qa",
        dialogue_audio=voice, operator_confirmed_audio_rights=True,
    )
    from drama_factory.pipeline.offline_qa import (
        OfflineQAError, inspect_offline_delivery,
    )
    with pytest.raises(OfflineQAError, match="Human-authenticated"):
        inspect_offline_delivery(result, Path(result["mp4_path"]),
                                 require_real_footage=True)
    assert result["technical_qa"]["copyright_scope_verified"] is False
