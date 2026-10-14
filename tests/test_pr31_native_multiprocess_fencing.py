"""PR-31c3a: PROCESS-isolated native-SDK regression on disposable local files.

This is not a remote Runner test: independent Python OS processes share a
single local marker-guarded SQLite fixture on one CI host. All state-changing
methods are the existing isolated experimental methods; never a paid provider.
"""
from __future__ import annotations

import multiprocessing as mp
import os
from datetime import datetime, timezone

import pytest

from drama_factory.storage.libsql_sdk_local_ledger import LocalNativeLibsqlLedger
from drama_factory.storage.pr31_native_fenced_job_lab import (
    LocalClaimToken, NativeFenceLabDenied,
    fenced_claim_local_job, set_local_writer_gate,
)
from drama_factory.storage.pr31_native_fenced_intent_lab import fenced_hold_and_record_intent_local
from drama_factory.storage.pr31_native_synthetic_task_lab import (
    fenced_bind_synthetic_provider_task_local,
)
from drama_factory.storage.pr31_offline_recovery import inspect_offline_job_recovery
from test_pr31_native_fenced_job_lab import _ready_lab
from test_pr31_native_fenced_intent_lab import _set_policies

libsql = pytest.importorskip("libsql")
_CTX = mp.get_context("spawn")
_SYNTHETIC_TASK = "SYNTHETIC_PROCESS_TASK_001"


def _actor(path, op, ready, go, output, *, when, worker=None, run=None, token=None):
    """Executed in a genuinely distinct Python process with a new DB handle.

    Never print user content or exception strings. Unexpected failures should
    fail CI rather than be categorized as an accepted lock/fence rejection.
    """
    db = LocalNativeLibsqlLedger(path, offline_test_only=True)
    ready.put(True)
    if not go.wait(timeout=30):
        raise RuntimeError("Offline process start barrier timed out")
    now = datetime.fromisoformat(when)
    try:
        if op == "claim":
            result = fenced_claim_local_job(
                db, worker, production_id=run, now=now,
            )
            output.put(("claimed", result) if result else ("empty", None))
        elif op == "intent":
            receipt = fenced_hold_and_record_intent_local(
                db, token, estimated_charge_usd="0.40", now=now,
            )
            assert receipt["authorizes_paid_provider_call"] is False
            output.put(("intent", None))
        elif op == "pause":
            reply = set_local_writer_gate(db, pause=True)
            output.put(("paused", reply["epoch"]))
        elif op == "resume":
            reply = set_local_writer_gate(db, pause=False, operator_reviewed=True)
            output.put(("resumed", reply["epoch"]))
        elif op == "task":
            reply = fenced_bind_synthetic_provider_task_local(
                db, token, _SYNTHETIC_TASK, now=now,
            )
            assert reply["authorizes_paid_provider_call"] is False
            output.put(("synthetic_task", None))
        elif op == "crash_after_task_commit":
            # Deliberate hard process termination AFTER the SDK has durably
            # committed. The caller receives NO ACK and must use SELECT-only
            # reconciliation instead of replaying the operation.
            from drama_factory.storage.libsql_sdk_local_ledger import _NativeConnection
            original = _NativeConnection.commit

            def commit_then_die(conn):
                original(conn)
                os._exit(73)

            _NativeConnection.commit = commit_then_die
            fenced_bind_synthetic_provider_task_local(
                db, token, _SYNTHETIC_TASK, now=now,
            )
            raise AssertionError("Simulated crash did not happen")
        elif op == "crash_before_intent_commit":
            # All budget/shot/fence writes have occurred inside an open
            # transaction, then process dies before commit: SQLite must
            # roll back all of them. No retry is attempted in this actor.
            import drama_factory.storage.pr31_native_fenced_intent_lab as module

            def last_audit_then_die(conn, action, epoch):
                module._gate_event_original(conn, action, epoch)
                os._exit(74)

            module._gate_event_original = module._gate_event
            module._gate_event = last_audit_then_die
            fenced_hold_and_record_intent_local(
                db, token, estimated_charge_usd="0.40", now=now,
            )
            raise AssertionError("Simulated pre-commit crash did not happen")
        else:
            raise AssertionError("Unsupported test actor")
    except NativeFenceLabDenied:
        output.put(("denied", None))


def _launch(db, specs, *, now, expected_exit=None):
    """Separate interpreter per actor; shared local test file only."""
    ready = _CTX.Queue()
    out = _CTX.Queue()
    go = _CTX.Event()
    tasks = []
    for spec in specs:
        p = _CTX.Process(
            target=_actor,
            args=(str(db.path), spec["op"], ready, go, out),
            kwargs={
                "when": now.isoformat(),
                "worker": spec.get("worker"),
                "run": spec.get("run"),
                "token": spec.get("token"),
            },
        )
        p.start()
        tasks.append(p)
    try:
        for _ in tasks:
            assert ready.get(timeout=35) is True
        go.set()
        for p in tasks:
            p.join(timeout=45)
            if p.is_alive():
                p.terminate()
                p.join(timeout=10)
                pytest.fail("Local subprocess hung (no remote SQL was used)")
        if expected_exit is not None:
            assert len(tasks) == 1 and tasks[0].exitcode == expected_exit
            return []
        assert all(p.exitcode == 0 for p in tasks), [p.exitcode for p in tasks]
        return [out.get(timeout=10) for _ in tasks]
    finally:
        for p in tasks:
            if p.is_alive():
                p.terminate()
                p.join(timeout=10)
        ready.close()
        out.close()


def _n(db, table, action):
    assert table in (
        "shot_job_events", "budget_reservation_events",
        "pr31_native_job_fence_events",
    )
    return db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE action=?", (action,))["n"]


def test_six_separate_os_processes_claim_two_disposable_jobs_exactly_once(client):
    db, _, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    results = _launch(db, [
        {"op": "claim", "worker": f"process-worker-{i}", "run": run}
        for i in range(6)
    ], now=now)
    claims = [token for status, token in results if status == "claimed"]
    assert len(claims) == 2
    assert {status for status, token in results} == {"claimed", "empty"}
    assert len({t.job_id for t in claims}) == 2
    assert all(t.attempt == 1 and t.epoch == 1 for t in claims)
    assert _n(db, "shot_job_events", "claimed") == 2
    assert _n(db, "pr31_native_job_fence_events", "fenced_claim") == 2
    assert db.safety_metadata()["remote_concurrency_verified"] is False


def test_separate_processes_compete_for_three_scope_budget_under_60_cent_cap(client):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series, provider_limit="0.60")
    tokens = [
        fenced_claim_local_job(
            db, f"budget-process-{i}", production_id=run, now=now,
        ) for i in range(2)
    ]
    assert all(tokens)
    results = _launch(
        db, [{"op": "intent", "token": token} for token in tokens],
        now=now,
    )
    assert sorted(x[0] for x in results) == ["denied", "intent"]
    assert db.one(
        "SELECT COUNT(*) AS n FROM job_budget_reservations WHERE status='held'"
    )["n"] == 1
    assert _n(db, "budget_reservation_events", "held") == 1
    assert _n(db, "shot_job_events", "generation_intent_recorded") == 1
    assert _n(db, "pr31_native_job_fence_events", "fenced_hold_and_intent") == 1
    assert all(db.one(
        "SELECT COUNT(*) AS n FROM job_budget_reservations WHERE job_id=?",
        (t.job_id,),
    )["n"] <= 1 for t in tokens)


def test_separate_process_pause_blocks_old_token_after_resume(client):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series)
    token = fenced_claim_local_job(db, "old-process", production_id=run, now=now)
    assert token
    assert _launch(db, [{"op": "pause"}], now=now) == [("paused", 2)]
    assert _launch(db, [{"op": "intent", "token": token}], now=now) == [("denied", None)]
    assert _launch(db, [{"op": "resume"}], now=now) == [("resumed", 3)]
    assert _launch(db, [{"op": "intent", "token": token}], now=now) == [("denied", None)]
    assert db.one(
        "SELECT status FROM shot_jobs WHERE id=?", (token.job_id,),
    )["status"] == "leased"
    assert db.one(
        "SELECT COUNT(*) AS n FROM job_budget_reservations"
    )["n"] == 0
    assert _n(db, "pr31_native_job_fence_events", "pause") == 1


def test_os_process_crashes_after_durable_task_commit_then_read_only_quarantine(client):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series)
    token = fenced_claim_local_job(db, "crash-process", production_id=run, now=now)
    assert token
    assert _launch(
        db, [{"op": "intent", "token": token}], now=now,
    ) == [("intent", None)]
    _launch(db, [{"op": "crash_after_task_commit", "token": token}], now=now,
            expected_exit=73)
    review = inspect_offline_job_recovery(db, token.job_id, now=now)
    assert "existing_provider_task" in review["flags"]
    assert "held_budget" in review["flags"]
    assert review["may_resubmit_paid_provider"] is False
    assert review["cross_runner_fencing_verified"] is False
    assert _launch(db, [{"op": "task", "token": token}], now=now) == [("denied", None)]
    assert db.one(
        "SELECT status,provider_task_id FROM shot_jobs WHERE id=?",
        (token.job_id,),
    ) == {"status": "submitted", "provider_task_id": _SYNTHETIC_TASK}
    assert _n(db, "shot_job_events", "provider_task_recorded") == 1
    assert _n(db, "pr31_native_job_fence_events", "fenced_synthetic_task_bound") == 1
    assert db.one("SELECT COUNT(*) AS n FROM job_budget_reservations")["n"] == 1


def test_os_process_crashes_before_commit_and_every_audit_hold_rolls_back(client):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series)
    token = fenced_claim_local_job(db, "precommit-worker", production_id=run, now=now)
    assert token
    _launch(db, [{"op": "crash_before_intent_commit", "token": token}],
            now=now, expected_exit=74)
    assert db.one(
        "SELECT status,generation_intent_recorded FROM shot_jobs WHERE id=?",
        (token.job_id,),
    ) == {"status": "leased", "generation_intent_recorded": 0}
    assert db.one("SELECT COUNT(*) AS n FROM job_budget_reservations")["n"] == 0
    assert _n(db, "budget_reservation_events", "held") == 0
    assert _n(db, "shot_job_events", "generation_intent_recorded") == 0
    assert _n(db, "pr31_native_job_fence_events", "fenced_hold_and_intent") == 0
    report = inspect_offline_job_recovery(db, token.job_id, now=now)
    assert "intent_uncertain" not in report["flags"]
    assert report["may_resubmit_paid_provider"] is False


def test_independent_process_pause_and_intent_race_serialized_by_local_ledger(client):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series)
    token = fenced_claim_local_job(db, "racing-process", production_id=run, now=now)
    assert token
    results = _launch(db, [
        {"op": "pause"},
        {"op": "intent", "token": token},
    ], now=now)
    statuses = {x[0] for x in results}
    assert "paused" in statuses
    assert statuses in ({"paused", "denied"}, {"paused", "intent"})
    current = db.one(
        "SELECT status,generation_intent_recorded FROM shot_jobs WHERE id=?",
        (token.job_id,),
    )
    if "intent" in statuses:
        assert current == {"status": "submission_intent", "generation_intent_recorded": 1}
        assert _n(db, "budget_reservation_events", "held") == 1
    else:
        assert current == {"status": "leased", "generation_intent_recorded": 0}
        assert _n(db, "budget_reservation_events", "held") == 0
    assert db.one(
        "SELECT epoch,state FROM pr31_native_job_fence_gate WHERE id=1"
    ) == {"epoch": 2, "state": "paused"}
    assert _launch(db, [{"op": "intent", "token": token}], now=now) == [("denied", None)]
