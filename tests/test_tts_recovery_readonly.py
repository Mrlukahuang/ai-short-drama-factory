"""PR-10j: SQLite-only readback classifies paid intent without resubmission."""
from __future__ import annotations

import sqlite3

import pytest

from drama_factory.jobs.tts_fake_dispatch import (
    OfflineFakeGeminiTransport, OfflineTtsDispatchDenied,
    execute_offline_fake_tts_once,
)
from drama_factory.jobs.tts_intents import (
    acknowledge_tts_provider_interaction, commit_tts_submission_intent,
    prepare_tts_task, quarantine_tts_unknown_ack, record_tts_vendor_charge,
)
from drama_factory.jobs.tts_recovery_readonly import (
    TtsRecoveryDenied, inspect_tts_recovery,
)
from drama_factory.providers.gemini_tts_contract import GeminiTtsPreparation
from test_gemini_tts_contract import _approved_spec
from test_tts_fake_dispatch import _ready


def _snapshot(db, task):
    events = db.one(
        "SELECT COUNT(*) AS n FROM tts_task_events WHERE task_id=?", (task,),
    )["n"]
    reservation = db.one(
        "SELECT * FROM tts_budget_reservations WHERE task_id=?", (task,),
    )
    return db.one("SELECT * FROM tts_tasks WHERE id=?", (task,)), reservation, events


def _checked(db, task, status, kind):
    before = _snapshot(db, task)
    result = inspect_tts_recovery(db, task)
    assert _snapshot(db, task) == before
    assert result["task_status"] == status
    assert result["recovery_class"] == kind
    assert result["immutable_audit_consistent"] is True
    assert result["automated_retry_allowed"] is False
    assert result["recover_by_resubmitting"] is False
    assert result["paid_provider_calls_by_this_probe"] == 0
    assert result["external_database_writes_by_this_probe"] == 0
    assert result["vendor_invoice_independently_verified"] is False
    assert result["publish_approved"] is False
    assert "Hello" not in str(result)
    assert "interaction" not in str(result.get("task_id", ""))
    return result


def test_prepared_no_budget_and_prepared_held_readbacks(client):
    db, spec, _, _ = _approved_spec(client)
    control = GeminiTtsPreparation(
        consent_reviewed_by_operator=True, max_acknowledged_spend_usd="0.04",
    )
    task = prepare_tts_task(db, spec, control)
    a = _checked(db, task["id"], "prepared", "prepared_no_budget_no_dispatch")
    assert a["three_scope_reservation"] == "missing"
    # Adding a real budget policy is a separate mutation, not observer work.
    from test_tts_persistent_ledger import _policies
    from drama_factory.jobs.tts_intents import reserve_tts_task_budget
    _policies(db, spec.series_id, limit="0.05")
    reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.03")
    b = _checked(db, task["id"], "prepared", "prepared_held_requires_separate_review")
    assert b["three_scope_reservation"] == "held"
    assert b["durable_paid_intent_recorded"] is False


def test_committed_no_ack_is_not_a_dispatch_permission(client):
    db, spec, control, task, _, _ = _ready(client)
    commit_tts_submission_intent(db, task)
    state = _checked(
        db, task, "submission_intent",
        "unknown_provider_outcome_check_existing_request_only",
    )
    assert state["durable_paid_intent_recorded"] is True
    assert state["provider_interaction_recorded"] is False


def test_quarantined_unknown_ack_still_holds_full_reserve(client):
    db, spec, control, task, _, _ = _ready(client)
    fake = OfflineFakeGeminiTransport(fail_mode="ack_lost")
    with pytest.raises(OfflineTtsDispatchDenied):
        execute_offline_fake_tts_once(db, task, spec, control, fake)
    state = _checked(
        db, task, "quarantined", "invoice_or_provider_support_review_no_retry",
    )
    assert fake.calls == 1 and state["three_scope_reservation"] == "held"
    assert state["wav_format_receipt_recorded"] is False


def test_known_external_id_without_valid_wav_is_recovery_not_resubmit(client):
    db, spec, control, task, _, _ = _ready(client)
    fake = OfflineFakeGeminiTransport(fail_mode="invalid_wav")
    with pytest.raises(OfflineTtsDispatchDenied):
        execute_offline_fake_tts_once(db, task, spec, control, fake)
    state = _checked(
        db, task, "acknowledged",
        "recover_existing_interaction_audio_only",
    )
    assert state["provider_interaction_recorded"] is True
    assert state["wav_format_receipt_recorded"] is False
    assert state["three_scope_reservation"] == "held"


def test_verified_wav_format_still_needs_invoice_and_human_rights(client):
    db, spec, control, task, _, _ = _ready(client)
    execute_offline_fake_tts_once(
        db, task, spec, control, OfflineFakeGeminiTransport(),
    )
    state = _checked(
        db, task, "verified", "review_existing_wav_and_vendor_invoice_only",
    )
    assert state["wav_format_receipt_recorded"] is True
    assert state["provider_interaction_recorded"] is True
    assert state["invoice_amount_entered_by_operator"] is False


def test_human_invoice_reconciliation_does_not_free_unknown_retry(client):
    db, spec, control, task, _, _ = _ready(client)
    commit_tts_submission_intent(db, task)
    quarantine_tts_unknown_ack(db, task)
    record_tts_vendor_charge(
        db, task, amount_usd="0.06",
        evidence_reference="manual-billing-ticket-0001",
        reviewer="human-auditor",
    )
    state = _checked(
        db, task, "quarantined", "invoice_or_provider_support_review_no_retry",
    )
    assert state["three_scope_reservation"] == "reconciled"
    assert state["invoice_amount_entered_by_operator"] is True
    assert state["automated_retry_allowed"] is False
    assert "billing-ticket" not in str(state)
    assert "human-auditor" not in str(state)


@pytest.mark.parametrize("corruption", [
    "pretend_verified", "fake_interaction_id", "fake_wav_digest",
    "fake_reconciled_invoice", "fake_budget_missing", "duplicate_audit",
])
def test_corrupted_or_malicious_recovery_snapshot_fails_closed(client, corruption):
    db, spec, control, task, _, _ = _ready(client)
    if corruption == "pretend_verified":
        db.exec("UPDATE tts_tasks SET status='verified' WHERE id=?", (task,))
    elif corruption == "fake_interaction_id":
        db.exec("UPDATE tts_tasks SET interaction_id='stolen-id' WHERE id=?", (task,))
    elif corruption == "fake_wav_digest":
        db.exec("UPDATE tts_tasks SET output_sha256=? WHERE id=?", ("f" * 64, task))
    elif corruption == "fake_reconciled_invoice":
        db.exec("UPDATE tts_budget_reservations SET status='reconciled' WHERE task_id=?", (task,))
    elif corruption == "fake_budget_missing":
        db.exec("DELETE FROM tts_budget_reservations WHERE task_id=?", (task,))
    else:
        db.exec(
            """INSERT INTO tts_task_events
               (id,task_id,action,previous_state,next_state,details_json,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            ("extra-test-event", task, "paid_intent_committed", "prepared",
             "submission_intent", "{}", "2026-10-14T00:00:00Z"),
        )
    with pytest.raises(TtsRecoveryDenied):
        inspect_tts_recovery(db, task)


def test_invalid_or_private_task_id_denied_before_db_read(client):
    db, *_ = _ready(client)
    for bogus in ("Hello", "", "ttstask_NOTHEX", None, 14, "ttstask_" + "x"*14):
        with pytest.raises(TtsRecoveryDenied):
            inspect_tts_recovery(db, bogus)
