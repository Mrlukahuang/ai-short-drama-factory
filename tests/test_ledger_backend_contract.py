"""PR-31b1 backend seam: run real production functions against isolated facade."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from drama_factory.jobs.budgets import BudgetDenied, configure_policy, reserve_job_budget
from drama_factory.jobs.shots import claim_next_job, prepare_shot_jobs
from drama_factory.storage.ledger_backend_contract import (
    LedgerBackend, OfflineAdapterDenied, OfflineSqliteLedger,
    export_offline_contract_metadata, require_ledger_contract,
)


def make_two_shot_production(client):
    p = client.post("/api/v1/projects", json={
        "title": "Offline candidate transaction", "premise": "Fictional original story",
    })
    assert p.status_code == 201
    series = p.json()["series_id"]
    e = client.post(f"/api/v1/projects/{series}/episodes", json={
        "title": "Trial", "episode_number": 1, "target_duration_seconds": 4,
        "shots": [
            {"shot_id": "shot1", "duration_seconds": 2,
             "visual_description": "Opening curtain", "video_model": "gemini-omni-1.1-flash"},
            {"shot_id": "shot2", "duration_seconds": 2,
             "visual_description": "Curtain closes", "video_model": "gemini-omni-1.1-flash"},
        ],
    })
    assert e.status_code == 201
    run = client.post(f"/api/v1/episodes/{e.json()['episode_id']}/productions")
    assert run.status_code == 201
    production = run.json()["production_id"]
    assert client.post(f"/api/v1/productions/{production}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{production}/approve-characters").status_code == 200
    return series, production


def candidate(client):
    source = client.app.state.db
    adapter = OfflineSqliteLedger(source.path, offline_test_only=True)
    assert isinstance(adapter, LedgerBackend)
    assert require_ledger_contract(adapter) is adapter
    return adapter


def test_candidate_explicit_offline_only_and_no_schema_creation(tmp_path):
    missing = tmp_path / "do-not-create" / "production.sqlite3"
    with pytest.raises(OfflineAdapterDenied, match="approval"):
        OfflineSqliteLedger(missing)
    with pytest.raises(OfflineAdapterDenied, match="Existing"):
        OfflineSqliteLedger(missing, offline_test_only=True)
    with pytest.raises(OfflineAdapterDenied, match="local"):
        OfflineSqliteLedger("libsql://ai-short-drama-factory-example.turso.io",
                            offline_test_only=True)
    assert not missing.exists()
    assert not missing.parent.exists()
    metadata = export_offline_contract_metadata()
    assert metadata["remote_concurrency_verified"] is False
    assert metadata["remote_sql_transaction_verified"] is False
    assert metadata["production_backend_switched"] is False
    assert metadata["live_migration_authorized"] is False
    assert metadata["turso_connections"] == 0


def test_candidate_real_parallel_claims_preserve_unique_lease_and_audit(client):
    _, run = make_two_shot_production(client)
    adapter = candidate(client)
    staged = prepare_shot_jobs(adapter, run)
    assert len(staged) == 2
    barrier = Barrier(8)

    def claim(i):
        barrier.wait(timeout=12)
        return claim_next_job(adapter, f"adapter-worker-{i}", production_id=run)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(claim, range(8)))

    claimed = [item for item in results if item is not None]
    assert len(claimed) == 2
    assert {item["id"] for item in claimed} == {item["id"] for item in staged}
    assert {item["lease_owner"] for item in claimed} == {
        f"adapter-worker-{i}" for i, item in enumerate(results) if item is not None
    }
    assert adapter.one("SELECT COUNT(*) AS n FROM shot_job_events WHERE action='claimed'")["n"] == 2
    assert adapter.one("SELECT COUNT(*) AS n FROM shot_jobs WHERE attempts>1")["n"] == 0


def test_candidate_parallel_budget_holds_cannot_double_spend(client):
    series, run = make_two_shot_production(client)
    adapter = candidate(client)
    prepared = prepare_shot_jobs(adapter, run)
    assert len(prepared) == 2
    column = adapter.one("SELECT column_id FROM projects WHERE id=?", (series,))["column_id"]
    for scope, name in (("column", column), ("series", series), ("provider", "google")):
        configure_policy(adapter, scope, name, daily_limit_usd="0.60",
                         max_active_jobs=2)
    first = claim_next_job(adapter, "adapter-spend-a", production_id=run)
    second = claim_next_job(adapter, "adapter-spend-b", production_id=run)
    barrier = Barrier(2)

    def reserve(job):
        barrier.wait(timeout=12)
        try:
            return reserve_job_budget(
                adapter, job["id"], estimated_charge_usd="0.40",
            )["status"]
        except BudgetDenied:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(reserve, (first, second)))
    assert sorted(result) == ["denied", "held"]
    assert adapter.one(
        "SELECT COUNT(*) AS n FROM job_budget_reservations"
    )["n"] == 1
    assert adapter.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events"
    )["n"] == 1
    assert adapter.one(
        "SELECT COUNT(*) AS n FROM shot_jobs WHERE generation_intent_recorded=1"
    )["n"] == 0


def test_candidate_transaction_context_rolls_back_if_audit_event_fails(client, monkeypatch):
    import drama_factory.jobs.shots as shots

    _, run = make_two_shot_production(client)
    adapter = candidate(client)
    staged = prepare_shot_jobs(adapter, run)

    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(shots, "_event", fail)
    with pytest.raises(RuntimeError, match="injected audit"):
        claim_next_job(adapter, "adapter-audit", production_id=run)
    state = adapter.one(
        "SELECT status,attempts,lease_owner FROM shot_jobs WHERE id=?",
        (staged[0]["id"],),
    )
    assert state == {"status": "pending", "attempts": 0, "lease_owner": None}
    assert adapter.one(
        "SELECT COUNT(*) AS n FROM shot_job_events WHERE shot_job_id=? AND action='claimed'",
        (staged[0]["id"],),
    )["n"] == 0


def test_structural_contract_refuses_incomplete_adapter():
    with pytest.raises(OfflineAdapterDenied, match="contract missing"):
        require_ledger_contract(object())
