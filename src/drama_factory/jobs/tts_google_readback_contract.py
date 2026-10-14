"""PR-10n: offline contract for Google Interactions GET of an ORIGINAL TTS ID.

This module deliberately does NOT import google-genai, create credentials,
send HTTP, write SQLite or accept a caller-supplied SDK. Only an exact-class
Fake implements the public GET signature. It is NOT a live recovery worker.
The real provider requires origin-project/auth provenance and live evidence.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field

from drama_factory.db import Database
from drama_factory.jobs.tts_fake_dispatch import _fake_pcm_wav
from drama_factory.jobs.tts_recovery_readonly import (
    TtsRecoveryDenied, _classify_tts_snapshot,
)
from drama_factory.providers.gemini_tts_contract import (
    inspect_gemini_tts_unary_response,
)


class OriginalTtsReadbackDenied(ValueError):
    """Fixed, redacted failures: never echo IDs, SDK exceptions or text."""


@dataclass(frozen=True)
class _FakeAudio:
    data: str = field(repr=False)
    mime_type: str = "audio/wav"


@dataclass(frozen=True)
class _FakeInteraction:
    id: str = field(repr=False)
    output_audio: _FakeAudio | None = field(default=None, repr=False)


@dataclass
class OfflineFakeGoogleInteractionsGetter:
    """An exact Fake for client.interactions.get(id=..., ...), NEVER create.

    All error modes are simulated without I/O; the object may be used once.
    The original interaction ID is private in repr and never returned.
    """

    original_interaction_id: str = field(repr=False)
    project_ref_sha256: str = field(repr=False)
    principal_ref_sha256: str = field(repr=False)
    fault: str | None = None
    get_calls: int = 0
    _audio_base64: str | None = field(default=None, repr=False)

    def get(self, *, id: str, include_input: bool = False,
            stream: bool = False) -> _FakeInteraction:
        self.get_calls += 1
        if include_input is not False or stream is not False:
            raise RuntimeError("Unsafe readback parameters")
        if self.fault in ("timeout", "permission", "expired"):
            raise RuntimeError("PRIVATE fake provider failure")
        if id != self.original_interaction_id:
            raise RuntimeError("Original fake interaction mismatch")
        if self.fault == "wrong_id":
            return _FakeInteraction("unrelated-interaction", _FakeAudio(_fake_pcm_wav()))
        if self.fault == "missing_audio":
            return _FakeInteraction(id, None)
        audio = self._audio_base64 or _fake_pcm_wav()
        if self.fault == "corrupt_audio":
            audio = base64.b64encode(b"private invalid wav").decode("ascii")
        if self.fault == "wrong_mime":
            return _FakeInteraction(id, _FakeAudio(audio, "audio/mpeg"))
        return _FakeInteraction(id, _FakeAudio(audio))


def _snapshot(db: Database, task_id: str):
    """Audit task, hold and original Google scope in ONE read transaction."""
    with db.connection() as conn:
        conn.execute("BEGIN")
        row = conn.execute(
            """SELECT t.id,t.provider,t.status,t.interaction_id,
                      t.output_sha256,t.output_duration_seconds,
                      t.approved_slot_seconds,b.status AS budget_status,
                      b.actual_usd,b.evidence_reference,b.reviewed_by
               FROM tts_tasks t
               LEFT JOIN tts_budget_reservations b ON b.task_id=t.id
               WHERE t.id=?""", (task_id,),
        ).fetchone()
        if row is None:
            raise OriginalTtsReadbackDenied("TTS readback task unavailable")
        events = conn.execute(
            """SELECT action,previous_state,next_state
               FROM tts_task_events WHERE task_id=? ORDER BY rowid""",
            (task_id,),
        ).fetchall()
        try:
            summary = _classify_tts_snapshot(row, events)
        except (TtsRecoveryDenied, ValueError, TypeError):
            raise OriginalTtsReadbackDenied("Durable TTS recovery audit invalid") from None
        if (
            row["status"] != "acknowledged"
            or row["provider"] != "google"
            or not row["interaction_id"]
            or row["budget_status"] not in ("held", "reconciled")
            or summary["recovery_class"] != "recover_existing_interaction_audio_only"
        ):
            raise OriginalTtsReadbackDenied("Original acknowledged TTS GET required")
        scope = conn.execute(
            """SELECT project_ref_sha256,principal_ref_sha256,source
               FROM tts_google_origin_scopes WHERE task_id=?""",
            (task_id,),
        ).fetchone()
        if (
            scope is None or scope["source"] != "offline_unverified"
            or not re.fullmatch(r"[0-9a-f]{64}", scope["project_ref_sha256"])
            or not re.fullmatch(r"[0-9a-f]{64}", scope["principal_ref_sha256"])
            or scope["project_ref_sha256"] == scope["principal_ref_sha256"]
        ):
            raise OriginalTtsReadbackDenied("Original Google scope registration absent or invalid")
        return (
            row["interaction_id"], row["approved_slot_seconds"],
            row["status"], row["budget_status"], len(events),
            scope["project_ref_sha256"], scope["principal_ref_sha256"],
        )


def inspect_offline_original_google_tts_get(
    db: Database, task_id: str, getter: OfflineFakeGoogleInteractionsGetter,
) -> dict:
    """One simulated GET, inspect original WAV and leave all ledgers untouched.

    A successful inspection is NOT a durable 'verified' transition. Callers
    cannot route an arbitrary SDK/client/duck type through this test-only API.
    """
    if type(getter) is not OfflineFakeGoogleInteractionsGetter:
        raise OriginalTtsReadbackDenied("Only exact offline Google GET Fake permitted")
    if getter.get_calls != 0 or getter.fault not in (
        None, "timeout", "permission", "expired", "wrong_id",
        "missing_audio", "corrupt_audio", "wrong_mime",
    ):
        raise OriginalTtsReadbackDenied("Original GET Fake must be unused")
    if type(task_id) is not str or not re.fullmatch(r"ttstask_[a-f0-9]{14}", task_id):
        raise OriginalTtsReadbackDenied("Invalid opaque TTS task identifier")

    original_id, slot, status, budget, events, project, principal = _snapshot(db, task_id)
    if original_id != getter.original_interaction_id:
        raise OriginalTtsReadbackDenied("Original ID differs from durable task")
    if (
        project != getter.project_ref_sha256
        or principal != getter.principal_ref_sha256
    ):
        raise OriginalTtsReadbackDenied("Original Google origin context mismatch")
    try:
        response = getter.get(id=original_id, include_input=False, stream=False)
        if (
            type(response) is not _FakeInteraction
            or response.id != original_id
            or type(response.output_audio) is not _FakeAudio
            or response.output_audio.mime_type not in ("audio/wav", "audio/x-wav")
        ):
            raise OriginalTtsReadbackDenied("Original interaction audio receipt invalid")
        inspected = inspect_gemini_tts_unary_response(response.output_audio.data, slot)
        # An identical WAV from another already verified cue is suspicious:
        # the operator must check provider billing/identity, never autopublish.
        duplicate = db.one(
            """SELECT id FROM tts_tasks
               WHERE provider='google' AND id<>? AND output_sha256=?
               LIMIT 1""", (task_id, inspected.sha256),
        )
        if duplicate is not None:
            raise OriginalTtsReadbackDenied("Audio receipt already used by another cue")
        if _snapshot(db, task_id) != (
            original_id, slot, status, budget, events, project, principal,
        ):
            raise OriginalTtsReadbackDenied("Durable TTS state changed during GET")
    except Exception:
        raise OriginalTtsReadbackDenied(
            "Existing provider GET unverified; no generation or automatic retry"
        ) from None
    return {
        "kind": "offline_original_google_interaction_get_inspected",
        "original_interaction_id_matches_durable_record": True,
        "offline_google_origin_scopes_match": True,
        "offline_scope_is_provider_authenticated": False,
        "wav_sha256": inspected.sha256,
        "duration_seconds": round(inspected.duration_seconds, 6),
        "original_get_attempts": getter.get_calls,
        "database_updates": 0,
        "new_generation_requests": 0,
        "paid_provider_calls": 0,
        "real_google_get_executed": False,
        "origin_google_project_and_permissions_verified": False,
        "vendor_invoice_verified": False,
        "voice_consent_verified": False,
        "durable_verification_written": False,
        "automated_retry_allowed": False,
        "publish_approved": False,
        "production_cutover_allowed": False,
    }
