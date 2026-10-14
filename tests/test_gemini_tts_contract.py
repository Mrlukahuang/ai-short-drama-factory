"""PR-10e: official Gemini 3.8 unary TTS schema, actor approval and WAV decoding."""
from __future__ import annotations

import base64
import io
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from drama_factory.models import EpisodeDraft
from drama_factory.providers.dialogue_audio import (
    DialogueGenerationSpec, DialogueGenerationDenied,
)
from drama_factory.providers.gemini_tts_contract import (
    GeminiTtsContractDenied, GeminiTtsPreparation,
    prepare_gemini_tts_request, inspect_gemini_tts_unary_response,
)
from test_offline_cast_timeline import create_reviewed_cast


def _approved_spec(client, *, timed=True):
    run, voices, actors = create_reviewed_cast(
        client, explicit_timing=timed,
    )
    db = client.app.state.db
    row = db.one(
        """SELECT e.body_json,e.project_id FROM productions p
           JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""", (run,),
    )
    episode = EpisodeDraft.model_validate_json(row["body_json"])
    cue = episode.shots[0].dialogue_cues[0]
    spec = DialogueGenerationSpec(
        series_id=row["project_id"], production_id=run,
        shot_id=episode.shots[0].shot_id,
        cue_index=0, speaker_actor_id=cue.speaker_actor_id,
        voice_asset_id=voices[cue.speaker_actor_id],
        dialogue_text=f"{cue.speaker_actor_id}: {cue.text}",
        duration_seconds=1 if timed else 2,
        operator_confirmed_voice_rights=True,
    )
    return db, spec, voices, actors


def _fake_gemini_unary_wav(seconds=0.75, sample_rate=24000):
    target = io.BytesIO()
    with wave.open(target, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(b"\x00\x00" * int(seconds * sample_rate))
    return base64.b64encode(target.getvalue()).decode("ascii")


def test_official_gemini_38_tts_payload_from_exact_reviewed_cue(client):
    db, spec, _, _ = _approved_spec(client)
    plan = prepare_gemini_tts_request(
        db, spec, GeminiTtsPreparation(
            model_id="gemini-3.8-flash-lite-tts",
            prebuilt_voice="Kore",
            consent_reviewed_by_operator=True,
        ),
    )
    private = plan.private_sdk_kwargs()
    assert private["model"] == "gemini-3.8-flash-lite-tts"
    assert private["input"][0]["type"] == "user_input"
    assert private["input"][0]["content"][0]["type"] == "text"
    assert private["input"][0]["content"][0]["text"] == "Hello"
    assert private["input"][0]["content"][0]["annotations"][0]["type"] == "speech_metadata"
    assert private["response_format"] == {"type": "audio"}
    assert private["generation_config"] == {"speech_config": [{"voice": "Kore"}]}
    assert plan.approved_slot_seconds == 1
    receipt = plan.safe_receipt()
    assert receipt["submitted_to_provider"] is False
    assert receipt["paid_model_calls"] == 0
    assert receipt["vendor_hard_spend_cap_verified"] is False
    assert receipt["voice_consent_independently_verified"] is False
    assert receipt["publish_approved"] is False
    assert "Hello" not in str(receipt)
    assert "Hello" not in repr(plan)
    # No live or Fake SDK call occurs from the implementation; provider
    # payload remains an ephemeral structured handoff for a future adapter.
    private["input"][0]["content"][0]["text"] = "mutated"
    assert plan.private_sdk_kwargs()["input"][0]["content"][0]["text"] == "Hello"


@pytest.mark.parametrize("cause", [
    "missing_review", "missing_explicit_voice_rights", "wrong_voice",
    "legacy_untimed", "missing_speaker", "wrong_cue_ordinal",
])
def test_gemini_tts_plan_rejects_wrong_rights_or_legacy_actor_guess(client, cause):
    db, spec, mapping, actors = _approved_spec(
        client, timed=(cause != "legacy_untimed"),
    )
    review = True
    if cause == "missing_review":
        review = False
    elif cause == "missing_explicit_voice_rights":
        spec = spec.model_copy(update={"operator_confirmed_voice_rights": False})
    elif cause == "wrong_voice":
        spec = spec.model_copy(update={"voice_asset_id": mapping[actors[1]]})
    elif cause == "missing_speaker":
        spec = spec.model_copy(update={"speaker_actor_id": None})
    elif cause == "wrong_cue_ordinal":
        spec = spec.model_copy(update={"cue_index": 4})
    with pytest.raises((GeminiTtsContractDenied, DialogueGenerationDenied)):
        prepare_gemini_tts_request(
            db, spec, GeminiTtsPreparation(
                consent_reviewed_by_operator=review,
            ),
        )


def test_no_unrecognized_model_voice_or_unbounded_spend_is_accepted(client):
    db, spec, _, _ = _approved_spec(client)
    for values in (
        {"model_id": "gemini-other-test", "consent_reviewed_by_operator": True},
        {"prebuilt_voice": "voicekey_someone-else", "consent_reviewed_by_operator": True},
    ):
        with pytest.raises(GeminiTtsContractDenied):
            prepare_gemini_tts_request(db, spec, GeminiTtsPreparation(**values))
    for amount in ("0", "2.01", "-1"):
        with pytest.raises(ValidationError):
            GeminiTtsPreparation(max_acknowledged_spend_usd=amount)
    assert plan_receipt_never_permits_live_call(db, spec)


def plan_receipt_never_permits_live_call(db, spec):
    plan = prepare_gemini_tts_request(
        db, spec, GeminiTtsPreparation(consent_reviewed_by_operator=True),
    )
    return plan.safe_receipt()["live_cutover_permitted"] is False


def test_unary_wav_response_correctly_parsed_and_fails_closed_on_malformed_audio():
    report = inspect_gemini_tts_unary_response(_fake_gemini_unary_wav(), 1)
    assert 0.74 <= report.duration_seconds <= 0.76
    assert len(report.wav_bytes) > 1000
    assert report.safe_receipt()["spoken_dialogue_human_verified"] is False
    assert report.safe_receipt()["publish_approved"] is False
    assert "wav_bytes" not in repr(report)
    for bad in ("!!!notbase64", "", base64.b64encode(b"not a wav").decode()):
        with pytest.raises(GeminiTtsContractDenied):
            inspect_gemini_tts_unary_response(bad, 1)
    for b64 in (_fake_gemini_unary_wav(2.0), _fake_gemini_unary_wav(1.0, 8000)):
        with pytest.raises(GeminiTtsContractDenied):
            inspect_gemini_tts_unary_response(b64, 1)
