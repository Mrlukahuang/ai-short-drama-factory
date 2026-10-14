"""PR-10e: OFFLINE-only contract for Gemini 3.8 single-turn TTS.

Google Interactions schema verified against official speech-generation docs:
https://ai.google.dev/gemini-api/docs/speech-generation (2026-10-14).

This module has no network client, no Google import and no method that can
submit a paid request. It prepares an ephemeral, PRIVATE request and checks
a supplied unary WAV response. Real dispatch needs a separate ledger-backed
paid adapter and fresh bounded execution evidence. Never log request payload.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import wave
from dataclasses import dataclass, field
from decimal import Decimal

from pydantic import BaseModel, Field

from drama_factory.db import Database
from drama_factory.models import EpisodeDraft
from drama_factory.providers.dialogue_audio import (
    DialogueGenerationDenied, DialogueGenerationSpec, _spec_fingerprint,
)


_TTS_MODELS = frozenset({
    "gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts",
})
# Restrict dry-run to two documented prebuilt voices until a separately
# checked voice library and licensing scope are wired into Series assets.
_PREBUILT_VOICES = frozenset({"Kore", "Puck"})
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_UNARY_WAV_SAMPLE_RATE = 24000


class GeminiTtsContractDenied(ValueError):
    """All errors are fixed messages; never include reviewed dialogue."""


class GeminiTtsPreparation(BaseModel):
    model_id: str = "gemini-3.8-flash-lite-tts"
    prebuilt_voice: str = "Kore"
    max_acknowledged_spend_usd: Decimal = Field(
        default=Decimal("0.02"), gt=Decimal("0"), le=Decimal("2.00"),
    )
    consent_reviewed_by_operator: bool = False


@dataclass(frozen=True)
class PreparedGeminiSpeech:
    """Private bytes of a request are excluded from repr and safe_receipt."""
    fingerprint: str
    model_id: str
    voice_name: str
    approved_slot_seconds: int
    max_acknowledged_spend_usd: Decimal
    _private_sdk_kwargs: dict = field(repr=False)

    def private_sdk_kwargs(self) -> dict:
        """Only caller explicitly preparing a request can access the text."""
        import copy
        return copy.deepcopy(self._private_sdk_kwargs)

    def safe_receipt(self) -> dict:
        return {
            "kind": "gemini_tts_prepared_not_submitted",
            "model": self.model_id,
            "prebuilt_voice": self.voice_name,
            "fingerprint": self.fingerprint,
            "approved_slot_seconds": self.approved_slot_seconds,
            "maximum_spend_acknowledgment_usd": str(self.max_acknowledged_spend_usd),
            "vendor_hard_spend_cap_verified": False,
            "voice_consent_independently_verified": False,
            "spoken_dialogue_generated": False,
            "submitted_to_provider": False,
            "paid_model_calls": 0,
            "operator_review_required": True,
            "publish_approved": False,
            "live_cutover_permitted": False,
        }


def prepare_gemini_tts_request(
    db: Database, spec: DialogueGenerationSpec,
    control: GeminiTtsPreparation,
) -> PreparedGeminiSpeech:
    """Validate only operator-approved, actor-assigned *structured* cues.

    Unlike the Fake legacy path, TTS cannot guess a voice from a plain
    string of the form 'actor: text'. Neither prebuilt voices nor an
    operator assertion independently prove commercial rights.
    """
    if control.model_id not in _TTS_MODELS or control.prebuilt_voice not in _PREBUILT_VOICES:
        raise GeminiTtsContractDenied("Unsupported or unreviewed TTS model/voice")
    if control.consent_reviewed_by_operator is not True:
        raise GeminiTtsContractDenied("Explicit TTS consent review required")
    if spec.cue_index is None or spec.speaker_actor_id is None:
        raise GeminiTtsContractDenied("Reviewed structured speaker cue required")
    # Inherit exact same-series approved actor -> voice assignment,
    # latest version, source consent reference and text equality checks.
    fingerprint, voice_version = _spec_fingerprint(db, spec)
    row = db.one(
        """SELECT e.body_json FROM productions p
           JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
        (spec.production_id,),
    )
    if row is None:
        raise GeminiTtsContractDenied("Approved episode no longer available")
    episode = EpisodeDraft.model_validate_json(row["body_json"])
    shot = next((s for s in episode.shots if s.shot_id == spec.shot_id), None)
    if shot is None or spec.cue_index >= len(shot.dialogue_cues):
        raise GeminiTtsContractDenied("Reviewed TTS cue no longer available")
    cue = shot.dialogue_cues[spec.cue_index]
    text = cue.text
    if cue.start_second is None or cue.end_second is None:
        raise GeminiTtsContractDenied("Director-reviewed cue time bounds required")
    if spec.duration_seconds != cue.end_second - cue.start_second:
        raise GeminiTtsContractDenied("TTS approval duration conflicts with cue slot")

    payload = {
        "model": control.model_id,
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{"type": "speech_metadata"}],
            }],
        }],
        "response_format": {"type": "audio"},
        "generation_config": {
            "speech_config": [{"voice": control.prebuilt_voice}],
        },
    }
    key = hashlib.sha256(json.dumps({
        "spec_key": fingerprint,
        "voice_version": voice_version,
        "model_id": control.model_id,
        "prebuilt_voice": control.prebuilt_voice,
        "slot_start": cue.start_second,
        "slot_end": cue.end_second,
        "request_schema": "gemini-interactions-tts-v1",
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PreparedGeminiSpeech(
        fingerprint=key,
        model_id=control.model_id,
        voice_name=control.prebuilt_voice,
        approved_slot_seconds=spec.duration_seconds,
        max_acknowledged_spend_usd=control.max_acknowledged_spend_usd,
        _private_sdk_kwargs=payload,
    )


@dataclass(frozen=True)
class InspectedGeminiSpeech:
    """Locally verified candidate audio; unapproved for final mix/publication."""
    wav_bytes: bytes = field(repr=False)
    sha256: str
    duration_seconds: float

    def safe_receipt(self) -> dict:
        return {
            "kind": "gemini_tts_unary_wav_validated_offline",
            "sha256": self.sha256,
            "duration_seconds": round(self.duration_seconds, 3),
            "spoken_dialogue_human_verified": False,
            "voice_license_independently_verified": False,
            "operator_review_required": True,
            "publish_approved": False,
        }


def inspect_gemini_tts_unary_response(
    output_audio_base64: str, approved_slot_seconds: int,
) -> InspectedGeminiSpeech:
    """Validate official unary output_audio.data base64 WAV, never submit.

    The API nominally emits mono 24 kHz 16-bit PCM WAV; reject all other
    codecs, empty/too-long audio or corrupted RIFF. External invoices,
    semantic correctness and voice rights are not established by RIFF.
    """
    if type(output_audio_base64) is not str or type(approved_slot_seconds) is not int:
        raise GeminiTtsContractDenied("Invalid TTS response contract")
    if not 1 <= approved_slot_seconds <= 30 or len(output_audio_base64) > 11 * 1024 * 1024:
        raise GeminiTtsContractDenied("TTS response outside bounded scope")
    try:
        contents = base64.b64decode(output_audio_base64, validate=True)
        if not 44 <= len(contents) <= _MAX_RESPONSE_BYTES:
            raise GeminiTtsContractDenied("Invalid TTS WAV byte length")
        with wave.open(io.BytesIO(contents), "rb") as audio:
            if (
                audio.getnchannels() != 1 or audio.getsampwidth() != 2
                or audio.getframerate() != _UNARY_WAV_SAMPLE_RATE
                or audio.getcomptype() != "NONE"
            ):
                raise GeminiTtsContractDenied("Unexpected TTS WAV format")
            seconds = audio.getnframes() / audio.getframerate()
            if not (0.1 <= seconds <= approved_slot_seconds + 0.25):
                raise GeminiTtsContractDenied("TTS WAV exceeds reviewed slot duration")
            if len(audio.readframes(audio.getnframes())) != audio.getnframes() * 2:
                raise GeminiTtsContractDenied("Incomplete TTS WAV audio frames")
    except GeminiTtsContractDenied:
        raise
    except (binascii.Error, ValueError, OSError, EOFError, wave.Error):
        raise GeminiTtsContractDenied("TTS WAV response is malformed") from None
    return InspectedGeminiSpeech(
        wav_bytes=contents,
        sha256=hashlib.sha256(contents).hexdigest(),
        duration_seconds=seconds,
    )
