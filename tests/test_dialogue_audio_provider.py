"""PR-10a voice assignment, approval, consent and real local WAV fake contract."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import wave
from pathlib import Path

import pytest
from pydantic import ValidationError

from drama_factory.providers.dialogue_audio import (
    DialogueGenerationDenied, DialogueGenerationSpec,
    FakeDialogueAudioProvider, GeminiDialogueAudioProvider,
)
from test_offline_render import make_production


def _voice(client, series_id: str, *, key="lead_voice", consent="owner-created-local-tone"):
    response = client.post(f"/api/v1/series/{series_id}/assets", json={
        "kind": "voice", "key": key,
        "specification": {
            "name": "Fictional synthetic timing placeholder",
            "voice_description": "No actual spoken words or human voice",
            "source_consent_reference": consent,
        },
    })
    assert response.status_code == 201, response.text
    return response.json()["asset_id"]


def _spec(series, production, voice, *, text="Who is there?", shot="shot-1"):
    return DialogueGenerationSpec(
        series_id=series, production_id=production,
        voice_asset_id=voice, shot_id=shot, dialogue_text=text,
        duration_seconds=1, language="en-NZ",
        operator_confirmed_voice_rights=True,
    )


def _approved(client):
    series, production = make_production(client)
    assert client.post(f"/api/v1/productions/{production}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{production}/approve-characters").status_code == 200
    return series, production


def test_fake_voice_tone_real_wav_stable_fingerprint_reusable_and_no_real_tts(client, tmp_path):
    series, production = _approved(client)
    voice = _voice(client, series)
    spec = _spec(series, production, voice)
    provider = FakeDialogueAudioProvider()
    first = provider.synthesize(client.app.state.db, spec, tmp_path / "wav")
    source = Path(first["local_wav_path"])
    assert source.is_file()
    assert first["local_wav_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert first["reused"] is False
    assert first["synthetic_timing_tone_only"] is True
    assert first["real_spoken_dialogue_generated"] is False
    assert first["voice_consent_independently_verified"] is False
    assert first["publish_approved"] is False
    assert first["paid_model_calls"] == 0
    assert spec.dialogue_text not in str(first)
    with wave.open(str(source), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 48000
        assert wav.getnframes() == 48000
    second = provider.synthesize(client.app.state.db, spec, tmp_path / "wav")
    assert second["reused"] is True
    assert second["local_wav_sha256"] == first["local_wav_sha256"]
    assert second["fingerprint"] == first["fingerprint"]
    # Same path with corrupted bytes must rebuild from the approved text and voice.
    source.write_bytes(b"corrupted-but-not-actually-wav" * 20)
    repaired = provider.synthesize(client.app.state.db, spec, tmp_path / "wav")
    assert repaired["reused"] is False
    assert repaired["local_wav_sha256"] == first["local_wav_sha256"]


def test_immutable_voice_asset_version_and_shot_text_change_fingerprint(client, tmp_path):
    series, production = _approved(client)
    voice1 = _voice(client, series)
    voice2 = _voice(client, series)
    provider = FakeDialogueAudioProvider()
    first = provider.synthesize(client.app.state.db, _spec(series, production, voice1), tmp_path)
    second = provider.synthesize(client.app.state.db, _spec(series, production, voice2), tmp_path)
    third = provider.synthesize(client.app.state.db, _spec(series, production, voice1,
                    text="Hello", shot="shot-2"), tmp_path)
    assert first["fingerprint"] != second["fingerprint"]
    assert first["fingerprint"] != third["fingerprint"]
    assert first["voice_asset_version"] == 1
    assert second["voice_asset_version"] == 2
    assert first["paid_model_calls"] == second["paid_model_calls"] == 0


@pytest.mark.parametrize("kind", [
    "unapproved_production", "no_consent", "wrong_series", "unreviewed_rights",
    "unapproved_script", "missing_shot", "too_long",
])
def test_voice_rights_and_scope_rejections_leave_no_wav(client, tmp_path, kind):
    series, production = make_production(client)
    if kind != "unapproved_production":
        assert client.post(f"/api/v1/productions/{production}/approve-script").status_code == 200
        assert client.post(f"/api/v1/productions/{production}/approve-characters").status_code == 200
    voice = _voice(client, series, consent="" if kind == "no_consent" else "owner-test-only")
    spec = _spec(series, production, voice)
    if kind == "wrong_series":
        extra = client.post("/api/v1/projects", json={
            "title": "Different series", "premise": "Keep actor identities isolated",
        }).json()["series_id"]
        spec = spec.model_copy(update={"series_id": extra})
    elif kind == "unreviewed_rights":
        spec = spec.model_copy(update={"operator_confirmed_voice_rights": False})
    elif kind == "unapproved_script":
        spec = spec.model_copy(update={"dialogue_text": "Private unapproved dialogue"})
    elif kind == "missing_shot":
        spec = spec.model_copy(update={"shot_id": "other-shot"})
    elif kind == "too_long":
        spec = spec.model_copy(update={"duration_seconds": 2})
    root = tmp_path / "no-audio"
    with pytest.raises(DialogueGenerationDenied):
        FakeDialogueAudioProvider().synthesize(client.app.state.db, spec, root)
    assert not root.exists()


def test_gemini_real_tts_cannot_be_accidentally_enabled_or_billed():
    with pytest.raises(DialogueGenerationDenied, match="not enabled|unavailable"):
        GeminiDialogueAudioProvider().synthesize("some fake spec")
    with pytest.raises(ValidationError):
        DialogueGenerationSpec(series_id="a", production_id="b", shot_id="s",
                               voice_asset_id="v", dialogue_text="", duration_seconds=0)


ffmpeg_only = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Dedicated offline-video CI explicitly runs this integration with FFmpeg",
)


@ffmpeg_only
def test_fake_voice_wav_feeds_actual_reviewed_mp4_mixer(client, tmp_path):
    from drama_factory.pipeline.offline_render import render_approved_preview, inspect_mp4
    series, production = _approved(client)
    voice = _voice(client, series)
    receipt = FakeDialogueAudioProvider().synthesize(
        client.app.state.db, _spec(series, production, voice),
        tmp_path / "fake-voice-asset",
    )
    result = render_approved_preview(
        client.app.state.db, production, tmp_path / "delivery",
        dialogue_audio=Path(receipt["local_wav_path"]),
        operator_confirmed_audio_rights=True,
    )
    assert result["offline_audio_mix"]["locally_supplied_dialogue"] is True
    assert result["technical_qa"]["technical_decode_passed"] is True
    assert result["spoken_dialogue_generated"] is False
    assert result["voice_license_independently_verified"] is False
    assert result["technical_qa"]["publish_approved"] is False
    assert result["paid_api_calls"] == receipt["paid_model_calls"] == 0
    assert inspect_mp4(Path(result["mp4_path"]), 2)["subtitle_codec"] == "mov_text"
