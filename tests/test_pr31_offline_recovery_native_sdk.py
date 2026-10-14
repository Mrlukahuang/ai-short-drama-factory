"""PR-31b2o2: native SDK ledger recovery inspection; offline only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from drama_factory.jobs.budgets import record_operator_verified_charge
from drama_factory.jobs.shots import record_submission_intent
from drama_factory.storage.libsql_sdk_local_ledger import _NativeConnection
from drama_factory.storage.pr31_offline_recovery import (
    OfflineRecoveryDenied, inspect_offline_job_recovery,
)
from test_libsql_sdk_local_ledger_adapter import _ready

libsql = pytest.importorskip("libsql")


def _inspect(backend, job, *, now=None):
    receipt = inspect_offline_job_recovery(backend, job, now=now)
    assert receipt["readonly_snapshot"] is True
    assert receipt["needs_operator_review"] is True
    assert receipt["safe_to_inspect_only"] is True
    assert receipt["may_resubmit_paid_provider"] is False
    assert receipt["may_release_held_budget"] is False
    assert receipt["remote_write_calls"] == receipt["paid_provider_calls"] == 0
    assert receipt["live_cutover_permitted"] is False
    return set(receipt["flags"]), receipt


def test_held_budget_and_missing_task_after_intent_never_allow_replay(client):
    backend, job, reserve = _ready(client)
    flags, report = _inspect(backend, job)
    assert "held_budget" in flags
    assert "intent_uncertain" not in flags
    record_submission_intent(backend, job, "sdk-test-worker")
    flags, report = _inspect(backend, job)
    assert {"held_budget", "intent_uncertain"} <= flags
    rendered = str(report)
    assert job not in rendered and reserve not in rendered
    assert "sdk-test-worker" not in rendered
    assert "0.40" not in rendered
    assert "google" not in rendered


def test_committed_charge_readback_with_lost_commit_ack_is_only_readonly(client, monkeypatch):
    backend, job, reserve = _ready(client)
    record_submission_intent(backend, job, "sdk-test-worker")
    real_commit = _NativeConnection.commit
    commit_count = []

    def commit_then_drop_reply(conn):
        real_commit(conn)
        commit_count.append(True)
        raise ConnectionError("COMMIT acknowledged nowhere — HIDDEN_TOKEN")

    with monkeypatch.context() as patch:
        patch.setattr(_NativeConnection, "commit", commit_then_drop_reply)
        with pytest.raises(ConnectionError, match="COMMIT"):
            record_operator_verified_charge(
                backend, job, amount_usd="0.55",
                evidence_reference="SYNTHETIC-NOT-VENDOR-PROOF",
                reviewer="offline-test",
            )
    assert len(commit_count) == 1
    before = backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events WHERE reservation_id=?",
        (reserve,),
    )["n"]
    flags, report = _inspect(backend, job)
    assert "charge_reconciled" in flags
    assert "held_budget" not in flags
    assert "intent_uncertain" in flags  # no task ID, never infer retry permission
    after = backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events WHERE reservation_id=?",
        (reserve,),
    )["n"]
    assert before == after
    assert "HIDDEN_TOKEN" not in str(report)
    assert "SYNTHETIC-NOT-VENDOR-PROOF" not in str(report)
    assert "0.55" not in str(report)


def test_failed_audit_write_rolls_back_charge_and_keeps_hold(client, monkeypatch):
    import drama_factory.jobs.budgets as budgets

    backend, job, reserve = _ready(client)
    record_submission_intent(backend, job, "sdk-test-worker")
    with monkeypatch.context() as patch:
        def deny(*args, **kwargs):
            raise RuntimeError("local synthetic append-only audit unavailable")
        patch.setattr(budgets, "_event", deny)
        with pytest.raises(RuntimeError, match="audit unavailable"):
            record_operator_verified_charge(
                backend, job, amount_usd="0.55",
                evidence_reference="SYNTHETIC", reviewer="offline-test",
            )
    flags, _ = _inspect(backend, job)
    assert {"held_budget", "intent_uncertain"} <= flags
    assert "charge_reconciled" not in flags
    assert backend.one(
        "SELECT status FROM job_budget_reservations WHERE id=?", (reserve,)
    )["status"] == "held"


def test_expired_lease_missing_job_and_invalid_time_are_fail_closed(client):
    backend, job, _ = _ready(client)
    flags, _ = _inspect(backend, job, now=datetime.now(timezone.utc) + timedelta(days=2))
    assert "lease_expired" in flags
    flags, report = _inspect(backend, "nonexistent-synthetic-fixture-key")
    assert "missing_job" in flags
    assert "nonexistent-synthetic-fixture-key" not in str(report)
    with pytest.raises(OfflineRecoveryDenied, match="Timezone"):
        inspect_offline_job_recovery(backend, job, now=datetime(2026, 10, 14))
    with pytest.raises(OfflineRecoveryDenied, match="fixture"):
        inspect_offline_job_recovery(object(), job)
