"""PR-10i: OFFLINE Fake-only durable TTS dispatch/finalization rehearsal.

This module never imports a Google SDK, opens a socket or accepts an arbitrary
client. Its exact-class Fake transport proves the ordering: reviewed cue ->
durable held budget -> durable paid intent -> ONE synthetic call -> unique
interaction ID -> actual PCM format validation -> immutable ledger receipt.

Errors after the committed intent may have been billed in a real adapter:
never retry or release held money. This is NOT a paid-worker implementation.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import wave
from dataclasses import dataclass, field
from decimal import Decimal

from drama_factory.db import Database
from drama_factory.jobs.tts_intents import (
    TtsLedgerDenied, acknowledge_tts_provider_interaction,
    commit_tts_submission_intent, prepare_tts_task,
    quarantine_tts_unknown_ack, record_offline_verified_tts_wav,
)
from drama_factory.providers.dialogue_audio import DialogueGenerationSpec
from drama_factory.providers.gemini_tts_contract import (
    GeminiTtsPreparation, inspect_gemini_tts_unary_response,
    prepare_gemini_tts_request,
)


class OfflineTtsDispatchDenied(ValueError):
    """Only fixed redacted error strings, no dialogue/credential leakage."""


@dataclass
class OfflineFakeGeminiTransport:
    """Exact-class fake with no HTTP, SDK or arbitrary callback capability.

    fail_mode: None, 'ack_lost', 'invalid_wav', 'bad_interaction_id' or
    'duplicate_interaction_id'. All modes count one simulated submission.
    """
    fail_mode: str | None = None
    simulated_interaction_id: str = "synthetic-fake-interaction"
    calls: int = 0
    seen_request_fingerprint: str | None = None
    _last_private_payload: dict | None = field(default=None, repr=False)

    def submit_one(self, payload: dict) -> tuple[str, str]:
        """Return (synthetic interaction ID, base64 WAV), never a paid call."""
        self.calls += 1
        self.seen_request_fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self.fail_mode == "ack_lost":
            raise RuntimeError("synthetic API timeout with private dialogue")
        if self.fail_mode == "invalid_wav":
            return self.simulated_interaction_id, base64.b64encode(b"bad-pcm").decode()
        if self.fail_mode == "bad_interaction_id":
            return "bad ID with spaces", _fake_pcm_wav()
        return self.simulated_interaction_id, _fake_pcm_wav()


def _fake_pcm_wav() -> str:
    out = io.BytesIO()
    with wave.open(out, "wb") as pcm:
        pcm.setnchannels(1)
        pcm.setsampwidth(2)
        pcm.setframerate(24000)
        pcm.writeframes(b"\x00\x00" * 12000)
    return base64.b64encode(out.getvalue()).decode("ascii")


def _quarantine_only_unacknowledged(db: Database, task_id: str) -> None:
    # If provider receipt was already persisted, do not corrupt acknowledged
    # state. This is for external investigator, never automatic resubmission.
    row = db.one("SELECT status FROM tts_tasks WHERE id=?", (task_id,))
    if row is not None and row["status"] == "submission_intent":
        quarantine_tts_unknown_ack(db, task_id)


def execute_offline_fake_tts_once(
    db: Database,
    task_id: str,
    spec: DialogueGenerationSpec,
    control: GeminiTtsPreparation,
    transport: OfflineFakeGeminiTransport,
) -> dict:
    """Actually exercise existing durable transitions with a fake transport.

    Every call needs current approved spec, voice, review and immutable task
    fingerprint; only untouched PREPARED task and held same-day budget can
    proceed. All providers other than the exact local Fake type are rejected
    before any task state mutation. No possible live provider dispatch path.
    """
    if type(transport) is not OfflineFakeGeminiTransport:
        raise OfflineTtsDispatchDenied("Only exact offline Fake TTS transport is allowed")
    if transport.calls != 0 or transport.fail_mode not in (
        None, "ack_lost", "invalid_wav", "bad_interaction_id",
        "duplicate_interaction_id",
    ):
        raise OfflineTtsDispatchDenied("Fake transport must be fresh and supported")
    plan = prepare_gemini_tts_request(db, spec, control)
    task = db.one("SELECT * FROM tts_tasks WHERE id=?", (task_id,))
    hold = db.one("SELECT status FROM tts_budget_reservations WHERE task_id=?", (task_id,))
    if (
        task is None or hold is None
        or hold["status"] != "held"
        or task["status"] != "prepared"
        or task["production_id"] != spec.production_id
        or task["series_id"] != spec.series_id
        or task["shot_id"] != spec.shot_id
        or task["cue_index"] != spec.cue_index
        or task["request_sha256"] != plan.fingerprint
        or task["model_id"] != plan.model_id
        or task["voice_name"] != plan.voice_name
        or Decimal(task["max_acknowledged_spend_usd"]) != plan.max_acknowledged_spend_usd
        or task["approved_slot_seconds"] != plan.approved_slot_seconds
    ):
        raise OfflineTtsDispatchDenied("Current immutable reviewed TTS task and hold required")
    # Existing BEGIN IMMEDIATE CAS guarantees exactly one caller can commit.
    # Any second concurrent worker is rejected BEFORE invoking submit_one.
    try:
        commit_tts_submission_intent(db, task_id)
    except TtsLedgerDenied:
        raise OfflineTtsDispatchDenied("TTS one-use intent already consumed or unavailable") from None

    try:
        # This line is the sole simulated submission. No retry loop exists.
        interaction_id, output_base64 = transport.submit_one(plan.private_sdk_kwargs())
        acknowledge_tts_provider_interaction(db, task_id, interaction_id)
    except Exception:
        # Unknown ACK, invalid interaction ID or duplicate ID: preserve hold
        # and quarantine. A real vendor might already have charged.
        _quarantine_only_unacknowledged(db, task_id)
        raise OfflineTtsDispatchDenied(
            "Synthetic request outcome ambiguous; hold retained, no retry"
        ) from None

    try:
        inspected = inspect_gemini_tts_unary_response(
            output_base64, plan.approved_slot_seconds,
        )
        verified = record_offline_verified_tts_wav(db, task_id, inspected)
    except Exception:
        # The unique interaction is already durably bound. Do not rewind to
        # prepared or release budget, even for invalid/oversize WAV bytes.
        raise OfflineTtsDispatchDenied(
            "Synthetic interaction recorded but WAV invalid; no retry"
        ) from None

    return {
        "kind": "offline_fake_gemini_tts_once",
        "task_status": verified["status"],
        "provider_interaction_recorded": verified["provider_interaction_recorded"],
        "wav_receipt_recorded": verified["wav_receipt_recorded"],
        "wav_sha256": inspected.sha256,
        "simulated_request_attempts": transport.calls,
        "actual_paid_provider_calls": 0,
        "vendor_billing_verified": False,
        "vendor_hard_spend_cap_verified": False,
        "voice_consent_independently_verified": False,
        "operator_review_required": True,
        "publish_approved": False,
        "automated_retry_allowed": False,
        "production_backend_switched": False,
    }
