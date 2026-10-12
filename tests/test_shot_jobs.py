"""Offline shot job ledger: strict series scope, idempotency, retries and audit."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from drama_factory.jobs.shots import (
    ShotJobError, claim_next_job, complete_submitted_job, list_job_events,
    list_stalled_jobs, prepare_shot_jobs, record_failure, record_submission,
    record_submission_intent, restore_failed_job, investigate_stale_job,
)


def make_production(client, label="A", *, approve=True):
    project = client.post("/api/v1/projects", json={
        "title": "Series " + label, "premise": "A fictional, entirely original plot",
    })
    assert project.status_code == 201
    series_id = project.json()["series_id"]
    actor = client.post(f"/api/v1/series/{series_id}/assets", json={
        "kind": "actor", "key": "lead", "specification": {
            "name": "Lead", "appearance": "dark hair",
            "identity_anchors": ["scarf"],
        },
    })
    assert actor.status_code == 201
    actor_id = actor.json()["asset_id"]
    episode = client.post(f"/api/v1/projects/{series_id}/episodes", json={
        "title": "Episode " + label, "episode_number": 1,
        "target_duration_seconds": 4,
        "shots": [
            {"shot_id": "S1", "duration_seconds": 2, "visual_description": "Opens door",
             "character_ids": [actor_id], "video_model": "gemini-omni-1.1-flash"},
            {"shot_id": "S2", "duration_seconds": 2, "visual_description": "Walks away",
             "character_ids": [actor_id], "video_model": "gemini-omni-1.1-flash"},
        ],
    })
    assert episode.status_code == 201, episode.text
    production = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
    )
    assert production.status_code == 201
    run_id = production.json()["production_id"]
    if approve:
        assert client.post(f"/api/v1/productions/{run_id}/approve-script").status_code == 200
        assert client.post(f"/api/v1/productions/{run_id}/approve-characters").status_code == 200
    return series_id, run_id, actor_id


def test_no_job_preparation_before_both_reviews(client):
    sid, run, _ = make_production(client, approve=False)
    db = client.app.state.db
    with pytest.raises(ShotJobError, match="approval"):
        prepare_shot_jobs(db, run)
    client.post(f"/api/v1/productions/{run}/approve-script")
    with pytest.raises(ShotJobError, match="approval"):
        prepare_shot_jobs(db, run)
    client.post(f"/api/v1/productions/{run}/approve-characters")
    jobs = prepare_shot_jobs(db, run)
    assert len(jobs) == 2
    assert all(job["series_id"] == sid for job in jobs)


def test_preparation_is_idempotent_and_auditable(client):
    _, run, _ = make_production(client)
    db = client.app.state.db
    original = prepare_shot_jobs(db, run)
    assert len(original) == 2
    copied = prepare_shot_jobs(db, run)
    assert copied == original
    assert original[0]["status"] == "pending"
    assert original[0]["attempts"] == 0
    assert original[0]["provider_task_id"] is None
    assert original[0]["actual_vendor_charge_usd"] is None
    assert len({j["idempotency_key"] for j in original}) == 2
    assert [e["action"] for e in list_job_events(db, original[0]["id"])] == ["prepared"]


def test_different_series_have_distinct_jobs_and_worker_filter(client):
    a, run_a, _ = make_production(client, "A")
    b, run_b, _ = make_production(client, "B")
    db = client.app.state.db
    prepare_shot_jobs(db, run_a)
    prepare_shot_jobs(db, run_b)
    claimed = claim_next_job(db, "worker-B", series_id=b)
    assert claimed["series_id"] == b
    assert claimed["production_id"] == run_b
    assert claim_next_job(db, "worker-A", series_id=a)["series_id"] == a
    assert len(db.many("SELECT id FROM shot_jobs WHERE series_id=?", (a,))) == 2
    assert len(db.many("SELECT id FROM shot_jobs WHERE series_id=?", (b,))) == 2


def test_provider_task_id_prevents_another_paid_submission(client):
    _, run, _ = make_production(client)
    db = client.app.state.db
    job = prepare_shot_jobs(db, run)[0]
    first = claim_next_job(db, "worker-A")
    assert first["id"] == job["id"]
    intent = record_submission_intent(db, job["id"], "worker-A")
    assert intent["status"] == "submission_intent"
    assert intent["generation_intent_recorded"] == 1
    submitted = record_submission(db, job["id"], "worker-A", "tasks/provider001")
    assert submitted["status"] == "submitted"
    assert submitted["attempts"] == 1
    assert submitted["provider_task_id"] == "tasks/provider001"
    assert claim_next_job(db, "worker-B")["id"] != job["id"]
    with pytest.raises(ShotJobError, match="not leased"):
        record_submission(db, job["id"], "worker-A", "tasks/double-paid")
    failed = record_failure(db, job["id"], "Video download failed", worker_id="worker-A")
    assert failed["status"] == "failed"
    with pytest.raises(ShotJobError, match="Human operator"):
        restore_failed_job(db, job["id"], operator_reviewed=False)
    restored = restore_failed_job(db, job["id"], operator_reviewed=True)
    assert restored["status"] == "submitted"
    assert restored["provider_task_id"] == "tasks/provider001"
    assert restored["attempts"] == 1
    completed = complete_submitted_job(
        db, job["id"], provider_task_id="tasks/provider001",
        result_sha256="a" * 64, result_path="series/test/video123.mp4",
    )
    assert completed["status"] == "succeeded"
    assert completed["actual_vendor_charge_usd"] is None
    assert [e["action"] for e in list_job_events(db, job["id"])] == [
        "prepared", "claimed", "generation_intent_recorded",
        "provider_task_recorded", "failed",
        "resume_existing_provider_task", "result_recorded",
    ]


def test_manual_retry_only_before_provider_submission(client):
    _, run, _ = make_production(client)
    db = client.app.state.db
    prepare_shot_jobs(db, run, max_attempts=2)
    job = claim_next_job(db, "worker1")
    record_failure(db, job["id"], "Local environment unavailable", worker_id="worker1")
    restored = restore_failed_job(db, job["id"], operator_reviewed=True)
    assert restored["status"] == "pending"
    second = claim_next_job(db, "worker2")
    assert second["id"] == job["id"]
    assert second["attempts"] == 2
    record_failure(db, job["id"], "Local validation failed again", worker_id="worker2")
    with pytest.raises(ShotJobError, match="exhausted"):
        restore_failed_job(db, job["id"], operator_reviewed=True)


def test_lease_expiry_never_auto_requeues_and_no_second_claim(client):
    _, run, _ = make_production(client)
    db = client.app.state.db
    prepare_shot_jobs(db, run)
    moment = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
    leased = claim_next_job(db, "worker1", now=moment, lease_seconds=10)
    old = list_stalled_jobs(db, now=moment + timedelta(seconds=11))
    assert [j["id"] for j in old] == [leased["id"]]
    with pytest.raises(ShotJobError, match="expired"):
        record_submission(db, leased["id"], "worker1", "tasks/late", now=moment+timedelta(seconds=11))
    other = claim_next_job(db, "worker2", now=moment + timedelta(seconds=11))
    assert other["id"] != leased["id"]
    assert db.one("SELECT status FROM shot_jobs WHERE id=?", (leased["id"],))["status"] == "leased"


def test_tampered_series_asset_is_rejected(client):
    a, run_a, actor_a = make_production(client, "A")
    b, _, actor_b = make_production(client, "B")
    db = client.app.state.db
    job = db.one("SELECT body_json,id FROM episodes WHERE project_id=?", (a,))
    episode = json.loads(job["body_json"])
    episode["shots"][0]["character_ids"] = [actor_b]
    db.exec("UPDATE episodes SET body_json=? WHERE id=?", (json.dumps(episode), job["id"]))
    with pytest.raises(ShotJobError, match="outside its own series"):
        prepare_shot_jobs(db, run_a)
    assert db.many("SELECT * FROM shot_jobs WHERE production_id=?", (run_a,)) == []


def test_mutated_shot_cannot_reuse_existing_idempotency_key(client):
    sid, run, _ = make_production(client)
    db = client.app.state.db
    prepare_shot_jobs(db, run)
    episode = db.one("SELECT id,body_json FROM episodes WHERE project_id=?", (sid,))
    body = json.loads(episode["body_json"])
    body["shots"][0]["visual_description"] = "Different prompt and shot content"
    db.exec("UPDATE episodes SET body_json=? WHERE id=?", (json.dumps(body), episode["id"]))
    with pytest.raises(ShotJobError, match="immutable"):
        prepare_shot_jobs(db, run)
    assert len(db.many("SELECT id FROM shot_jobs WHERE production_id=?", (run,))) == 2


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity", "1.234", "101", "invalid"])
def test_bad_spend_acknowledgments_fail_without_side_effect(client, amount):
    _, run, _ = make_production(client)
    db = client.app.state.db
    with pytest.raises(ShotJobError):
        prepare_shot_jobs(db, run, max_acknowledged_spend_usd=amount)
    assert db.many("SELECT * FROM shot_jobs WHERE production_id=?", (run,)) == []


def test_event_log_is_immutable_even_under_direct_sql(client):
    _, run, _ = make_production(client)
    db = client.app.state.db
    job = prepare_shot_jobs(db, run)[0]
    evt = list_job_events(db, job["id"])[0]
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.exec("UPDATE shot_job_events SET action='changed' WHERE id=?", (evt["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.exec("DELETE FROM shot_job_events WHERE id=?", (evt["id"],))


def test_uncertain_paid_request_is_quarantined_if_no_task_id(client):
    _, run, _ = make_production(client)
    db = client.app.state.db
    prepare_shot_jobs(db, run)
    leased = claim_next_job(db, "worker1")
    record_submission_intent(db, leased["id"], "worker1")
    record_failure(db, leased["id"], "Network died after submission; no task ID",
                   worker_id="worker1")
    with pytest.raises(ShotJobError, match="may have been billed"):
        restore_failed_job(db, leased["id"], operator_reviewed=True)
    assert db.one("SELECT status FROM shot_jobs WHERE id=?", (leased["id"],))["status"] == "failed"


def test_expired_submission_intent_cannot_auto_retry(client):
    _, run, _ = make_production(client)
    db = client.app.state.db
    prepare_shot_jobs(db, run)
    t0 = datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)
    leased = claim_next_job(db, "worker1", now=t0, lease_seconds=10)
    record_submission_intent(db, leased["id"], "worker1", now=t0)
    stale = list_stalled_jobs(db, now=t0 + timedelta(seconds=11))
    assert leased["id"] in {x["id"] for x in stale}
    with pytest.raises(ShotJobError, match="review"):
        investigate_stale_job(db, leased["id"], operator_reviewed=False, now=t0+timedelta(seconds=11))
    flagged = investigate_stale_job(
        db, leased["id"], operator_reviewed=True, now=t0+timedelta(seconds=11),
    )
    assert flagged["status"] == "failed"
    assert flagged["generation_intent_recorded"] == 1
    with pytest.raises(ShotJobError, match="may have been billed"):
        restore_failed_job(db, leased["id"], operator_reviewed=True)
