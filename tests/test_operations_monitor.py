"""Read-only, series-filtered operations snapshot. No external provider calls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from drama_factory.jobs.monitor import OperationsScopeError, production_operations
from drama_factory.jobs.shots import (
    prepare_shot_jobs, claim_next_job, record_submission_intent,
    record_submission, record_failure,
)
from drama_factory.jobs.budgets import configure_policy, reserve_job_budget
from drama_factory.jobs.google_recovery import bind_existing_google_file


def series_and_job(client, label: str, column_id=None):
    response = client.post("/api/v1/projects", json={
        "title": label, "premise": "Original monitored short drama",
        **({"column_id": column_id} if column_id is not None else {}),
    })
    assert response.status_code == 201, response.text
    sid = response.json()["series_id"]
    ep = client.post(f"/api/v1/projects/{sid}/episodes", json={
        "title": "Pilot", "episode_number": 1, "target_duration_seconds": 2,
        "shots": [{
            "shot_id": "S1", "duration_seconds": 2,
            "visual_description": "One short camera shot",
            "video_model": "gemini-omni-1.1-flash",
        }],
    })
    assert ep.status_code == 201, ep.text
    creation = client.post(
        f"/api/v1/episodes/{ep.json()['episode_id']}/productions"
    )
    assert creation.status_code == 201
    pid = creation.json()["production_id"]
    assert client.post(f"/api/v1/productions/{pid}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{pid}/approve-characters").status_code == 200
    job = prepare_shot_jobs(client.app.state.db, pid)[0]
    return sid, pid, job


def fund(db, series, job_id, *, amount="0.50"):
    column = db.one("SELECT column_id FROM projects WHERE id=?", (series,))["column_id"]
    for scope, value in (("column", column), ("series", series), ("provider", "google")):
        configure_policy(db, scope, value, daily_limit_usd="10.00", max_active_jobs=5)
    return reserve_job_budget(db, job_id, estimated_charge_usd=amount)


def test_column_and_series_scoped_operations_and_global_provider_budget(client):
    db = client.app.state.db
    a, _, a_job = series_and_job(client, "Drama A")
    b, _, b_job = series_and_job(client, "Drama B")
    column = db.one("SELECT column_id FROM projects WHERE id=?", (a,))["column_id"]
    first = claim_next_job(db, "worker_a", series_id=a)
    second = claim_next_job(db, "worker_b", series_id=b)
    assert first["id"] == a_job["id"] and second["id"] == b_job["id"]
    fund(db, a, a_job["id"])
    fund(db, b, b_job["id"])
    record_submission_intent(db, first["id"], "worker_a")
    record_submission(db, first["id"], "worker_a", "tasks/first-123")
    bind_existing_google_file(db, first["id"], "generated123", operator_reviewed=True)
    # Simulate an in-progress download; only the read-only report is under test.
    db.exec("UPDATE google_existing_files SET recovery_active=1 WHERE job_id=?",
            (first["id"],))
    record_submission_intent(db, second["id"], "worker_b")
    record_failure(db, second["id"], "HTTP acknowledgement lost", worker_id="worker_b")
    before = len(db.many("SELECT id FROM shot_job_events"))
    report = production_operations(db, column_id=column)
    after = len(db.many("SELECT id FROM shot_job_events"))
    assert before == after
    assert report["read_only"] and report["new_model_generation_calls"] == 0
    assert report["series_count"] == 2
    assert report["shot_job_totals"]["submitted"] == 1
    assert report["shot_job_totals"]["failed"] == 1
    assert report["alerts"]["vendor_charges_unverified"] == 2
    assert report["alerts"]["paid_submission_uncertain_manual_review"] == 1
    assert report["alerts"]["existing_provider_tasks_to_recover"] == 1
    assert report["alerts"]["video_downloads_locked"] == 1
    assert report["column_budgets"][0]["committed_usd"] == "1.00"
    assert report["provider_budgets_global"][0]["committed_usd"] == "1.00"
    assert report["provider_budgets_global"][0]["global_across_columns"] is True
    assert "generated123" not in str(report)
    assert "tasks/first-123" not in str(report)
    filtered = production_operations(db, series_id=a)
    assert filtered["series_count"] == 1
    assert filtered["alerts"]["vendor_charges_unverified"] == 1
    # Provider budgets still reflect the global provider total, not just Series A.
    assert filtered["provider_budgets_global"][0]["committed_usd"] == "1.00"


def test_cross_column_filter_disallows_cross_series_scope(client):
    col = client.post("/api/v1/columns", json={
        "slug": "monitor-col", "name": "Monitored column",
    })
    assert col.status_code == 201, col.text
    foreign_column = col.json()["column_id"]
    home, _, _ = series_and_job(client, "Home")
    remote, _, _ = series_and_job(client, "Remote", column_id=foreign_column)
    default_col = client.app.state.db.one(
        "SELECT column_id FROM projects WHERE id=?", (home,),
    )["column_id"]
    with pytest.raises(OperationsScopeError, match="outside selected column"):
        production_operations(client.app.state.db,
                              column_id=default_col, series_id=remote)
    result = production_operations(client.app.state.db, column_id=foreign_column)
    assert result["series_count"] == 1
    assert result["series"][0]["series_id"] == remote
    with pytest.raises(OperationsScopeError, match="does not exist"):
        production_operations(client.app.state.db, series_id="series_nonexistent")
    with pytest.raises(OperationsScopeError, match="does not exist"):
        production_operations(client.app.state.db, column_id="column_nonexistent")


def test_expired_lease_alert_and_naive_datetime_rejection(client):
    sid, _, job = series_and_job(client, "Late worker")
    db = client.app.state.db
    t0 = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
    claim_next_job(db, "worker_late", series_id=sid, lease_seconds=10, now=t0)
    snapshot = production_operations(db, series_id=sid,
                                     now=t0 + timedelta(seconds=11))
    assert snapshot["alerts"]["expired_worker_leases"] == 1
    assert snapshot["shot_job_totals"]["leased"] == 1
    with pytest.raises(OperationsScopeError, match="Aware"):
        production_operations(db, now=datetime(2026, 10, 12))


def test_empty_column_is_read_only_with_empty_totals(client):
    c = client.post("/api/v1/columns", json={
        "slug": "empty-monitor-col", "name": "Empty monitored column",
    })
    assert c.status_code == 201
    report = production_operations(
        client.app.state.db, column_id=c.json()["column_id"],
    )
    assert report["series_count"] == 0
    assert report["shot_job_totals"]["succeeded"] == 0
    assert report["alerts"]["vendor_charges_unverified"] == 0
    assert report["column_budgets"] == []
    assert report["provider_budgets_global"] == []
