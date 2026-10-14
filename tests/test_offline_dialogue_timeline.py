"""PR-10b: approved per-shot fake voice -> full offline dialogue track -> MP4."""
from __future__ import annotations

import hashlib
import shutil
import wave
from pathlib import Path

import pytest

from drama_factory.pipeline.offline_dialogue_timeline import (
    build_fake_episode_dialogue_timeline,
)
from drama_factory.pipeline.offline_demo import build_offline_demo
from drama_factory.providers.dialogue_audio import DialogueGenerationDenied
from test_offline_render import make_production


def _approved_voice(client, *, consent="original-local-synthetic-only"):
    series, run = make_production(client)
    assert client.post(f"/api/v1/productions/{run}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code == 200
    voice = client.post(f"/api/v1/series/{series}/assets", json={
        "kind": "voice", "key": "lead_voice", "specification": {
            "name": "Original fake test tone",
            "voice_description": "One fixed synthetic timing sine per shot",
            "source_consent_reference": consent,
        },
    })
    assert voice.status_code == 201
    return run, voice.json()["asset_id"]


def test_two_approved_shot_lines_create_exact_two_second_pcm_timeline_and_cache(client, tmp_path):
    run, voice = _approved_voice(client)
    db = client.app.state.db
    out = tmp_path / "per-shot-fake-voice"
    first = build_fake_episode_dialogue_timeline(
        db, run, voice, out, operator_confirmed_voice_rights=True,
    )
    track = Path(first["local_wav_path"])
    assert track.is_file()
    with wave.open(str(track), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 48000
        assert wav.getnframes() == 2 * 48000
    assert first["reused"] is False
    assert first["duration_seconds"] == 2
    assert len(first["shots"]) == 2
    assert sum(x["seconds"] for x in first["shots"]) == 2
    assert first["real_spoken_dialogue_generated"] is False
    assert first["voice_consent_independently_verified"] is False
    assert first["publish_approved"] is False
    assert first["paid_provider_calls"] == 0
    assert "Who is there?" not in str(first)
    first_bytes = track.read_bytes()
    assert hashlib.sha256(first_bytes).hexdigest() == first["local_wav_sha256"]
    again = build_fake_episode_dialogue_timeline(
        db, run, voice, out, operator_confirmed_voice_rights=True,
    )
    assert again["reused"] is True
    assert again["fingerprint"] == first["fingerprint"]
    track.write_bytes(b"fake-wav-corruption" * 200)
    repaired = build_fake_episode_dialogue_timeline(
        db, run, voice, out, operator_confirmed_voice_rights=True,
    )
    assert repaired["reused"] is False
    assert repaired["local_wav_sha256"] == first["local_wav_sha256"]


def test_missing_voice_confirmation_and_foreign_voice_fail_before_file_io(client, tmp_path):
    run, voice = _approved_voice(client)
    out = tmp_path / "must-never-create"
    with pytest.raises(DialogueGenerationDenied):
        build_fake_episode_dialogue_timeline(client.app.state.db, run, voice, out)
    assert not out.exists()
    with pytest.raises(DialogueGenerationDenied):
        build_fake_episode_dialogue_timeline(
            client.app.state.db, run, "not-a-valid-series-voice", out,
            operator_confirmed_voice_rights=True,
        )
    assert not out.exists()


def test_unapproved_production_cannot_build_audio_timeline(client, tmp_path):
    _, run = make_production(client)
    out = tmp_path / "unapproved-audio"
    with pytest.raises(DialogueGenerationDenied):
        build_fake_episode_dialogue_timeline(
            client.app.state.db, run, "unused-voice", out,
            operator_confirmed_voice_rights=True,
        )
    assert not out.exists()


@pytest.mark.parametrize("bad", ["true", None, 0, 1, [], {}])
def test_invalid_fake_voice_demo_option_fails_before_file_creation(tmp_path, bad):
    root = tmp_path / "bad-flag"
    with pytest.raises(ValueError, match="Fake voice timeline flag"):
        build_offline_demo(root, with_fake_voice_timeline=bad)
    assert not root.exists()


def test_fake_voice_and_synthetic_audio_modes_cannot_both_run(tmp_path):
    root = tmp_path / "conflicting-flags"
    with pytest.raises(ValueError, match="Select only one"):
        build_offline_demo(root, with_fake_voice_timeline=True,
                           with_synthetic_audio_mix=True)
    assert not root.exists()


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Real FFmpeg test runs under mandatory offline-video job",
)


@ffmpeg_required
def test_real_six_second_end_to_end_script_voice_assets_shot_wavs_music_and_mp4(tmp_path):
    root = tmp_path / "voice-timeline-e2e"
    result = build_offline_demo(
        root, duration_seconds=6, with_fake_voice_timeline=True,
    )
    assert result["fake_voice_timeline"] is True
    assert result["fake_voice_shots"] == 3
    assert result["synthetic_test_tone_stems"] is False
    assert result["local_dialogue_audio_supplied"] is True
    assert result["local_music_audio_supplied"] is True
    assert result["audio_rights_self_attested"] is True
    assert result["voice_license_independently_verified"] is False
    assert result["spoken_dialogue_generated"] is False
    assert result["real_tts_generated"] is False
    assert result["paid_api_calls"] == 0
    assert result["technical_qa"]["subtitle_sidecar_timing_passed"] is True
    assert result["technical_qa"]["technical_decode_passed"] is True
    assert result["technical_qa"]["publish_approved"] is False
    assert result["technical_qa"]["production_ready"] is False
    from drama_factory.pipeline.offline_render import inspect_mp4
    assert inspect_mp4(root / "demo.mp4", 6)["subtitle_codec"] == "mov_text"
