"""Offline PR-31c0 backup/recovery integrity without Turso or real source data."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from drama_factory.db import Database, DEFAULT_COLUMN_ID
from drama_factory.storage.snapshot_rehearsal import (
    SnapshotRehearsalDenied, _logical_digest, rehearse_local_snapshot,
)


def source_file(tmp_path):
    source = tmp_path / "original.sqlite"
    Database(source)
    return source


def test_snapshot_restores_full_logical_database_and_keeps_original(tmp_path):
    source = source_file(tmp_path)
    conn = sqlite3.connect(source)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "INSERT INTO projects (id,title,premise,visual_style,ratio,created_at,column_id) "
            "VALUES (?,?,?,?,?,?,?)",
            ("test-series", "SECRET ORIGINAL SERIES NAME", "PRIVATE PLOT",
             "live_action", "9:16", "2026-10-13T00:00:00+00:00", DEFAULT_COLUMN_ID),
        )
        conn.commit()
    finally:
        conn.close()

    original_bytes = source.read_bytes()
    backup, restored = tmp_path / "backup.sqlite", tmp_path / "recovered.sqlite"
    outcome = rehearse_local_snapshot(
        source, backup, restored, operator_approved=True, offline_rehearsal_only=True,
    )
    assert source.read_bytes() == original_bytes
    assert outcome["original_opened_read_only"] is True
    assert outcome["backup_and_restore_logically_equal"] is True
    assert outcome["table_count"] >= 12
    assert outcome["row_count_total"] >= 2
    assert len(outcome["schema_sha256"]) == 64
    assert len(outcome["logical_sha256"]) == 64
    assert outcome["live_turso_connections"] == 0
    assert outcome["source_data_uploaded"] is False
    assert outcome["remote_transaction_verified"] is False
    assert outcome["remote_concurrency_verified"] is False
    assert outcome["production_backend_switched"] is False
    assert outcome["live_cutover_permitted"] is False
    assert outcome["new_ai_model_generation_calls"] == 0
    assert (backup.stat().st_mode & 0o777) == 0o600
    assert (restored.stat().st_mode & 0o777) == 0o600
    with sqlite3.connect(restored) as con:
        assert con.execute("SELECT title FROM projects WHERE id='test-series'").fetchone()[0] == "SECRET ORIGINAL SERIES NAME"
    assert _logical_digest(backup) == _logical_digest(restored)
    receipt = json.dumps(outcome)
    for secret in ("PRIVATE PLOT", "SECRET ORIGINAL SERIES NAME", "test-series", str(source)):
        assert secret not in receipt


def test_all_approval_and_existence_checks_before_file_creation(tmp_path):
    source = source_file(tmp_path)
    backup, restored = tmp_path / "b.sqlite", tmp_path / "r.sqlite"
    for opts in (
        {},
        {"operator_approved": True},
        {"offline_rehearsal_only": True},
    ):
        with pytest.raises(SnapshotRehearsalDenied, match="approval"):
            rehearse_local_snapshot(source, backup, restored, **opts)
    assert not backup.exists()
    assert not restored.exists()
    with pytest.raises(SnapshotRehearsalDenied, match="existing regular"):
        rehearse_local_snapshot(
            tmp_path / "missing.db", backup, restored,
            operator_approved=True, offline_rehearsal_only=True,
        )
    assert not (tmp_path / "missing.db").exists()
    assert not backup.exists()
    assert not restored.exists()


def test_never_overwrites_existing_file_or_aliases_source(tmp_path):
    source = source_file(tmp_path)
    existing_backup = tmp_path / "existing.sqlite"
    existing_backup.write_bytes(b"DO_NOT_ERASE")
    target = tmp_path / "restore.sqlite"
    with pytest.raises(SnapshotRehearsalDenied, match="Refusing"):
        rehearse_local_snapshot(
            source, existing_backup, target,
            operator_approved=True, offline_rehearsal_only=True,
        )
    assert existing_backup.read_bytes() == b"DO_NOT_ERASE"
    assert not target.exists()
    with pytest.raises(SnapshotRehearsalDenied, match="Refusing"):
        rehearse_local_snapshot(
            source, source, target, operator_approved=True, offline_rehearsal_only=True,
        )
    assert not target.exists()
    with pytest.raises(SnapshotRehearsalDenied, match="differ"):
        rehearse_local_snapshot(
            source, target, target, operator_approved=True, offline_rehearsal_only=True,
        )
    assert not target.exists()


def test_refuses_symlinks_and_existing_restore(tmp_path):
    source = source_file(tmp_path)
    backup = tmp_path / "backup.sqlite"
    restore = tmp_path / "restore.sqlite"
    alias = tmp_path / "alias.sqlite"
    alias.symlink_to(source)
    with pytest.raises(SnapshotRehearsalDenied, match="existing regular"):
        rehearse_local_snapshot(
            alias, backup, restore, operator_approved=True, offline_rehearsal_only=True,
        )
    restore.symlink_to(source)
    with pytest.raises(SnapshotRehearsalDenied, match="Refusing"):
        rehearse_local_snapshot(
            source, backup, restore, operator_approved=True, offline_rehearsal_only=True,
        )
    assert not backup.exists()
    assert source.is_file()


def test_unknown_schema_or_foreign_key_violation_is_not_backed_up(tmp_path):
    source = tmp_path / "unknown.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE unrelated (txt TEXT)")
        conn.execute("INSERT INTO unrelated VALUES ('confidential')")
    backup, restored = tmp_path / "backup.db", tmp_path / "restore.db"
    with pytest.raises(SnapshotRehearsalDenied, match="schema and integrity"):
        rehearse_local_snapshot(
            source, backup, restored,
            operator_approved=True, offline_rehearsal_only=True,
        )
    assert not backup.exists()
    assert not restored.exists()


def test_recovery_checksum_corruption_is_detected(tmp_path):
    source = source_file(tmp_path)
    backup = tmp_path / "backup.db"
    recovered = tmp_path / "recovered.db"
    outcome = rehearse_local_snapshot(
        source, backup, recovered,
        operator_approved=True, offline_rehearsal_only=True,
    )
    with sqlite3.connect(recovered) as conn:
        conn.execute(
            "UPDATE columns SET name='tampered-backup' WHERE id=?",
            (DEFAULT_COLUMN_ID,),
        )
    assert _logical_digest(recovered)["logical_sha256"] != outcome["logical_sha256"]
    assert _logical_digest(backup) != _logical_digest(recovered)


def test_does_not_import_cloud_clients(tmp_path, monkeypatch):
    import builtins

    source = source_file(tmp_path)
    imported = builtins.__import__
    def forbid_cloud(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "googleapiclient")):
            raise AssertionError("Unexpected cloud client import")
        return imported(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", forbid_cloud)
    result = rehearse_local_snapshot(
        source, tmp_path / "offline-b.db", tmp_path / "offline-r.db",
        operator_approved=True, offline_rehearsal_only=True,
    )
    assert result["live_turso_connections"] == 0
