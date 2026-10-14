"""PR-31c3b: read-only quiescence report on marked temporary SDK ledger."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from drama_factory.jobs.budgets import record_operator_verified_charge
from drama_factory.storage.pr31_native_fenced_job_lab import (
    fenced_claim_local_job, set_local_writer_gate,
)
from drama_factory.storage.pr31_native_fenced_intent_lab import (
    fenced_hold_and_record_intent_local,
)
from drama_factory.storage.pr31_native_synthetic_task_lab import (
    fenced_bind_synthetic_provider_task_local,
)
from drama_factory.storage.pr31_offline_writer_quiescence import (
    LocalQuiescenceDenied, inspect_offline_writer_quiescence,
)
from test_pr31_native_fenced_job_lab import _ready_lab
from test_pr31_native_fenced_intent_lab import _set_policies
from test_libsql_sdk_local_ledger_adapter import _backend, _production

libsql = pytest.importorskip("libsql")


def _state(db):
    return (
        db.one("SELECT epoch,state FROM pr31_native_job_fence_gate WHERE id=1"),
        db.one("SELECT COUNT(*) AS n FROM shot_job_events"),
        db.one("SELECT COUNT(*) AS n FROM budget_reservation_events"),
    )


def test_pending_jobs_and_paused_gate_are_only_local_review_candidates(client):
    db, _, run = _ready_lab(client)
    assert run
    running = inspect_offline_writer_quiescence(db)
    assert "writer_gate_running" in running["flags"]
    assert running["offline_quiescence_candidate_for_review"] is False
    assert set_local_writer_gate(db, pause=True)["epoch"] == 2
    previous = _state(db)
    disk_before = db.path.read_bytes()
    review = inspect_offline_writer_quiescence(db)
    assert review["flags"] == ["operator_review_required", "writer_gate_paused"]
    assert review["offline_quiescence_candidate_for_review"] is True
    assert review["safe_to_authorize_resume"] is False
    assert review["may_resume_remote_writers"] is False
    assert review["may_resume_production_writers"] is False
    assert review["live_cutover_permitted"] is False
    assert review["sqlite_read_only"] is True
    assert review["remote_write_calls"] == review["paid_provider_calls"] == 0
    assert run not in str(review)
    assert _state(db) == previous
    assert db.path.read_bytes() == disk_before


def test_leased_job_blocks_quiescence_even_after_writer_pause(client):
    db, _, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    token = fenced_claim_local_job(db, "local-quiescence-worker", production_id=run, now=now)
    assert token
    set_local_writer_gate(db, pause=True)
    r = inspect_offline_writer_quiescence(db)
    assert {"unsettled_shot", "active_or_stale_lease", "writer_gate_paused"} <= set(r["flags"])
    assert r["offline_quiescence_candidate_for_review"] is False
    assert r["may_resume_production_writers"] is False


def test_held_reservation_and_uncertain_intent_remain_blocked(client):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series)
    token = fenced_claim_local_job(db, "intent-quiescence-worker", production_id=run, now=now)
    assert token
    assert fenced_hold_and_record_intent_local(
        db, token, estimated_charge_usd="0.40", now=now
    )["status"] == "submission_intent"
    set_local_writer_gate(db, pause=True)
    r = inspect_offline_writer_quiescence(db)
    assert {"historical_paid_intent", "held_budget_needs_reconciliation",
            "unsettled_shot", "writer_gate_paused"} <= set(r["flags"])
    assert r["offline_quiescence_candidate_for_review"] is False
    assert r["may_retry_paid_provider"] is False
    assert r["may_release_held_budget"] is False
    assert token.job_id not in str(r)


def test_provider_task_recorded_still_requires_independent_review(client):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series)
    token = fenced_claim_local_job(db, "task-quiescence-worker", production_id=run, now=now)
    assert token
    fenced_hold_and_record_intent_local(db, token, estimated_charge_usd="0.40", now=now)
    fenced_bind_synthetic_provider_task_local(
        db, token, "SYNTHETIC_TASK_FOR_REVIEW_001", now=now
    )
    set_local_writer_gate(db, pause=True)
    review = inspect_offline_writer_quiescence(db)
    assert {"historical_paid_intent", "provider_task_needs_independent_review",
            "held_budget_needs_reconciliation"} <= set(review["flags"])
    assert review["offline_quiescence_candidate_for_review"] is False
    assert "SYNTHETIC_TASK_FOR_REVIEW_001" not in str(review)


def test_manually_reconciled_charge_is_not_voucher_for_provider_replay(client):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series)
    token = fenced_claim_local_job(db, "reviewed-quiescence-worker", production_id=run, now=now)
    assert token
    fenced_hold_and_record_intent_local(db, token, estimated_charge_usd="0.40", now=now)
    verified = record_operator_verified_charge(
        db, token.job_id, amount_usd="0.40",
        evidence_reference="SYNTHETIC-LOCAL-ONLY-EVIDENCE",
        reviewer="offline-test-reviewer",
    )
    assert verified["status"] == "reconciled"
    set_local_writer_gate(db, pause=True)
    report = inspect_offline_writer_quiescence(db)
    assert "held_budget_needs_reconciliation" not in report["flags"]
    assert "historical_paid_intent" in report["flags"]
    assert report["offline_quiescence_candidate_for_review"] is False
    assert report["may_retry_paid_provider"] is False


def test_gate_epoch_or_audit_mismatch_denies_candidate_without_auto_repair(client):
    db, _, _ = _ready_lab(client)
    set_local_writer_gate(db, pause=True)
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE pr31_native_job_fence_gate SET epoch=9 WHERE id=1")
    original = _state(db)
    report = inspect_offline_writer_quiescence(db)
    assert "gate_audit_inconsistent" in report["flags"]
    assert report["offline_quiescence_candidate_for_review"] is False
    assert _state(db) == original


def test_missing_gate_marker_or_unmarked_backend_fails_closed(client):
    _production(client)
    uninitialized = _backend(client)
    with pytest.raises(LocalQuiescenceDenied, match="unavailable"):
        inspect_offline_writer_quiescence(uninitialized)
    with pytest.raises(LocalQuiescenceDenied, match="Marked"):
        inspect_offline_writer_quiescence(object())
    from drama_factory.storage.libsql_sdk_local_ledger import _MARKER_TABLE
    from drama_factory.storage.pr31_native_fenced_job_lab import init_local_native_fence_lab
    init_local_native_fence_lab(uninitialized, isolated_test_only=True)
    with uninitialized.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(f"DELETE FROM {_MARKER_TABLE}")
    with pytest.raises(LocalQuiescenceDenied, match="marker"):
        inspect_offline_writer_quiescence(uninitialized)
