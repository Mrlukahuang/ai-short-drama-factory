"""PR-31b2i: the REAL shot/budget business functions under multi-table faults.

All inputs live in a freshly generated temp SQLite database. The production
Worker, Turso clients, Google Drive and paid Provider modules are not used.

This locks down the contract a future *independently verified* remote backend
must satisfy: per-operation atomicity, immutable financial audit, manual
reconciliation and no duplicate provider intent. It does not verify libSQL.
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from drama_factory.jobs.budgets import (
    BudgetDenied, configure_policy, record_operator_verified_charge,
    reserve_job_budget,
)
from drama_factory.jobs.shots import (
    ShotJobError, claim_next_job, prepare_shot_jobs,
    record_submission, record_submission_intent,
)
from drama_factory.storage.ledger_backend_contract import OfflineSqliteLedger


def _make_reviewed_jobs(client):
    project = client.post("/api/v1/projects", json={
        "title": "ORIGINAL_FAKE_LEDGER_SERIES", "premise": "Original disposable CI story",
    })
    assert project.status_code == 201, project.text
    series = project.json()["series_id"]
    episode = client.post(f"/api/v1/projects/{series}/episodes", json={
        "title": "Test pilot", "episode_number": 1, "target_duration_seconds": 4,
        "shots": [
            {"shot_id": "S01", "duration_seconds": 2,
             "visual_description": "Door opens", "video_model": "gemini-omni-1.1-flash"},
            {"shot_id": "S02", "duration_seconds": 2,
             "visual_description": "Door closes", "video_model": "gemini-omni-1.1-flash"},
        ],
    })
    assert episode.status_code == 201, episode.text
    production = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
    )
    assert production.status_code == 201, production.text
    run_id = production.json()["production_id"]
    assert client.post(f"/api/v1/productions/{run_id}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{run_id}/approve-characters").status_code == 200
    return series, run_id


def _funded_job(client):
    series, run_id = _make_reviewed_jobs(client)
    backend = OfflineSqliteLedger(
        client.app.state.db.path, offline_test_only=True,
    )
    assert len(prepare_shot_jobs(backend, run_id)) == 2
    column = backend.one(
        "SELECT column_id FROM projects WHERE id=?", (series,)
    )["column_id"]
    for scope, value in (
        ("column", column), ("series", series), ("provider", "google"),
    ):
        configure_policy(
            backend, scope, value, daily_limit_usd="1.00", max_active_jobs=2,
        )
    job = claim_next_job(backend, "offline-atomic-worker", production_id=run_id)
    assert job and job["status"] == "leased"
    reserve = reserve_job_budget(
        backend, job["id"], estimated_charge_usd="0.40",
    )
    assert reserve["status"] == "held"
    return backend, job["id"], reserve["id"]


def _get_state(backend, job_id, reservation_id):
    return {
        "job": backend.one(
            "SELECT status,generation_intent_recorded,provider_task_id,"
            "actual_vendor_charge_usd FROM shot_jobs WHERE id=?", (job_id,),
        ),
        "budget": backend.one(
            "SELECT status,reserved_usd,actual_usd,evidence_reference,reviewed_by "
            "FROM job_budget_reservations WHERE id=?", (reservation_id,),
        ),
        "job_event_count": backend.one(
            "SELECT COUNT(*) AS n FROM shot_job_events WHERE shot_job_id=?", (job_id,),
        )["n"],
        "budget_event_count": backend.one(
            "SELECT COUNT(*) AS n FROM budget_reservation_events WHERE reservation_id=?",
            (reservation_id,),
        )["n"],
    }


def test_generation_intent_and_its_audit_rollback_together(client, monkeypatch):
    import drama_factory.jobs.shots as shots_module

    backend, job_id, reservation_id = _funded_job(client)
    before = _get_state(backend, job_id, reservation_id)
    assert before["job"]["status"] == "leased"
    assert before["job"]["generation_intent_recorded"] == 0
    assert before["budget"]["status"] == "held"
    assert before["budget_event_count"] == 1

    with monkeypatch.context() as patch:
        def broken_event(*args, **kwargs):
            raise RuntimeError("synthetic job audit outage")
        patch.setattr(shots_module, "_event", broken_event)
        with pytest.raises(RuntimeError, match="synthetic job audit"):
            record_submission_intent(backend, job_id, "offline-atomic-worker")

    assert _get_state(backend, job_id, reservation_id) == before
    assert backend.one(
        "SELECT COUNT(*) AS n FROM shot_job_events "
        "WHERE shot_job_id=? AND action='generation_intent_recorded'",
        (job_id,),
    )["n"] == 0

    recovered = record_submission_intent(backend, job_id, "offline-atomic-worker")
    assert recovered["status"] == "submission_intent"
    assert recovered["generation_intent_recorded"] == 1
    after = _get_state(backend, job_id, reservation_id)
    assert after["job_event_count"] == before["job_event_count"] + 1
    assert after["budget"] == before["budget"]  # existing hold is not silently released
    with pytest.raises(ShotJobError):
        record_submission_intent(backend, job_id, "offline-atomic-worker")


def test_task_receipt_and_audit_rollback_prevents_duplicate_paid_intent(client, monkeypatch):
    import drama_factory.jobs.shots as shots_module

    backend, job_id, reserve_id = _funded_job(client)
    record_submission_intent(backend, job_id, "offline-atomic-worker")
    before = _get_state(backend, job_id, reserve_id)
    with monkeypatch.context() as patch:
        def broken_event(*args, **kwargs):
            raise RuntimeError("synthetic task receipt audit failure")
        patch.setattr(shots_module, "_event", broken_event)
        with pytest.raises(RuntimeError, match="synthetic task receipt"):
            record_submission(
                backend, job_id, "offline-atomic-worker", "tasks/offline-only-001",
            )
    assert _get_state(backend, job_id, reserve_id) == before
    assert before["job"]["provider_task_id"] is None
    assert before["job"]["generation_intent_recorded"] == 1
    # Error after intent must NOT reset the guard and allow paid re-generation.
    with pytest.raises(ShotJobError, match="generation intent"):
        record_submission(
            backend, job_id, "wrong-worker", "tasks/second-paid-task",
        )
    recorded = record_submission(
        backend, job_id, "offline-atomic-worker", "tasks/offline-only-001",
    )
    assert recorded["provider_task_id"] == "tasks/offline-only-001"
    assert recorded["status"] == "submitted"
    assert backend.one(
        "SELECT COUNT(*) AS n FROM shot_job_events "
        "WHERE shot_job_id=? AND action='provider_task_recorded'", (job_id,),
    )["n"] == 1
    with pytest.raises(ShotJobError):
        record_submission(
            backend, job_id, "offline-atomic-worker", "tasks/second-paid-task",
        )


def test_billing_reconciliation_audit_failure_undoes_two_updated_tables(
    client, monkeypatch,
):
    import drama_factory.jobs.budgets as budgets_module

    backend, job_id, reserve_id = _funded_job(client)
    record_submission_intent(backend, job_id, "offline-atomic-worker")
    before = _get_state(backend, job_id, reserve_id)
    assert before["budget"]["status"] == "held"
    assert before["budget"]["actual_usd"] is None
    assert before["job"]["actual_vendor_charge_usd"] is None

    with monkeypatch.context() as patch:
        def broken_event(*args, **kwargs):
            raise RuntimeError("synthetic billing audit failure")
        patch.setattr(budgets_module, "_event", broken_event)
        with pytest.raises(RuntimeError, match="synthetic billing audit"):
            record_operator_verified_charge(
                backend, job_id, amount_usd="0.55",
                evidence_reference="ORIGINAL-FAKE-INVOICE",
                reviewer="offline-test-reviewer",
            )

    assert _get_state(backend, job_id, reserve_id) == before
    reconciled = record_operator_verified_charge(
        backend, job_id, amount_usd="0.55",
        evidence_reference="ORIGINAL-FAKE-INVOICE",
        reviewer="offline-test-reviewer",
    )
    assert reconciled["status"] == "reconciled"
    assert reconciled["actual_usd"] == "0.55"
    after = _get_state(backend, job_id, reserve_id)
    assert after["job"]["actual_vendor_charge_usd"] == "0.55"
    assert after["budget_event_count"] == before["budget_event_count"] + 1
    with pytest.raises(BudgetDenied):
        record_operator_verified_charge(
            backend, job_id, amount_usd="0.55",
            evidence_reference="FAKE-REPEAT-INVOICE",
            reviewer="other-reviewer",
        )


def test_second_table_rejects_billing_write_without_partial_budget_commit(client):
    """DB-level injected failure AFTER reservation update, BEFORE job update."""
    backend, job_id, reserve_id = _funded_job(client)
    record_submission_intent(backend, job_id, "offline-atomic-worker")
    before = _get_state(backend, job_id, reserve_id)

    # A trigger in the *temporary isolated test ledger* rejects the second
    # real production UPDATE, after the budget reservation row was updated.
    # Production trigger/schema definitions remain unchanged.
    backend.exec("""
        CREATE TRIGGER pr31_test_fail_bill_job_update
        BEFORE UPDATE OF actual_vendor_charge_usd ON shot_jobs
        BEGIN
            SELECT RAISE(ABORT,'synthetic second-table failure');
        END
    """)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="synthetic second-table"):
            record_operator_verified_charge(
                backend, job_id, amount_usd="0.55",
                evidence_reference="FAIL-BEFORE-SECOND-TABLE",
                reviewer="offline-review",
            )
        assert _get_state(backend, job_id, reserve_id) == before
    finally:
        backend.exec("DROP TRIGGER pr31_test_fail_bill_job_update")

    reconciled = record_operator_verified_charge(
        backend, job_id, amount_usd="0.55",
        evidence_reference="NOW-APPROVED-ONCE",
        reviewer="offline-review",
    )
    assert reconciled["status"] == "reconciled"
    assert backend.one(
        "SELECT actual_vendor_charge_usd FROM shot_jobs WHERE id=?", (job_id,),
    )["actual_vendor_charge_usd"] == "0.55"


def test_two_billing_reviewers_compete_only_one_update_and_one_event(client):
    backend, job_id, reserve_id = _funded_job(client)
    record_submission_intent(backend, job_id, "offline-atomic-worker")
    start = Barrier(2)

    def reconcile(amount, reviewer):
        start.wait(timeout=15)
        try:
            result = record_operator_verified_charge(
                backend, job_id, amount_usd=amount,
                evidence_reference="FAKE-EVIDENCE-" + reviewer,
                reviewer=reviewer,
            )
            return ("committed", result["actual_usd"])
        except BudgetDenied:
            return ("rejected", None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(
            lambda values: reconcile(*values),
            [("0.45", "offline-reviewer-a"), ("0.60", "offline-reviewer-b")],
        ))

    assert sorted(item[0] for item in result) == ["committed", "rejected"]
    committed_amount = [amount for kind, amount in result if kind == "committed"][0]
    after = _get_state(backend, job_id, reserve_id)
    assert after["budget"]["status"] == "reconciled"
    assert after["budget"]["actual_usd"] == committed_amount
    assert after["job"]["actual_vendor_charge_usd"] == committed_amount
    assert after["budget_event_count"] == 2  # initial held + ONE reconciliation
    assert backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events "
        "WHERE reservation_id=? AND action='operator_entered_vendor_charge'",
        (reserve_id,),
    )["n"] == 1
    assert backend.one(
        "SELECT COUNT(*) AS n FROM shot_jobs WHERE id=? "
        "AND generation_intent_recorded=1", (job_id,),
    )["n"] == 1


def test_three_table_contract_is_only_local_and_cannot_authorize_turso(client):
    backend, job_id, reserve_id = _funded_job(client)
    assert backend.one(
        "SELECT COUNT(*) AS n FROM job_budget_reservations WHERE id=?",
        (reserve_id,),
    )["n"] == 1
    assert backend.one(
        "SELECT COUNT(*) AS n FROM shot_job_events WHERE shot_job_id=?",
        (job_id,),
    )["n"] >= 2  # prepared and claimed
    with pytest.raises(BudgetDenied):
        record_operator_verified_charge(
            backend, job_id, amount_usd="0.55",
            evidence_reference="MISSING-EXTERNAL-INTENT",
            reviewer="offline-review",
        )
    assert backend.one(
        "SELECT status FROM job_budget_reservations WHERE id=?", (reserve_id,),
    )["status"] == "held"
    # These checks run through OfflineSqliteLedger, not through any cloud SDK.
