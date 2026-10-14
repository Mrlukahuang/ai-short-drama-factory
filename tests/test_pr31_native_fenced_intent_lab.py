"""PR-31b2o4: pinned native libSQL SDK, disposable local fixture only."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

from drama_factory.jobs.budgets import configure_policy
from drama_factory.storage.libsql_sdk_local_ledger import _NativeConnection
from drama_factory.storage.pr31_native_fenced_intent_lab import (
    fenced_hold_and_record_intent_local,
)
from drama_factory.storage.pr31_native_fenced_job_lab import (
    NativeFenceLabDenied, fenced_claim_local_job, set_local_writer_gate,
)
from drama_factory.storage.pr31_offline_recovery import inspect_offline_job_recovery
from test_pr31_native_fenced_job_lab import _ready_lab

libsql = pytest.importorskip("libsql")


def _set_policies(backend, series, *, provider_limit="0.60", active_cap=2):
    column = backend.one(
        "SELECT column_id FROM projects WHERE id=?", (series,),
    )["column_id"]
    for scope, key, limit in (
        ("column", column, "2.00"),
        ("series", series, "2.00"),
        ("provider", "google", provider_limit),
    ):
        configure_policy(
            backend, scope, key, daily_limit_usd=limit,
            max_active_jobs=active_cap,
        )


def _count(backend, query, *params):
    # Query arguments are fixed literals below, not caller supplied SQL.
    return backend.one(query, tuple(params))["n"]


def _assert_no_intent(backend, job):
    row = backend.one(
        "SELECT status,generation_intent_recorded FROM shot_jobs WHERE id=?",
        (job,),
    )
    assert row == {"status": "leased", "generation_intent_recorded": 0}
    assert _count(
        backend,
        "SELECT COUNT(*) AS n FROM job_budget_reservations WHERE job_id=?",
        job,
    ) == 0
    assert _count(
        backend,
        "SELECT COUNT(*) AS n FROM shot_job_events "
        "WHERE shot_job_id=? AND action='generation_intent_recorded'",
        job,
    ) == 0


def test_atomic_fenced_hold_intent_and_recovery_review_cannot_authorize_vendor(client):
    backend, series, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    _set_policies(backend, series)
    token = fenced_claim_local_job(backend, "fence-intent-worker", production_id=run, now=point)
    report = fenced_hold_and_record_intent_local(
        backend, token, estimated_charge_usd="0.40", now=point,
    )
    assert report["status"] == "submission_intent"
    assert report["reservation_status"] == "held"
    assert report["authorizes_paid_provider_call"] is False
    assert report["may_automatically_retry"] is False
    assert report["paid_provider_calls"] == 0

    state = backend.one(
        "SELECT status,generation_intent_recorded,provider_task_id "
        "FROM shot_jobs WHERE id=?", (token.job_id,),
    )
    assert state == {
        "status": "submission_intent",
        "generation_intent_recorded": 1,
        "provider_task_id": None,
    }
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM job_budget_reservations "
        "WHERE job_id=? AND reserved_usd='0.40' AND status='held'", token.job_id,
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM budget_reservation_events "
        "WHERE action='held'",
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM shot_job_events "
        "WHERE action='generation_intent_recorded'",
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM pr31_native_job_fence_events "
        "WHERE action='fenced_hold_and_intent'",
    ) == 1
    recovery = inspect_offline_job_recovery(backend, token.job_id, now=point)
    assert {"held_budget", "intent_uncertain"} <= set(recovery["flags"])
    assert recovery["may_resubmit_paid_provider"] is False
    assert recovery["may_release_held_budget"] is False
    with pytest.raises(NativeFenceLabDenied, match="submitted"):
        fenced_hold_and_record_intent_local(
            backend, token, estimated_charge_usd="0.40", now=point,
        )


def test_two_workers_compete_for_same_provider_daily_cap_without_overbooking(client):
    backend, series, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    _set_policies(backend, series, provider_limit="0.60")
    tokens = [
        fenced_claim_local_job(backend, f"budget-worker-{i}", production_id=run, now=point)
        for i in range(2)
    ]
    assert tokens[0] and tokens[1] and tokens[0].job_id != tokens[1].job_id
    gate = Barrier(2)

    def compete(token):
        gate.wait(timeout=20)
        try:
            fenced_hold_and_record_intent_local(
                backend, token, estimated_charge_usd="0.40", now=point,
            )
            return "committed"
        except NativeFenceLabDenied:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, tokens))
    assert sorted(results) == ["committed", "rejected"]
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM job_budget_reservations "
        "WHERE status='held'",
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM shot_job_events "
        "WHERE action='generation_intent_recorded'",
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM budget_reservation_events "
        "WHERE action='held'",
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM pr31_native_job_fence_events "
        "WHERE action='fenced_hold_and_intent'",
    ) == 1


@pytest.mark.parametrize("change", [
    {"attempt": 2},
    {"worker_id": "different-worker"},
    {"epoch": 2},
    {"lease_expires_at": "2099-01-01T00:00:00+00:00"},
])
def test_modified_claim_is_rejected_without_any_reserved_amount(client, change):
    backend, series, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    _set_policies(backend, series)
    token = fenced_claim_local_job(backend, "original-worker", production_id=run, now=point)
    with pytest.raises(NativeFenceLabDenied):
        fenced_hold_and_record_intent_local(
            backend, replace(token, **change), estimated_charge_usd="0.40", now=point,
        )
    _assert_no_intent(backend, token.job_id)


def test_expiry_and_pause_resume_deny_old_claim_even_with_budget(client):
    backend, series, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    _set_policies(backend, series)
    token = fenced_claim_local_job(backend, "paused-worker", production_id=run, now=point)
    with pytest.raises(NativeFenceLabDenied):
        fenced_hold_and_record_intent_local(
            backend, token, estimated_charge_usd="0.40",
            now=point + timedelta(seconds=91),
        )
    paused = set_local_writer_gate(backend, pause=True)
    assert paused["epoch"] == 2
    with pytest.raises(NativeFenceLabDenied, match="gate"):
        fenced_hold_and_record_intent_local(
            backend, token, estimated_charge_usd="0.40", now=point,
        )
    assert set_local_writer_gate(
        backend, pause=False, operator_reviewed=True,
    )["epoch"] == 3
    with pytest.raises(NativeFenceLabDenied, match="epoch"):
        fenced_hold_and_record_intent_local(
            backend, token, estimated_charge_usd="0.40", now=point,
        )
    _assert_no_intent(backend, token.job_id)


def test_missing_policy_and_invalid_estimate_do_not_write(client):
    backend, _, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    token = fenced_claim_local_job(backend, "no-policy-worker", production_id=run, now=point)
    with pytest.raises(NativeFenceLabDenied, match="policy"):
        fenced_hold_and_record_intent_local(
            backend, token, estimated_charge_usd="0.40", now=point,
        )
    with pytest.raises(NativeFenceLabDenied, match="estimate"):
        fenced_hold_and_record_intent_local(
            backend, token, estimated_charge_usd="-5.00", now=point,
        )
    _assert_no_intent(backend, token.job_id)


def test_budget_audit_failure_rolls_back_entire_real_transaction(client, monkeypatch):
    import drama_factory.jobs.budgets as budgets

    backend, series, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    _set_policies(backend, series)
    token = fenced_claim_local_job(backend, "audit-worker", production_id=run, now=point)
    with monkeypatch.context() as patch:
        patch.setattr(budgets, "_event", lambda *args: (_ for _ in ()).throw(
            RuntimeError("Synthetic budget audit insertion failed")
        ))
        with pytest.raises(RuntimeError, match="audit"):
            fenced_hold_and_record_intent_local(
                backend, token, estimated_charge_usd="0.40", now=point,
            )
    _assert_no_intent(backend, token.job_id)
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM pr31_native_job_fence_events "
        "WHERE action='fenced_hold_and_intent'",
    ) == 0


def test_second_gate_audit_failure_rolls_back_reserve_intent_both_audits(client, monkeypatch):
    import drama_factory.storage.pr31_native_fenced_intent_lab as module

    backend, series, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    _set_policies(backend, series)
    token = fenced_claim_local_job(backend, "last-audit-worker", production_id=run, now=point)
    with monkeypatch.context() as patch:
        patch.setattr(module, "_gate_event", lambda *args: (_ for _ in ()).throw(
            RuntimeError("Synthetic final audit insertion failed")
        ))
        with pytest.raises(RuntimeError, match="final audit"):
            fenced_hold_and_record_intent_local(
                backend, token, estimated_charge_usd="0.40", now=point,
            )
    _assert_no_intent(backend, token.job_id)
    assert _count(backend, "SELECT COUNT(*) AS n FROM budget_reservation_events") == 0
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM pr31_native_job_fence_events "
        "WHERE action='fenced_hold_and_intent'",
    ) == 0


def test_commit_ack_loss_after_real_sdk_commit_is_quarantined_no_replay(client, monkeypatch):
    backend, series, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    _set_policies(backend, series)
    token = fenced_claim_local_job(backend, "ack-loss-worker", production_id=run, now=point)
    original_commit = _NativeConnection.commit
    observed = []

    def commit_then_lose_reply(conn):
        original_commit(conn)
        observed.append("durably_committed")
        raise ConnectionError("synthetic COMMIT response lost: SECRET_NEVER_OUTPUT")

    with monkeypatch.context() as patch:
        patch.setattr(_NativeConnection, "commit", commit_then_lose_reply)
        with pytest.raises(ConnectionError, match="response lost"):
            fenced_hold_and_record_intent_local(
                backend, token, estimated_charge_usd="0.40", now=point,
            )

    assert observed == ["durably_committed"]
    assert backend.one(
        "SELECT status,generation_intent_recorded FROM shot_jobs WHERE id=?",
        (token.job_id,),
    ) == {"status": "submission_intent", "generation_intent_recorded": 1}
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM job_budget_reservations WHERE job_id=?",
        token.job_id,
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM budget_reservation_events WHERE action='held'",
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM shot_job_events "
        "WHERE action='generation_intent_recorded'",
    ) == 1
    assert _count(
        backend, "SELECT COUNT(*) AS n FROM pr31_native_job_fence_events "
        "WHERE action='fenced_hold_and_intent'",
    ) == 1
    receipt = inspect_offline_job_recovery(backend, token.job_id, now=point)
    assert {"held_budget", "intent_uncertain"} <= set(receipt["flags"])
    assert receipt["may_resubmit_paid_provider"] is False
    assert "SECRET_NEVER_OUTPUT" not in str(receipt)
    with pytest.raises(NativeFenceLabDenied):
        fenced_hold_and_record_intent_local(
            backend, token, estimated_charge_usd="0.40", now=point,
        )
    assert _count(backend, "SELECT COUNT(*) AS n FROM job_budget_reservations") == 1


def test_not_exposed_to_unmarked_backend(client):
    with pytest.raises(NativeFenceLabDenied, match="fixture"):
        fenced_hold_and_record_intent_local(
            object(), object(), estimated_charge_usd="0.40",
        )
