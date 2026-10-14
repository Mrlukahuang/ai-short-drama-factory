"""PR-10j: TTS post-crash read-only snapshot and recovery classification.

This is an OBSERVER: it never submits, polls, mutates, releases a held budget
or authorizes production. Snapshot uses one local SQLite read transaction.
No IDs, voice names, dialogue, vendor raw receipts, paths or invoice content
appear in its returned result. Corrupt/incomplete state fails closed.
"""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal, InvalidOperation

from drama_factory.db import Database


class TtsRecoveryDenied(ValueError):
    """Error text must never embed a private provider or story record."""


_EXPECTED = {
    "prepared": {"prepared_offline": 1, "paid_intent_committed": 0,
                 "interaction_id_recorded": 0, "unknown_ack_quarantined": 0,
                 "format_verified_not_speech_reviewed": 0},
    "submission_intent": {"prepared_offline": 1, "paid_intent_committed": 1,
                          "interaction_id_recorded": 0, "unknown_ack_quarantined": 0,
                          "format_verified_not_speech_reviewed": 0},
    "quarantined": {"prepared_offline": 1, "paid_intent_committed": 1,
                    "interaction_id_recorded": 0, "unknown_ack_quarantined": 1,
                    "format_verified_not_speech_reviewed": 0},
    "acknowledged": {"prepared_offline": 1, "paid_intent_committed": 1,
                     "interaction_id_recorded": 1, "unknown_ack_quarantined": 0,
                     "format_verified_not_speech_reviewed": 0},
    "verified": {"prepared_offline": 1, "paid_intent_committed": 1,
                 "interaction_id_recorded": 1, "unknown_ack_quarantined": 0,
                 "format_verified_not_speech_reviewed": 1},
}

_RECOVERY = {
    "submission_intent": "unknown_provider_outcome_check_existing_request_only",
    "quarantined": "invoice_or_provider_support_review_no_retry",
    "acknowledged": "recover_existing_interaction_audio_only",
    "verified": "review_existing_wav_and_vendor_invoice_only",
}


def inspect_tts_recovery(db: Database, task_id: str) -> dict:
    """Fail closed on missing/forged audit, inconsistent state or budget.

    A successful read is NOT a command to transition state. Even prepared
    tasks aren't newly authorized for paid Google submission by this query.
    """
    if type(task_id) is not str or not re.fullmatch(r"ttstask_[a-f0-9]{14}", task_id):
        raise TtsRecoveryDenied("Invalid opaque TTS task identifier")
    with db.connection() as conn:
        conn.execute("BEGIN")
        row = conn.execute(
            """SELECT t.status,t.interaction_id,t.output_sha256,
                      t.output_duration_seconds,t.approved_slot_seconds,
                      b.status AS budget_status,b.actual_usd,
                      b.evidence_reference,b.reviewed_by
               FROM tts_tasks t
               LEFT JOIN tts_budget_reservations b ON b.task_id=t.id
               WHERE t.id=?""",
            (task_id,),
        ).fetchone()
        if row is None:
            raise TtsRecoveryDenied("Local TTS task absent")
        events = conn.execute(
            """SELECT action,previous_state,next_state
               FROM tts_task_events WHERE task_id=? ORDER BY rowid""",
            (task_id,),
        ).fetchall()

    return _classify_tts_snapshot(row, events)


def _classify_tts_snapshot(row, events) -> dict:
    """Validate a task and its append-only audit from ONE pinned snapshot."""
    status = row["status"]
    expected = _EXPECTED.get(status)
    if expected is None:
        raise TtsRecoveryDenied("Unknown durable TTS state")
    count = Counter(e["action"] for e in events)
    if any(count.get(name, 0) != required for name, required in expected.items()):
        raise TtsRecoveryDenied("TTS state and immutable audit are inconsistent")
    known = set(next(iter(_EXPECTED.values()))) | {
        "budget_held", "operator_entered_vendor_charge",
    }
    if set(count) - known or count["budget_held"] > 1 or count["operator_entered_vendor_charge"] > 1:
        raise TtsRecoveryDenied("Unexpected or duplicated TTS audit events")

    budget = row["budget_status"]
    if (budget is None) != (count["budget_held"] == 0):
        raise TtsRecoveryDenied("TTS reservation audit mismatch")
    if budget is not None and budget not in ("held", "reconciled"):
        raise TtsRecoveryDenied("Unsafe TTS budget reservation state")
    if status != "prepared" and budget is None:
        raise TtsRecoveryDenied("Committed TTS submission lacks a durable budget hold")
    if budget == "reconciled":
        if (
            count["operator_entered_vendor_charge"] != 1
            or row["actual_usd"] is None
            or not row["evidence_reference"]
            or not row["reviewed_by"]
        ):
            raise TtsRecoveryDenied("Vendor charge entry lacks documented human review")
        try:
            if not Decimal(row["actual_usd"]).is_finite() or Decimal(row["actual_usd"]) < 0:
                raise TtsRecoveryDenied("Invalid recorded TTS charge amount")
        except (InvalidOperation, ValueError, TypeError):
            raise TtsRecoveryDenied("Invalid recorded TTS charge amount") from None
    elif count["operator_entered_vendor_charge"]:
        raise TtsRecoveryDenied("TTS charge event has no reconciled reservation")

    interaction = row["interaction_id"]
    has_interaction = interaction is not None
    has_audio = row["output_sha256"] is not None
    if has_interaction != (status in ("acknowledged", "verified")):
        raise TtsRecoveryDenied("Recorded provider interaction contradicts TTS state")
    if has_audio != (status == "verified"):
        raise TtsRecoveryDenied("Recorded WAV hash contradicts TTS state")
    if has_audio:
        if (
            not re.fullmatch(r"[0-9a-f]{64}", row["output_sha256"])
            or row["output_duration_seconds"] is None
        ):
            raise TtsRecoveryDenied("Verified WAV receipt malformed")
        try:
            length = Decimal(row["output_duration_seconds"])
            if not length.is_finite() or not (
                Decimal("0") < length <= Decimal(row["approved_slot_seconds"]) + Decimal("0.25")
            ):
                raise TtsRecoveryDenied("Verified WAV duration outside approved slot")
        except (InvalidOperation, ValueError, TypeError):
            raise TtsRecoveryDenied("Verified WAV duration outside approved slot") from None
    elif row["output_duration_seconds"] is not None:
        raise TtsRecoveryDenied("Unverified task contains unexpected WAV metadata")

    # Check every observed transition in durable order rather than trusting
    # status strings supplied by a caller. Billing review is state-preserving.
    previous = None
    for event in events:
        if event["previous_state"] != previous:
            raise TtsRecoveryDenied("TTS event transition chain is inconsistent")
        if event["action"] == "prepared_offline":
            destination = "prepared"
        elif event["action"] == "budget_held":
            destination = "prepared"
        elif event["action"] == "paid_intent_committed":
            destination = "submission_intent"
        elif event["action"] == "interaction_id_recorded":
            destination = "acknowledged"
        elif event["action"] == "unknown_ack_quarantined":
            destination = "quarantined"
        elif event["action"] == "format_verified_not_speech_reviewed":
            destination = "verified"
        else:  # Human entered vendor evidence does not change task status
            destination = previous
        if event["next_state"] != destination:
            raise TtsRecoveryDenied("TTS event transition chain is inconsistent")
        previous = destination
    if previous != status:
        raise TtsRecoveryDenied("Last recorded TTS event does not match durable task")

    return {
        "kind": "offline_tts_recovery_readonly",
        "task_status": status,
        "recovery_class": (
            "prepared_held_requires_separate_review"
            if status == "prepared" and budget == "held"
            else "prepared_no_budget_no_dispatch"
            if status == "prepared" else _RECOVERY[status]
        ),
        "durable_paid_intent_recorded": status != "prepared",
        "provider_interaction_recorded": has_interaction,
        "wav_format_receipt_recorded": has_audio,
        "three_scope_reservation": budget or "missing",
        "invoice_amount_entered_by_operator": budget == "reconciled",
        "vendor_invoice_independently_verified": False,
        "paid_provider_calls_by_this_probe": 0,
        "external_database_writes_by_this_probe": 0,
        "automated_retry_allowed": False,
        "recover_by_resubmitting": False,
        "publish_approved": False,
        "production_cutover_allowed": False,
        "immutable_audit_consistent": True,
    }
