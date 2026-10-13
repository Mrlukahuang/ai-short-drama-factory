"""PR-31c1: local, sanitized cutover evidence can NEVER unlock production."""
from __future__ import annotations

import json
import sqlite3

import pytest

from drama_factory.db import Database, DEFAULT_COLUMN_ID
from drama_factory.storage.cutover_evidence import (
    OfflineCutoverDenied, inspect_cutover_evidence,
)
from drama_factory.storage.snapshot_rehearsal import rehearse_local_snapshot


def make_triplet(tmp_path):
    source = tmp_path / "source.db"
    Database(source)
    with sqlite3.connect(source) as conn:
        conn.execute(
            "UPDATE columns SET name=? WHERE id=?",
            ("PRIVATE CHARACTER REFERENCE", DEFAULT_COLUMN_ID),
        )
    backup = tmp_path / "backup.db"
    recovered = tmp_path / "restore.db"
    rehearsal = rehearse_local_snapshot(
        source, backup, recovered,
        operator_approved=True, offline_rehearsal_only=True,
    )
    assert rehearsal["backup_and_restore_logically_equal"] is True
    return source, backup, recovered


def review(paths):
    return inspect_cutover_evidence(
        *paths, operator_approved=True, offline_review_only=True,
    )


def test_three_way_match_does_not_enable_cutover(tmp_path):
    paths = make_triplet(tmp_path)
    before = [p.read_bytes() for p in paths]
    result = review(paths)
    after = [p.read_bytes() for p in paths]
    assert before == after
    assert result["mode"] == "offline_cutover_evidence_review_only"
    assert result["local_snapshot_and_restore_match"] is True
    assert result["source_matches_snapshot_during_review"] is True
    assert result["offline_evidence_checks_passed"] is True
    assert result["blockers"] == []
    assert all(x == 0 for x in result["source_risk_counts"].values())
    assert len(result["report_sha256"]) == 64
    assert len(result["snapshot_logical_sha256"]) == 64
    for name in (
        "fleet_writers_fenced",
        "provider_intents_reconciled_externally",
        "remote_transactions_verified",
        "remote_concurrency_verified",
        "remote_schema_and_import_verified",
        "rollback_on_real_workers_rehearsed",
        "live_cutover_authorized",
        "live_cutover_permitted",
        "source_modified",
        "destination_files_modified",
    ):
        assert result[name] is False
    assert result["turso_connections"] == 0
    assert result["paid_provider_calls"] == 0
    dumped = json.dumps(result, sort_keys=True)
    assert "PRIVATE CHARACTER REFERENCE" not in dumped
    assert "source.db" not in dumped


def test_source_changes_after_snapshot_blocks_evidence(tmp_path):
    paths = make_triplet(tmp_path)
    with sqlite3.connect(paths[0]) as conn:
        conn.execute(
            "UPDATE columns SET name='PRIVATE LATER EDIT' WHERE id=?",
            (DEFAULT_COLUMN_ID,),
        )
    result = review(paths)
    assert result["local_snapshot_and_restore_match"] is True
    assert result["source_matches_snapshot_during_review"] is False
    assert result["offline_evidence_checks_passed"] is False
    assert "source_snapshot_mismatch" in result["blockers"]
    assert result["live_cutover_permitted"] is False
    assert "PRIVATE LATER EDIT" not in json.dumps(result)


def test_changed_restored_copy_blocks_evidence(tmp_path):
    paths = make_triplet(tmp_path)
    with sqlite3.connect(paths[2]) as conn:
        conn.execute(
            "UPDATE columns SET name='PRIVATE RECOVERY TAMPER' WHERE id=?",
            (DEFAULT_COLUMN_ID,),
        )
    result = review(paths)
    assert result["local_snapshot_and_restore_match"] is False
    assert result["offline_evidence_checks_passed"] is False
    assert "snapshot_restore_mismatch" in result["blockers"]
    assert "PRIVATE RECOVERY TAMPER" not in json.dumps(result)


def test_active_worker_lease_blocks_even_perfect_snapshot(tmp_path):
    source = tmp_path / "source.db"
    Database(source)
    now = "2026-10-13T00:00:00+00:00"
    with sqlite3.connect(source) as db:
        db.execute(
            "INSERT INTO projects (id,title,premise,visual_style,ratio,created_at,column_id)"
            " VALUES (?,?,?,?,?,?,?)",
            ("series_test", "PRIVATE SHORT FILM", "Unpublished", "live_action",
             "9:16", now, DEFAULT_COLUMN_ID),
        )
        db.execute(
            "INSERT INTO episodes (id,project_id,episode_number,title,body_json,created_at)"
            " VALUES (?,?,?,?,?,?)",
            ("episode_test", "series_test", 1, "PRIVATE EPISODE", "{}", now),
        )
        db.execute(
            "INSERT INTO productions (id,episode_id,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?)",
            ("production_test", "episode_test", "approved", now, now),
        )
        db.execute(
            "INSERT INTO shot_jobs (id,production_id,episode_id,series_id,shot_id,"
            "provider,model_id,input_sha256,idempotency_key,"
            "max_acknowledged_spend_usd,status,generation_intent_recorded,"
            "lease_owner,lease_expires_at,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("job_test", "production_test", "episode_test", "series_test",
             "shot1", "google", "fake", "a" * 64, "idempotency_test", "1.00",
             "leased", 0, "PRIVATE WORKER", "2026-10-20T00:00:00+00:00",
             now, now),
        )
    backup, recovered = tmp_path / "backup.db", tmp_path / "restore.db"
    rehearse_local_snapshot(
        source, backup, recovered,
        operator_approved=True, offline_rehearsal_only=True,
    )
    result = review((source, backup, recovered))
    assert result["local_snapshot_and_restore_match"] is True
    assert result["source_matches_snapshot_during_review"] is True
    assert result["source_risk_counts"]["leased_jobs"] == 1
    assert "unsettled_source_work" in result["blockers"]
    assert "unsettled_backup_work" in result["blockers"]
    assert "unsettled_restored_work" in result["blockers"]
    assert result["offline_evidence_checks_passed"] is False
    assert result["live_cutover_permitted"] is False
    assert "PRIVATE WORKER" not in json.dumps(result)


def test_explicit_permission_and_three_distinct_files_required(tmp_path):
    paths = make_triplet(tmp_path)
    for args in ({}, {"operator_approved": True}, {"offline_review_only": True}):
        with pytest.raises(OfflineCutoverDenied, match="approval"):
            inspect_cutover_evidence(*paths, **args)
    with pytest.raises(OfflineCutoverDenied, match="distinct"):
        review((paths[0], paths[1], paths[1]))
    alias = tmp_path / "alias.db"
    alias.symlink_to(paths[0])
    with pytest.raises(OfflineCutoverDenied, match="non-symlink"):
        review((alias, paths[1], paths[2]))


def test_missing_or_wrong_schema_does_not_create_or_fix_anything(tmp_path):
    source = tmp_path / "missing.db"
    backup = tmp_path / "snapshot.db"
    restored = tmp_path / "restored.db"
    with pytest.raises(OfflineCutoverDenied, match="existing"):
        review((source, backup, restored))
    assert not any(x.exists() for x in (source, backup, restored))

    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE unexpected (name TEXT)")
    with pytest.raises(OfflineCutoverDenied, match="integrity"):
        review((source, source.parent / "missing-other.db", restored))
    # Real wrong schema is checked before trying to access payload tables:
    shutil_backup = tmp_path / "one.db"
    shutil_restored = tmp_path / "two.db"
    with sqlite3.connect(shutil_backup) as c:
        c.execute("CREATE TABLE unexpected (name TEXT)")
    with sqlite3.connect(shutil_restored) as c:
        c.execute("CREATE TABLE unexpected (name TEXT)")
    with pytest.raises(OfflineCutoverDenied, match="integrity"):
        review((source, shutil_backup, shutil_restored))


def test_no_cloud_sdk_import_or_actual_migration(tmp_path, monkeypatch):
    import builtins

    paths = make_triplet(tmp_path)
    original_import = builtins.__import__

    def forbid_remote(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "googleapiclient")):
            raise AssertionError("Unexpected remote SDK import")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid_remote)
    result = review(paths)
    assert result["live_cutover_permitted"] is False
    assert result["turso_connections"] == 0
