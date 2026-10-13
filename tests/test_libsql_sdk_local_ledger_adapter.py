"""PR-31b2o0: existing shot/budget business funcs on REAL libsql SDK local DB."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from drama_factory.jobs.budgets import (
    BudgetDenied, configure_policy, record_operator_verified_charge,
    reserve_job_budget,
)
from drama_factory.jobs.shots import (
    ShotJobError, claim_next_job, prepare_shot_jobs,
    record_submission_intent,
)
from drama_factory.storage.ledger_backend_contract import (
    LedgerBackend, require_ledger_contract,
)
from drama_factory.storage.libsql_sdk_local_ledger import (
    LocalNativeLibsqlLedger, LocalSdkDenied,
    _MARKER_TABLE, _MARKER_VALUE,
)

libsql = pytest.importorskip("libsql")


def _mark_test_fixture(path):
    # TEST ONLY: this is intentionally not a library method, because a
    # general-purpose 'tag existing file' helper could mark a real DB.
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(
            f"CREATE TABLE {_MARKER_TABLE} (value TEXT PRIMARY KEY)"
        )
        conn.execute(
            f"INSERT INTO {_MARKER_TABLE} (value) VALUES (?)",
            (_MARKER_VALUE,),
        )
        conn.commit()


def _production(client):
    project = client.post("/api/v1/projects", json={
        "title": "Completely original local-only test story",
        "premise": "No provider requests",
    })
    assert project.status_code == 201, project.text
    series = project.json()["series_id"]
    episode = client.post(f"/api/v1/projects/{series}/episodes", json={
        "title": "Fake scene", "episode_number": 1, "target_duration_seconds": 4,
        "shots": [
            {"shot_id": "S01", "duration_seconds": 2,
             "visual_description": "A candle", "video_model": "gemini-omni-1.1-flash"},
            {"shot_id": "S02", "duration_seconds": 2,
             "visual_description": "The candle goes out",
             "video_model": "gemini-omni-1.1-flash"},
        ],
    })
    assert episode.status_code == 201, episode.text
    production = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
    )
    assert production.status_code == 201, production.text
    run = production.json()["production_id"]
    assert client.post(f"/api/v1/productions/{run}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code == 200
    return series, run


def _backend(client):
    file = client.app.state.db.path
    _mark_test_fixture(file)
    adapter = LocalNativeLibsqlLedger(file, offline_test_only=True)
    assert isinstance(adapter, LedgerBackend)
    assert require_ledger_contract(adapter) is adapter
    return adapter


def _ready(client):
    series, run = _production(client)
    backend = _backend(client)
    staged = prepare_shot_jobs(backend, run)
    assert len(staged) == 2
    column = backend.one(
        "SELECT column_id FROM projects WHERE id=?", (series,),
    )["column_id"]
    for scope, scope_id in (
        ("column", column), ("series", series), ("provider", "google"),
    ):
        configured = configure_policy(
            backend, scope, scope_id,
            daily_limit_usd="1.00", max_active_jobs=2,
        )
        assert configured["revision"] == 1
    job = claim_next_job(backend, "sdk-test-worker", production_id=run)
    assert job["status"] == "leased"
    reservation = reserve_job_budget(
        backend, job["id"], estimated_charge_usd="0.40",
    )
    assert reservation["status"] == "held"
    return backend, job["id"], reservation["id"]


def test_no_marker_no_access_to_existing_source_even_with_opt_in(client, tmp_path):
    file = client.app.state.db.path  # actual normal SQLite fixture, not marked
    with pytest.raises(LocalSdkDenied, match="offline SDK"):
        LocalNativeLibsqlLedger(file)
    previous = file.read_bytes()
    with pytest.raises(LocalSdkDenied, match="Unmarked"):
        LocalNativeLibsqlLedger(file, offline_test_only=True)
    assert file.read_bytes() == previous
    missing = tmp_path / "missing-db.sqlite"
    with pytest.raises(LocalSdkDenied, match="Existing"):
        LocalNativeLibsqlLedger(missing, offline_test_only=True)
    assert not missing.exists()
    with pytest.raises(LocalSdkDenied, match="local"):
        LocalNativeLibsqlLedger(
            "libsql://ai-short-drama-factory.turso.io",
            offline_test_only=True,
        )
    alias = tmp_path / "linked.sqlite"
    alias.symlink_to(file)
    with pytest.raises(LocalSdkDenied, match="symlink"):
        LocalNativeLibsqlLedger(alias, offline_test_only=True)


def test_native_sdk_named_mapping_supports_ordinal_keys_and_dict(client):
    _production(client)
    adapter = _backend(client)
    assert adapter.many("SELECT id FROM shot_jobs") == []
    with adapter.connection() as conn:
        row = conn.execute("SELECT ? AS status, ? AS cost", ("held", "0.40")).fetchone()
        assert row["status"] == row[0] == "held"
        assert row["cost"] == row[1] == "0.40"
        assert dict(row) == {"status": "held", "cost": "0.40"}
        assert list(row.keys()) == ["status", "cost"]
        assert len(row) == 2
        assert conn.execute("SELECT 1 WHERE 1=0").fetchone() is None
        assert conn.execute("SELECT 1 WHERE 1=0").fetchall() == []
        assert [dict(r) for r in conn.execute("SELECT 1 AS first").fetchall()] == [
            {"first": 1}
        ]
        with pytest.raises(LocalSdkDenied, match="duplicate"):
            conn.execute("SELECT 1 AS duplicate, 2 AS duplicate").fetchone()
    assert adapter.safety_metadata()["remote_concurrency_verified"] is False
    assert adapter.safety_metadata()["production_backend_switched"] is False
    assert adapter.safety_metadata()["paid_provider_calls"] == 0


def test_real_job_budget_intent_and_billing_functions_work_on_local_native_sdk(client):
    backend, job_id, reservation_id = _ready(client)
    assert backend.one(
        "SELECT COUNT(*) AS n FROM job_budget_reservations"
    )["n"] == 1
    assert backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events"
    )["n"] == 1
    intent = record_submission_intent(backend, job_id, "sdk-test-worker")
    assert intent["status"] == "submission_intent"
    assert intent["generation_intent_recorded"] == 1

    reconciled = record_operator_verified_charge(
        backend, job_id, amount_usd="0.55",
        evidence_reference="SYNTHETIC-SDK-RECEIPT",
        reviewer="offline-test-operator",
    )
    assert reconciled["status"] == "reconciled"
    assert reconciled["actual_usd"] == "0.55"
    assert backend.one(
        "SELECT actual_vendor_charge_usd AS amount FROM shot_jobs WHERE id=?",
        (job_id,),
    )["amount"] == "0.55"
    assert backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events "
        "WHERE reservation_id=? AND action='operator_entered_vendor_charge'",
        (reservation_id,),
    )["n"] == 1
    assert backend.one(
        "SELECT COUNT(*) AS n FROM shot_job_events "
        "WHERE shot_job_id=? AND action='generation_intent_recorded'",
        (job_id,),
    )["n"] == 1
    with pytest.raises(BudgetDenied):
        record_operator_verified_charge(
            backend, job_id, amount_usd="0.55",
            evidence_reference="DUPLICATE-RECEIPT",
            reviewer="other-reviewer",
        )


def test_real_sdk_rollback_of_charge_and_audit_does_not_lose_budget_hold(
    client, monkeypatch,
):
    import drama_factory.jobs.budgets as budgets

    backend, job_id, reservation_id = _ready(client)
    record_submission_intent(backend, job_id, "sdk-test-worker")
    before = backend.one(
        "SELECT status,actual_usd,evidence_reference FROM job_budget_reservations "
        "WHERE id=?", (reservation_id,),
    )
    budget_events = backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events "
        "WHERE reservation_id=?", (reservation_id,),
    )["n"]
    with monkeypatch.context() as patch:
        def reject_audit(*args, **kwargs):
            raise RuntimeError("offline synthetic audit injection")
        patch.setattr(budgets, "_event", reject_audit)
        with pytest.raises(RuntimeError, match="audit injection"):
            record_operator_verified_charge(
                backend, job_id, amount_usd="0.55",
                evidence_reference="SYNTHETIC-FAIL-RECEIPT",
                reviewer="offline-reviewer",
            )

    assert backend.one(
        "SELECT status,actual_usd,evidence_reference FROM job_budget_reservations "
        "WHERE id=?", (reservation_id,),
    ) == before
    assert backend.one(
        "SELECT actual_vendor_charge_usd AS amount FROM shot_jobs WHERE id=?",
        (job_id,),
    )["amount"] is None
    assert backend.one(
        "SELECT COUNT(*) AS n FROM budget_reservation_events "
        "WHERE reservation_id=?", (reservation_id,),
    )["n"] == budget_events


def test_real_sdk_rollback_of_job_claim_event_keeps_job_pending(client, monkeypatch):
    import drama_factory.jobs.shots as shots

    _, run = _production(client)
    backend = _backend(client)
    staged = prepare_shot_jobs(backend, run)
    first = staged[0]["id"]
    with monkeypatch.context() as patch:
        def reject_event(*args, **kwargs):
            raise RuntimeError("offline synthetic job-audit failure")
        patch.setattr(shots, "_event", reject_event)
        with pytest.raises(RuntimeError, match="job-audit"):
            claim_next_job(backend, "sdk-test-worker", production_id=run)
    record = backend.one(
        "SELECT status,attempts,lease_owner FROM shot_jobs WHERE id=?", (first,),
    )
    assert record == {"status": "pending", "attempts": 0, "lease_owner": None}
    assert backend.one(
        "SELECT COUNT(*) AS n FROM shot_job_events "
        "WHERE shot_job_id=? AND action='claimed'", (first,),
    )["n"] == 0


def test_native_sdk_adapter_never_loads_remote_connection_from_local_path(client):
    _production(client)
    backend = _backend(client)
    receipt = backend.safety_metadata()
    assert receipt["remote_txlab_connection_attempts"] == 0
    assert receipt["remote_sql_semantics_verified"] is False
    assert receipt["remote_concurrency_verified"] is False
    assert receipt["network_commit_recovery_verified"] is False
    assert receipt["production_backend_switched"] is False
    assert receipt["live_cutover_permitted"] is False
    assert "remote" not in json.dumps(backend.one("SELECT 1 AS synthetic"))
