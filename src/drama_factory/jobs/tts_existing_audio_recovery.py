"""PR-10k: existing-interaction WAV recovery rehearsal, strictly OFFLINE Fake.

After an original provider interaction ID has been durably acknowledged but
before WAV metadata is stored, only the SAME interaction's existing bytes
may be inspected. There is no "create" or paid dispatch API in this file.
The exact-class Fake read adapter prevents accidental network SDK injection.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

from drama_factory.db import Database
from drama_factory.jobs.tts_intents import (
    TtsLedgerDenied, record_offline_verified_tts_wav,
)
from drama_factory.providers.gemini_tts_contract import (
    GeminiTtsContractDenied, inspect_gemini_tts_unary_response,
)
from drama_factory.jobs.tts_fake_dispatch import _fake_pcm_wav


class OfflineExistingAudioDenied(ValueError):
    """Never include requested provider IDs, model body or private metadata."""


@dataclass
class OfflineFakeExistingAudioReader:
    """Exact local Fake-only readback; no Google SDK import and no write API."""
    existing_interaction_id: str
    fault: str | None = None
    read_calls: int = 0
    _private_audio_base64: str | None = field(default=None, repr=False)

    def read_existing(self, interaction_id: str) -> tuple[str, str]:
        self.read_calls += 1
        if self.fault == "timeout":
            raise RuntimeError("SECRET private network response from fake")
        if self.fault == "wrong_id":
            return "synthetic-wrong-id", _fake_pcm_wav()
        if interaction_id != self.existing_interaction_id:
            raise RuntimeError("Provider interaction mismatch")
        if self.fault == "corrupt_audio":
            return interaction_id, base64.b64encode(b"broken wav").decode("ascii")
        return interaction_id, self._private_audio_base64 or _fake_pcm_wav()


def recover_offline_existing_tts_wav(
    db: Database, task_id: str, reader: OfflineFakeExistingAudioReader,
) -> dict:
    """Read ONLY existing Fake Interaction; reverify output and durable hash.

    No generation, retry or release path. Fail closed if provider identity,
    state, format or original receipt fails, without touching the old hold.
    """
    if type(reader) is not OfflineFakeExistingAudioReader:
        raise OfflineExistingAudioDenied("Only exact local Fake read adapter is allowed")
    if reader.read_calls != 0 or reader.fault not in (
        None, "timeout", "wrong_id", "corrupt_audio",
    ):
        raise OfflineExistingAudioDenied("Existing-interaction reader is already used")
    if type(task_id) is not str or not re.fullmatch(r"ttstask_[a-f0-9]{14}", task_id):
        raise OfflineExistingAudioDenied("Invalid opaque TTS task ID")
    row = db.one(
        """SELECT t.status,t.interaction_id,t.approved_slot_seconds,
                  b.status AS reservation_status
           FROM tts_tasks t
           LEFT JOIN tts_budget_reservations b ON b.task_id=t.id
           WHERE t.id=?""",
        (task_id,),
    )
    if (
        row is None or row["status"] != "acknowledged"
        or not row["interaction_id"]
        or row["reservation_status"] not in ("held", "reconciled")
        or row["interaction_id"] != reader.existing_interaction_id
    ):
        raise OfflineExistingAudioDenied("Single acknowledged existing TTS interaction required")
    try:
        original_id, b64 = reader.read_existing(row["interaction_id"])
        if original_id != row["interaction_id"]:
            raise OfflineExistingAudioDenied("Existing interaction identity mismatch")
        inspected = inspect_gemini_tts_unary_response(
            b64, row["approved_slot_seconds"],
        )
        receipt = record_offline_verified_tts_wav(db, task_id, inspected)
    except Exception:
        # No second retrieval with the same fake instance, and NEVER any
        # additional model submission. Task/hold retain the original status.
        raise OfflineExistingAudioDenied(
            "Existing original WAV recovery was not verified; no resubmission"
        ) from None
    return {
        "kind": "offline_existing_interaction_audio_recovered",
        "task_status": receipt["status"],
        "wav_sha256": inspected.sha256,
        "provider_interaction_recorded": receipt["provider_interaction_recorded"],
        "wav_receipt_recorded": receipt["wav_receipt_recorded"],
        "existing_interaction_reads": reader.read_calls,
        "new_tts_generation_attempts": 0,
        "actual_paid_provider_calls": 0,
        "vendor_invoice_independently_verified": False,
        "voice_consent_independently_verified": False,
        "automated_retry_allowed": False,
        "publish_approved": False,
        "production_cutover_allowed": False,
    }
