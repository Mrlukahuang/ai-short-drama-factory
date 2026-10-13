"""PR-31b2o1: actual native libsql local SDK under parallel business operations.

Only fresh pytest SQLite fixtures carrying the local-only marker are used.
There is no remote URL, no Turso credential, no paid Provider/Drive interaction,
and no automatic retry. Lock errors are measured, never treated as success.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from drama_factory.jobs.budgets import (
    BudgetDenied, configure_policy, reserve_job_budget, record_operator_verified_charge,
)
from drama_factory.jobs.shots import (
    ShotJobError, claim_next_job, prepare_shot_jobs, record_submission_intent,
)
from drama_factory.storage.libsql_sdk_local_ledger import _NativeConnection
from test_libsql_sdk_local_ledger_adapter import _production, _backend, _ready

libsql = pytest.importorskip("libsql")


def _race(count, action):
    gate = Barrier(count)
    def run(i):
        gate.wait(timeout=20)
        try:
            return ("success", action(i))
        except Exception as exc:
            # Both SQLITE_BUSY and business denial are distinct non-commits.
            # Never include SDK exception text in reports.
            category = "busy" if "lock" in str(exc).lower() or "busy" in str(exc).lower() else "denied"
            return (category, None)
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(run, range(count)))


def test_native_sdk_concurrent_shot_claims_keep_unique_leases(client):
    _, run = _production(client)
    backend = _backend(client)
    jobs = prepare_shot_jobs(backend, run)
    assert len(jobs) == 2

    results = _race(8, lambda i: claim_next_job(
        backend, f"native-sdk-worker-{i}", production_id=run,
    ))
    successful = [item for state, item in results if state == "success" and item]
    assert len({item["id"] for item in successful}) == len(successful)
    assert len(successful) <= 2
    assert all(item["status"] == "leased" for item in successful)
    rows = backend.many(
        "SELECT id,status,attempts,lease_owner FROM shot_jobs WHERE production_id=?",
        (run,),
    )
    leased = [row for row in rows if row["status"] == "leased"]
    assert len(leased) == len(successful)
    assert all(row["attempts"] == 1 and row["lease_owner"] for row in leased)
    assert backend.one(
        "SELECT COUNT(*) AS n FROM shot_job_events WHERE action='claimed' "
        "AND shot_job_id IN (SELECT id FROM shot_jobs WHERE production_id=?)",
        (run,),
    )["n"] == len(leased)


def test_native_sdk_competing_budget_reservations_never_exceed_provider_cap(client):
    series, run = _production(client)
    backend = _backend(client)
    assert len(prepare_shot_jobs(backend, run)) == 2
    col = backend.one("SELECT column_id FROM projects WHERE id=?", (series,))["column_id"]
    for scope, value, limit in (
        ("column", col, "1.00"), ("series", series, "1.00"),
        ("provider", "google", "0.60"),
    ):
        configure_policy(
            backend, scope, value, daily_limit_usd=limit, max_active_jobs=2,
        )
    first = claim_next_job(backend, "sdk-first", production_id=run)
    second = claim_next_job(backend, "sdk-second", production_id=run)
    assert first and second and first["id"] != second["id"]

    ids = [first["id"], second["id"]]
    result = _race(2, lambda i: reserve_job_budget(
        backend, ids[i], estimated_charge_usd="0.40",
    ))
    held = backend.many(
        "SELECT job_id,reserved_usd,status FROM job_budget_reservations "
        "WHERE status='held'"
    )
    assert len(held) <= 1
    assert len({row["job_id"] for row in held}) == len(held)
    assert sum(int(round(float(r["reserved_usd"]) * 100)) for r in held) <= 60
    assert sum(state == "success" for state, _ in result) == len(held)
    assert backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events WHERE action='held'"
    )["n"] == len(held)


def test_native_sdk_commit_ack_lost_does_not_replay_billing(client, monkeypatch):
    backend, job_id, reservation_id = _ready(client)
    record_submission_intent(backend, job_id, "sdk-test-worker")
    real_commit = _NativeConnection.commit
    observed = {"raised": 0}

    def reply_lost_after_real_commit(conn):
        real_commit(conn)
        observed["raised"] += 1
        raise ConnectionError("ACK lost after durable COMMIT — PRIVATE_TEST_TOKEN")

    # Inject only during this real business transaction, with SDK performing
    # the durable COMMIT before simulated response loss.
    with monkeypatch.context() as patch:
        patch.setattr(_NativeConnection, "commit", reply_lost_after_real_commit)
        with pytest.raises(ConnectionError, match="ACK lost"):
            record_operator_verified_charge(
                backend, job_id, amount_usd="0.55",
                evidence_reference="SYNTHETIC-ACK-LOSS",
                reviewer="offline-native-reviewer",
            )
    assert observed["raised"] == 1  # no internal commit replay
    reservation = backend.one(
        "SELECT status,actual_usd FROM job_budget_reservations WHERE id=?",
        (reservation_id,),
    )
    job = backend.one(
        "SELECT actual_vendor_charge_usd AS cost FROM shot_jobs WHERE id=?",
        (job_id,),
    )
    events = backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events "
        "WHERE reservation_id=? AND action='operator_entered_vendor_charge'",
        (reservation_id,),
    )["n"]
    assert reservation == {"status": "reconciled", "actual_usd": "0.55"}
    assert job["cost"] == "0.55"
    assert events == 1
    with pytest.raises(BudgetDenied):
        record_operator_verified_charge(
            backend, job_id, amount_usd="0.55",
            evidence_reference="SYNTHETIC-UNSAFE-REPLAY",
            reviewer="different-reviewer",
        )
    assert backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events "
        "WHERE reservation_id=? AND action='operator_entered_vendor_charge'",
        (reservation_id,),
    )["n"] == 1
    assert backend.safety_metadata()["remote_concurrency_verified"] is False
    assert backend.safety_metadata()["network_commit_recovery_verified"] is False
    assert backend.safety_metadata()["production_backend_switched"] is False
