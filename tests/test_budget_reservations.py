"""Offline three-layer budget holds, concurrency and manual billing reconciliation."""
from __future__ import annotations

import sqlite3
from decimal import Decimal

import pytest

from drama_factory.jobs.shots import (
    ShotJobError, claim_next_job, prepare_shot_jobs,
    record_submission_intent, record_submission,
)
from drama_factory.jobs.budgets import (
    BudgetDenied, configure_policy, record_operator_verified_charge,
    release_unsubmitted_reservation, reserve_job_budget,
)


def prepared(client, label):
    r = client.post("/api/v1/projects", json={
        "title": label, "premise": "Original screenplay for budget tests",
    })
    assert r.status_code == 201, r.text
    sid = r.json()["series_id"]
    response = client.post(f"/api/v1/projects/{sid}/episodes", json={
        "title": "Pilot", "episode_number": 1, "target_duration_seconds": 4,
        "shots": [
            {"shot_id": "s01", "duration_seconds": 2,
             "visual_description": "Walk forward", "video_model": "gemini-omni-1.1-flash"},
            {"shot_id": "s02", "duration_seconds": 2,
             "visual_description": "Walk backward", "video_model": "gemini-omni-1.1-flash"},
        ],
    })
    assert response.status_code == 201, response.text
    episode_id = response.json()["episode_id"]
    result = client.post(f"/api/v1/episodes/{episode_id}/productions")
    assert result.status_code == 201, result.text
    run = result.json()["production_id"]
    assert client.post(f"/api/v1/productions/{run}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code == 200
    jobs = prepare_shot_jobs(client.app.state.db, run)
    return sid, jobs


def configure_three(db, series_id, *, column_limit="10.00", series_limit="10.00",
                    provider_limit="10.00", parallel=10):
    column = db.one("SELECT column_id FROM projects WHERE id=?", (series_id,))["column_id"]
    for kind, value, limit in (
        ("column", column, column_limit), ("series", series_id, series_limit),
        ("provider", "google", provider_limit),
    ):
        configure_policy(db, kind, value,
                         daily_limit_usd=limit, max_active_jobs=parallel)


def test_budget_fail_closed_until_all_three_policies_exist(client):
    sid, _ = prepared(client, "Without policies")
    db = client.app.state.db
    job = claim_next_job(db, "worker1", series_id=sid)
    with pytest.raises(BudgetDenied, match="column"):
        reserve_job_budget(db, job["id"], estimated_charge_usd="0.50")
    column = db.one("SELECT column_id FROM projects WHERE id=?", (sid,))["column_id"]
    configure_policy(db, "column", column, daily_limit_usd="2.00", max_active_jobs=2)
    with pytest.raises(BudgetDenied, match="series"):
        reserve_job_budget(db, job["id"], estimated_charge_usd="0.50")
    configure_policy(db, "series", sid, daily_limit_usd="2.00", max_active_jobs=2)
    with pytest.raises(BudgetDenied, match="provider"):
        reserve_job_budget(db, job["id"], estimated_charge_usd="0.50")
    with pytest.raises(ShotJobError, match="budget reservation"):
        record_submission_intent(db, job["id"], "worker1")
    configure_policy(db, "provider", "google", daily_limit_usd="2.00", max_active_jobs=2)
    reservation = reserve_job_budget(db, job["id"], estimated_charge_usd="0.50")
    assert reservation["reserved_usd"] == "0.50"
    assert reservation["status"] == "held"
    assert record_submission_intent(db, job["id"], "worker1")["status"] == "submission_intent"


def test_two_series_share_the_column_spending_limit(client):
    sid_a, _ = prepared(client, "Series A")
    sid_b, _ = prepared(client, "Series B")
    db = client.app.state.db
    configure_three(db, sid_a, column_limit="1.00")
    configure_three(db, sid_b, column_limit="1.00")
    first = claim_next_job(db, "worker1", series_id=sid_a)
    second = claim_next_job(db, "worker2", series_id=sid_b)
    reserve_job_budget(db, first["id"], estimated_charge_usd="0.80")
    with pytest.raises(BudgetDenied, match="column daily budget"):
        reserve_job_budget(db, second["id"], estimated_charge_usd="0.30")
    assert reserve_job_budget(db, second["id"], estimated_charge_usd="0.20")["status"] == "held"


def test_series_and_provider_limits_work_independently(client):
    a, _ = prepared(client, "Series A")
    b, _ = prepared(client, "Series B")
    db = client.app.state.db
    configure_three(db, a, series_limit="0.50", provider_limit="0.70")
    configure_three(db, b, series_limit="10.00", provider_limit="0.70")
    job_a1 = claim_next_job(db, "worker1", series_id=a)
    reserve_job_budget(db, job_a1["id"], estimated_charge_usd="0.45")
    job_a2 = claim_next_job(db, "worker2", series_id=a)
    with pytest.raises(BudgetDenied, match="series"):
        reserve_job_budget(db, job_a2["id"], estimated_charge_usd="0.20")
    job_b = claim_next_job(db, "worker3", series_id=b)
    with pytest.raises(BudgetDenied, match="provider"):
        reserve_job_budget(db, job_b["id"], estimated_charge_usd="0.30")


def test_parallel_limit_blocks_second_held_job_until_safe_release(client):
    sid, _ = prepared(client, "Parallel")
    db = client.app.state.db
    configure_three(db, sid, parallel=1)
    first = claim_next_job(db, "worker1", series_id=sid)
    second = claim_next_job(db, "worker2", series_id=sid)
    reserve_job_budget(db, first["id"], estimated_charge_usd="0.40")
    with pytest.raises(BudgetDenied, match="active job"):
        reserve_job_budget(db, second["id"], estimated_charge_usd="0.40")
    with pytest.raises(BudgetDenied, match="Manual review"):
        release_unsubmitted_reservation(db, first["id"], operator_reviewed=False)
    assert release_unsubmitted_reservation(
        db, first["id"], operator_reviewed=True,
    )["status"] == "released"
    assert reserve_job_budget(db, second["id"], estimated_charge_usd="0.40")["status"] == "held"


def test_paid_intent_holds_budget_until_evidence_backed_reconciliation(client):
    sid, _ = prepared(client, "Billing")
    db = client.app.state.db
    configure_three(db, sid, column_limit="1.00", series_limit="1.00",
                    provider_limit="1.00")
    first = claim_next_job(db, "worker1", series_id=sid)
    reserve_job_budget(db, first["id"], estimated_charge_usd="0.70")
    record_submission_intent(db, first["id"], "worker1")
    with pytest.raises(BudgetDenied, match="cannot release"):
        release_unsubmitted_reservation(db, first["id"], operator_reviewed=True)
    record_submission(db, first["id"], "worker1", "tasks/manual_video_1")
    settled = record_operator_verified_charge(
        db, first["id"], amount_usd="0.90",
        evidence_reference="GOOGLE-INVOICE-TEST-001", reviewer="operator",
    )
    assert settled["status"] == "reconciled" and settled["actual_usd"] == "0.90"
    assert db.one("SELECT actual_vendor_charge_usd FROM shot_jobs WHERE id=?",
                  (first["id"],))["actual_vendor_charge_usd"] == "0.90"
    second = claim_next_job(db, "worker2", series_id=sid)
    with pytest.raises(BudgetDenied, match="daily budget"):
        reserve_job_budget(db, second["id"], estimated_charge_usd="0.20")


def test_estimate_cannot_exceed_operator_acknowledgement(client):
    sid, _ = prepared(client, "Acknowledged")
    db = client.app.state.db
    configure_three(db, sid)
    first = claim_next_job(db, "worker1", series_id=sid)
    with pytest.raises(BudgetDenied, match="acknowledged"):
        reserve_job_budget(db, first["id"], estimated_charge_usd="1.01")


def test_budget_policies_version_and_disabled_policy(client):
    sid, _ = prepared(client, "Policy revisions")
    db = client.app.state.db
    configure_three(db, sid)
    disabled = configure_policy(db, "series", sid,
                                daily_limit_usd="1.00",
                                max_active_jobs=1, enabled=False)
    assert disabled["revision"] == 2
    first = claim_next_job(db, "worker1", series_id=sid)
    with pytest.raises(BudgetDenied, match="series"):
        reserve_job_budget(db, first["id"], estimated_charge_usd="0.10")


def test_budget_reservation_events_are_append_only(client):
    sid, _ = prepared(client, "Audit")
    db = client.app.state.db
    configure_three(db, sid)
    job = claim_next_job(db, "worker1", series_id=sid)
    reservation = reserve_job_budget(db, job["id"], estimated_charge_usd="0.25")
    assert reserve_job_budget(db, job["id"], estimated_charge_usd="0.25")["id"] == reservation["id"]
    event = db.one("SELECT id FROM budget_reservation_events WHERE reservation_id=?",
                   (reservation["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.exec("DELETE FROM budget_reservation_events WHERE id=?", (event["id"],))


def test_operator_entered_over_reserve_charge_cannot_hide_overspend(client):
    sid, _ = prepared(client, "Overcharge")
    db = client.app.state.db
    configure_three(db, sid, column_limit="1.00", series_limit="1.00",
                    provider_limit="1.00")
    first = claim_next_job(db, "worker1", series_id=sid)
    reserve_job_budget(db, first["id"], estimated_charge_usd="0.70")
    record_submission_intent(db, first["id"], "worker1")
    adjusted = record_operator_verified_charge(
        db, first["id"], amount_usd="1.20",
        evidence_reference="INVOICE-EXCEEDS-RESERVE", reviewer="operator",
    )
    assert adjusted["status"] == "reconciled"
    assert Decimal(adjusted["actual_usd"]) > Decimal(adjusted["reserved_usd"])
    second = claim_next_job(db, "worker2", series_id=sid)
    with pytest.raises(BudgetDenied, match="daily budget"):
        reserve_job_budget(db, second["id"], estimated_charge_usd="0.10")


def test_true_concurrent_budget_reservations_never_exceed_limits(client):
    """PR-31b source baseline: simultaneous reservations cannot double-spend."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    sid, _ = prepared(client, "two simultaneous budget requests")
    db = client.app.state.db
    configure_three(
        db, sid, column_limit="0.60", series_limit="0.60",
        provider_limit="0.60", parallel=2,
    )
    first = claim_next_job(db, "parallel-budget-a", series_id=sid)
    second = claim_next_job(db, "parallel-budget-b", series_id=sid)
    assert first["id"] != second["id"]
    gate = Barrier(2)

    def reserve(job_id):
        gate.wait(timeout=10)
        try:
            return reserve_job_budget(
                db, job_id, estimated_charge_usd="0.40",
            )["status"]
        except BudgetDenied:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, (first["id"], second["id"])))

    assert sorted(outcomes) == ["denied", "held"]
    reservations = db.many("SELECT job_id,reserved_usd,status FROM job_budget_reservations")
    assert len(reservations) == 1
    assert reservations[0]["reserved_usd"] == "0.40"
    assert reservations[0]["status"] == "held"
    assert db.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events WHERE action='held'"
    )["n"] == 1
    assert db.one(
        "SELECT COUNT(*) AS n FROM shot_jobs WHERE generation_intent_recorded=1"
    )["n"] == 0


def test_budget_audit_failure_undoes_reservation_without_overspending(client, monkeypatch):
    """Reservation and audit must commit or roll back together."""
    import drama_factory.jobs.budgets as budgets_module

    sid, _ = prepared(client, "migration-atomic-budget-audit")
    db = client.app.state.db
    configure_three(db, sid)
    job = claim_next_job(db, "budget-worker", series_id=sid)

    def fail_event(*args, **kwargs):
        raise RuntimeError("simulated reservation audit failure")

    monkeypatch.setattr(budgets_module, "_event", fail_event)
    with pytest.raises(RuntimeError, match="simulated reservation audit failure"):
        reserve_job_budget(db, job["id"], estimated_charge_usd="0.40")
    assert db.one(
        "SELECT COUNT(*) AS n FROM job_budget_reservations"
    )["n"] == 0
    assert db.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events"
    )["n"] == 0
    assert db.one(
        "SELECT status FROM shot_jobs WHERE id=?", (job["id"],),
    )["status"] == "leased"
