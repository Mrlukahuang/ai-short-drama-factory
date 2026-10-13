"""PR-31b2j: test true production-schema safety constraints, locally only."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing

import pytest

from drama_factory.db import Database, DEFAULT_COLUMN_ID
from drama_factory.storage.critical_ledger_schema import (
    CriticalSchemaDenied, inspect_critical_local_schema,
)


def _source(tmp_path):
    path = tmp_path / "critical-test-ledger.sqlite"
    Database(path)  # creates only disposable test schema
    return path


def _check(path):
    return inspect_critical_local_schema(path, offline_review_only=True)


def test_real_schema_has_all_job_and_budget_protections(tmp_path):
    path = _source(tmp_path)
    before = path.read_bytes()
    receipt = _check(path)
    assert path.read_bytes() == before
    assert receipt["local_schema_safety_checks_passed"] is True
    assert receipt["blockers"] == []
    assert receipt["checked_critical_tables"] == 5
    assert receipt["checked_explicit_indexes"] == 5
    assert receipt["checked_append_only_triggers"] == 4
    assert receipt["checked_foreign_key_edges"] == 5
    assert receipt["checked_unique_rules"] == 2
    assert len(receipt["schema_fingerprint_sha256"]) == 64
    assert receipt["remote_transaction_atomicity_verified"] is False
    assert receipt["real_remote_schema_import_verified"] is False
    assert receipt["remote_multi_worker_concurrency_verified"] is False
    assert receipt["production_backend_switched"] is False
    assert receipt["live_cutover_permitted"] is False
    assert receipt["turso_connections"] == 0
    assert receipt["paid_provider_calls"] == 0


def test_schema_digest_is_independent_of_confidential_business_rows(tmp_path):
    path = _source(tmp_path)
    before = _check(path)["schema_fingerprint_sha256"]
    with closing(sqlite3.connect(path)) as db:
        db.execute(
            "INSERT INTO projects (id,title,premise,visual_style,ratio,created_at,column_id) "
            "VALUES (?,?,?,?,?,?,?)",
            ("private-original-id", "SUPER PRIVATE ORIGINAL PLOT",
             "CREATIVE STORY PROTECTED", "live_action", "9:16",
             "2026-10-13T00:00:00+00:00", DEFAULT_COLUMN_ID),
        )
        db.commit()
    receipt = _check(path)
    assert receipt["schema_fingerprint_sha256"] == before
    payload = json.dumps(receipt, sort_keys=True)
    for secret in (
        "SUPER PRIVATE ORIGINAL PLOT", "CREATIVE STORY PROTECTED",
        "private-original-id", str(path),
    ):
        assert secret not in payload


def test_disappeared_provider_task_index_fails_closed(tmp_path):
    path = _source(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP INDEX idx_shot_jobs_provider_task")
        db.commit()
    receipt = _check(path)
    assert receipt["local_schema_safety_checks_passed"] is False
    assert "missing_index_idx_shot_jobs_provider_task" in receipt["blockers"]
    assert receipt["live_cutover_permitted"] is False


def test_same_name_nonunique_index_is_not_accepted(tmp_path):
    path = _source(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP INDEX idx_shot_jobs_provider_task")
        db.execute(
            "CREATE INDEX idx_shot_jobs_provider_task "
            "ON shot_jobs(provider,provider_task_id)"
        )
        db.commit()
    receipt = _check(path)
    assert receipt["local_schema_safety_checks_passed"] is False
    assert "invalid_unique_partial_provider_task_index" in receipt["blockers"]


def test_missing_or_fake_audit_trigger_does_not_pass(tmp_path):
    path = _source(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TRIGGER shot_job_events_immutable_delete")
        db.execute("DROP TRIGGER budget_events_immutable_update")
        # Same-name no-op trigger must never be accepted as append-only.
        db.execute(
            "CREATE TRIGGER budget_events_immutable_update "
            "BEFORE UPDATE ON budget_reservation_events "
            "BEGIN SELECT 1; END"
        )
        db.commit()
    receipt = _check(path)
    assert receipt["local_schema_safety_checks_passed"] is False
    assert "missing_append_only_trigger_shot_job_events_immutable_delete" in receipt["blockers"]
    assert "invalid_append_only_trigger_budget_events_immutable_update" in receipt["blockers"]


def test_missing_fk_and_unique_constraint_detected_in_incomplete_schema(tmp_path):
    path = tmp_path / "not_a_production_schema.sqlite"
    with closing(sqlite3.connect(path)) as db:
        db.execute(
            "CREATE TABLE shot_jobs (id TEXT PRIMARY KEY, idempotency_key TEXT)"
        )
        db.execute(
            "CREATE TABLE job_budget_reservations (id TEXT PRIMARY KEY,job_id TEXT)"
        )
        db.execute(
            "CREATE TABLE budget_reservation_events (id TEXT PRIMARY KEY,"
            "reservation_id TEXT)"
        )
        db.commit()
    result = _check(path)
    blockers = result["blockers"]
    assert "missing_unique_job_idempotency" in blockers
    assert "missing_unique_reservation_per_job" in blockers
    assert "missing_foreign_key_job_budget_reservations_job_id" in blockers
    assert "missing_foreign_key_budget_reservation_events_reservation_id" in blockers
    assert result["local_schema_safety_checks_passed"] is False


def test_actual_fk_orphan_is_a_blocker_not_repaired(tmp_path):
    path = _source(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute(
            "INSERT INTO shot_job_events VALUES (?,?,?,?,?,?,?)",
            ("event-private", "does-not-exist", "claimed", "pending",
             "leased", "{}", "2026-10-13T00:00:00+00:00"),
        )
        db.commit()
    before = path.read_bytes()
    receipt = _check(path)
    assert path.read_bytes() == before
    assert receipt["local_schema_safety_checks_passed"] is False
    assert "foreign_key_data_violation" in receipt["blockers"]
    assert "event-private" not in json.dumps(receipt)


def test_existing_only_operator_gate_and_no_remote_urls(tmp_path):
    target = tmp_path / "must-not-create.sqlite"
    with pytest.raises(CriticalSchemaDenied, match="review"):
        inspect_critical_local_schema(target)
    with pytest.raises(CriticalSchemaDenied, match="Existing"):
        _check(target)
    assert not target.exists()
    with pytest.raises(CriticalSchemaDenied, match="Local"):
        _check("libsql://ai-short-drama-factory-txlab-x.turso.io")
    source = _source(tmp_path)
    alias = tmp_path / "source-symlink.sqlite"
    alias.symlink_to(source)
    with pytest.raises(CriticalSchemaDenied, match="non-symlink"):
        _check(alias)


def test_schema_reader_has_no_cloud_sdk_dependency(tmp_path, monkeypatch):
    import builtins

    source = _source(tmp_path)
    original = builtins.__import__

    def forbid_remote(name, *args, **kwargs):
        if name.startswith(("libsql", "googleapiclient", "turso_serverless")):
            raise AssertionError("Unexpected remote client import")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid_remote)
    result = _check(source)
    assert result["local_schema_safety_checks_passed"] is True
    assert result["turso_connections"] == 0
