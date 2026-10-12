"""Offline PR-31a: fail-closed inspection; no Turso, Drive or paid services."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from drama_factory.db import Database, DEFAULT_COLUMN_ID
from drama_factory.storage.migration_readiness import (
    MigrationInventoryError, inspect_local_sqlite, run_cli,
)


def seeded_database(tmp_path):
    path = tmp_path / "local" / "factory.sqlite3"
    Database(path)
    return path


def test_new_empty_schema_is_inspected_without_modification(tmp_path):
    source = seeded_database(tmp_path)
    before = hashlib.sha256(source.read_bytes()).digest()
    result = inspect_local_sqlite(source)
    after = hashlib.sha256(source.read_bytes()).digest()
    assert before == after
    assert result["mode"] == "local_sqlite_read_only"
    assert result["source_opened_read_only"] is True
    assert result["source_modified"] is False
    assert result["schema_compatible_with_current_ledger"] is True
    assert result["missing_required_tables"] == []
    assert result["incomplete_required_tables"] == []
    assert result["integrity_ok"] is True
    assert result["foreign_key_violation_count"] == 0
    assert result["offline_snapshot_checks_passed"] is True
    assert result["blockers"] == []
    assert all(value == 0 for value in result["risk_counts"].values())
    assert len(result["schema_fingerprint_sha256"]) == 64
    assert result["live_migration_authorized"] is False
    assert result["live_cutover_permitted"] is False
    assert len(result["unvalidated_remote_requirements"]) >= 4
    assert result["turso_connections"] == 0
    assert result["new_ai_model_generation_calls"] == 0


def test_missing_source_is_not_created(tmp_path):
    source = tmp_path / "not-created" / "source.sqlite"
    with pytest.raises(MigrationInventoryError, match="Existing"):
        inspect_local_sqlite(source)
    assert not source.exists()
    assert not source.parent.exists()


def _seed_risky_state(source):
    now = "2026-10-13T00:00:00+00:00"
    with sqlite3.connect(source) as db:
        db.execute(
            "INSERT INTO projects (id,title,premise,visual_style,ratio,created_at,column_id) "
            "VALUES (?,?,?,?,?,?,?)",
            ("series_fake", "UNIQUE_SECRET_PRODUCTION_TITLE", "secret script", "live_action",
             "9:16", now, DEFAULT_COLUMN_ID),
        )
        db.execute(
            "INSERT INTO episodes (id,project_id,episode_number,title,body_json,created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("episode_fake", "series_fake", 1, "SECRET_EPISODE", '{"dialogue":"secret"}', now),
        )
        db.execute(
            "INSERT INTO productions (id,episode_id,status,created_at,updated_at) "
            "VALUES (?,?,?,?,?)",
            ("production_fake", "episode_fake", "approved", now, now),
        )
        for jid, status, intent in (
            ("job_lease", "leased", 0),
            ("job_unknown", "submitted", 1),
        ):
            db.execute(
                "INSERT INTO shot_jobs "
                "(id,production_id,episode_id,series_id,shot_id,provider,model_id,"
                "input_sha256,idempotency_key,max_acknowledged_spend_usd,status,"
                "generation_intent_recorded,lease_owner,lease_expires_at,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (jid, "production_fake", "episode_fake", "series_fake",
                 "shot_" + jid, "google", "fake_model", "a" * 64,
                 "idempotency_" + jid, "1.00", status, intent,
                 "worker_private", "2026-10-20T00:00:00+00:00", now, now),
            )
        db.execute(
            "INSERT INTO job_budget_reservations "
            "(id,job_id,column_id,series_id,provider,day_utc,reserved_usd,"
            "status,policy_snapshot_json,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("reserve_fake", "job_unknown", DEFAULT_COLUMN_ID, "series_fake",
             "google", "2026-10-13", "1.00", "held", "{}", now, now),
        )
        db.execute(
            "INSERT INTO google_existing_files (job_id,file_id,recovery_active,bound_at)"
            " VALUES (?,?,?,?)",
            ("job_unknown", "fakeSensitiveDriveFile09876", 1, now),
        )
        db.commit()


def test_active_leases_provider_uncertainty_and_budget_holds_block(tmp_path):
    source = seeded_database(tmp_path)
    _seed_risky_state(source)
    before = source.read_bytes()
    result = inspect_local_sqlite(source)
    assert source.read_bytes() == before
    assert result["risk_counts"] == {
        "leased_jobs": 1,
        "uncertain_submission_jobs": 1,
        "unreconciled_vendor_intents": 1,
        "held_budget_reservations": 1,
        "active_google_recoveries": 1,
    }
    assert result["offline_snapshot_checks_passed"] is False
    assert set(result["blockers"]) == set(result["risk_counts"])
    assert result["live_cutover_permitted"] is False
    serialized = json.dumps(result)
    for secret in (
        "UNIQUE_SECRET_PRODUCTION_TITLE",
        "SECRET_EPISODE",
        "secret script",
        "fakeSensitiveDriveFile09876",
        "worker_private",
        "series_fake",
        str(source),
    ):
        assert secret not in serialized


def test_foreign_key_violations_block_without_repair(tmp_path):
    source = seeded_database(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute(
            "INSERT INTO episodes (id,project_id,episode_number,title,body_json,created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("bad_episode", "not_a_real_series", 1, "forbidden data", "{}", "today"),
        )
        db.commit()
    result = inspect_local_sqlite(source)
    assert result["foreign_key_violation_count"] == 1
    assert "source_foreign_key_violations" in result["blockers"]
    assert result["offline_snapshot_checks_passed"] is False
    # Merely inspecting does not delete/repair the orphan record.
    with sqlite3.connect(source) as db:
        assert db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 1


def test_unknown_schema_fails_closed_without_adding_tables(tmp_path):
    source = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE only_legacy (secret_text TEXT)")
        db.execute("INSERT INTO only_legacy VALUES ('not_to_be_printed')")
        db.commit()
    before = source.read_bytes()
    result = inspect_local_sqlite(source)
    assert result["schema_compatible_with_current_ledger"] is False
    assert "source_schema_incomplete" in result["blockers"]
    assert "shot_jobs" in result["missing_required_tables"]
    assert result["risk_counts"] is None
    assert result["live_cutover_permitted"] is False
    assert "not_to_be_printed" not in json.dumps(result)
    assert source.read_bytes() == before


def test_older_schema_with_missing_risk_column_fails_closed(tmp_path):
    source = seeded_database(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("DROP TABLE google_existing_files")
        db.execute("CREATE TABLE google_existing_files (job_id TEXT)")
        db.commit()
    result = inspect_local_sqlite(source)
    assert result["schema_compatible_with_current_ledger"] is False
    assert "google_existing_files" in result["incomplete_required_tables"]
    assert result["risk_counts"] is None
    assert "source_schema_incomplete" in result["blockers"]


def test_cli_confirmation_and_redacted_failures(tmp_path, capsys):
    source = seeded_database(tmp_path)
    assert run_cli(["--source", str(source), "--confirmation", "no"]) == 1
    failure = capsys.readouterr()
    assert failure.out == ""
    assert str(source) not in failure.err
    assert "details redacted" in failure.err
    assert run_cli([
        "--source", str(source),
        "--confirmation", "INSPECT_LOCAL_SQLITE_READ_ONLY",
    ]) == 0
    success = capsys.readouterr()
    assert success.err == ""
    assert json.loads(success.out)["live_cutover_permitted"] is False
    assert str(source) not in success.out


def test_no_remote_sdk_or_network_dependency_for_inspection(tmp_path, monkeypatch):
    import builtins

    source = seeded_database(tmp_path)
    original_import = builtins.__import__

    def forbid(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "googleapiclient", "PIL")):
            raise AssertionError("Unexpected external/optional SDK import: " + name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid)
    result = inspect_local_sqlite(source)
    assert result["offline_snapshot_checks_passed"] is True
    assert result["turso_connections"] == 0
