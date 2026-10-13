"""PR-31b2m: source-only, no-cloud cutover gap contract regression tests."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing

import pytest

from drama_factory.db import Database, DEFAULT_COLUMN_ID
from drama_factory.storage.pr31_remote_gap_assessment import (
    RemoteGapDenied, assess_pr31_cutover_gaps, run_cli,
)


def fixture(tmp_path):
    path = tmp_path / "disposable-production-shaped-source.sqlite"
    Database(path)
    return path


def assess(path):
    return assess_pr31_cutover_gaps(path, offline_review_only=True)


def test_complete_local_business_and_media_structure_is_still_not_cutover(tmp_path):
    path = fixture(tmp_path)
    before = path.read_bytes()
    receipt = assess(path)
    assert path.read_bytes() == before
    assert receipt["reference_real_v3_actions_run_id"] == "38417337745"
    assert receipt["remote_v3_synthetic_serial_multitable_verified"] is True
    assert receipt["remote_v3_synthetic_fk_partial_unique_audit_verified"] is True
    assert receipt["remote_v3_only_test_objects"] == 10
    assert receipt["full_production_tables_run_remotely_in_v3"] == 0
    assert receipt["local_schema_safety_checks_passed"] is True
    assert receipt["local_quiescence_checks_passed"] is True
    assert receipt["blockers"] == []
    assert receipt["source_global_cross_scan_snapshot_verified"] is False
    assert receipt["local_schema_metrics"]["total_local_tables"] >= 20
    assert receipt["local_schema_metrics"]["checked_asset_tables"] == 6
    assert receipt["local_schema_metrics"]["checked_asset_indexes"] == 3
    assert receipt["local_schema_metrics"]["checked_asset_audit_triggers"] == 4
    assert receipt["local_schema_metrics"]["checked_additional_fk_edges"] == 9
    assert receipt["local_schema_metrics"]["checked_uniques"] == 6
    assert receipt["local_schema_metrics"]["checked_column_groups"] == 7
    assert len(receipt["local_inventory_schema_fingerprint_sha256"]) == 64
    assert len(receipt["local_critical_schema_fingerprint_sha256"]) == 64
    assert len(receipt["pending_remote_gates"]) >= 7
    for name in (
        "full_production_schema_import_verified",
        "remote_budget_fencing_verified",
        "remote_multiworker_concurrency_verified",
        "remote_network_commit_recovery_verified",
        "cloud_artifact_migration_verified",
        "production_backend_switched",
        "live_cutover_permitted",
    ):
        assert receipt[name] is False
    assert receipt["requires_new_live_write_authorization"] is True
    assert receipt["turso_connections"] == receipt["paid_provider_calls"] == 0


def test_deleting_media_audit_trigger_fails_even_when_critical_job_audit_intact(tmp_path):
    path = fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TRIGGER drive_events_no_update")
        db.commit()
    before = path.read_bytes()
    receipt = assess(path)
    assert path.read_bytes() == before
    assert receipt["local_schema_safety_checks_passed"] is False
    assert "missing_asset_immutable_trigger_drive_events_no_update" in receipt["blockers"]
    assert receipt["live_cutover_permitted"] is False
    assert receipt["local_quiescence_checks_passed"] is True


def test_same_name_noop_media_audit_trigger_cannot_pass(tmp_path):
    path = fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP TRIGGER cloud_events_immutable_delete")
        db.execute(
            "CREATE TRIGGER cloud_events_immutable_delete "
            "BEFORE DELETE ON cloud_artifact_events BEGIN SELECT 1; END"
        )
        db.commit()
    result = assess(path)
    assert "invalid_asset_immutable_trigger_cloud_events_immutable_delete" in result["blockers"]
    assert result["local_schema_safety_checks_passed"] is False


def test_missing_media_index_and_leaf_table_block_even_if_v3_passed(tmp_path):
    path = fixture(tmp_path)
    with closing(sqlite3.connect(path)) as db:
        db.execute("DROP INDEX idx_drive_artifacts_source")
        db.execute("DROP TABLE cloud_artifact_events")
        db.commit()
    result = assess(path)
    assert "missing_asset_index_idx_drive_artifacts_source" in result["blockers"]
    assert "missing_asset_table_cloud_artifact_events" in result["blockers"]
    assert "missing_asset_immutable_trigger_cloud_events_immutable_update" in result["blockers"]
    assert result["remote_v3_synthetic_serial_multitable_verified"] is True
    assert result["full_production_schema_import_verified"] is False


def test_missing_real_lease_and_budget_fields_refused_in_partial_schema(tmp_path):
    path = tmp_path / "old-incomplete-schema.sqlite"
    with closing(sqlite3.connect(path)) as db:
        db.execute("CREATE TABLE shot_jobs (id TEXT PRIMARY KEY, status TEXT)")
        db.execute("CREATE TABLE budget_policies (id TEXT PRIMARY KEY)")
        db.commit()
    result = assess(path)
    assert "missing_required_columns_shot_jobs" in result["blockers"]
    assert "missing_required_columns_budget_policies" in result["blockers"]
    assert result["local_schema_safety_checks_passed"] is False
    assert result["local_quiescence_checks_passed"] is False
    assert result["local_operational_risk_counts"] is None
    assert result["live_cutover_permitted"] is False


def test_active_real_business_lease_blocks_quiescence_even_if_schema_valid(tmp_path):
    path = fixture(tmp_path)
    ts = "2026-10-14T00:00:00+00:00"
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute(
            "INSERT INTO projects "
            "(id,title,premise,visual_style,ratio,created_at,column_id)"
            " VALUES (?,?,?,?,?,?,?)",
            ("confidential-series", "CONFIDENTIAL STORY", "PRIVATE PLOT",
             "live_action", "9:16", ts, DEFAULT_COLUMN_ID),
        )
        db.execute(
            "INSERT INTO episodes "
            "(id,project_id,episode_number,title,body_json,created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("confidential-episode", "confidential-series", 1,
             "SECRET_EPISODE", "{}", ts),
        )
        db.execute(
            "INSERT INTO productions (id,episode_id,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?)",
            ("confidential-run", "confidential-episode", "approved", ts, ts),
        )
        db.execute(
            "INSERT INTO shot_jobs "
            "(id,production_id,episode_id,series_id,shot_id,provider,model_id,"
            "input_sha256,idempotency_key,max_acknowledged_spend_usd,status,"
            "generation_intent_recorded,lease_owner,lease_expires_at,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("confidential-job", "confidential-run", "confidential-episode",
             "confidential-series", "shot-1", "google", "test",
             "b" * 64, "confidential-idempotency", "1.00", "leased", 0,
             "SECRET_WORKER", "2026-12-01T00:00:00+00:00", ts, ts),
        )
        db.commit()
    before = path.read_bytes()
    result = assess(path)
    assert before == path.read_bytes()
    assert result["local_schema_safety_checks_passed"] is True
    assert result["local_quiescence_checks_passed"] is False
    assert result["local_operational_risk_counts"]["leased_jobs"] == 1
    assert "leased_jobs" in result["blockers"]
    assert result["live_cutover_permitted"] is False
    payload = json.dumps(result, sort_keys=True)
    for secret in (
        "CONFIDENTIAL STORY", "PRIVATE PLOT", "SECRET_EPISODE",
        "SECRET_WORKER", "confidential-idempotency", "confidential-job",
        str(path),
    ):
        assert secret not in payload


def test_gate_refuses_remote_urls_existing_symlink_and_missing_files(tmp_path):
    path = tmp_path / "never-created.sqlite"
    with pytest.raises(RemoteGapDenied, match="review"):
        assess_pr31_cutover_gaps(path)
    with pytest.raises(RemoteGapDenied, match="Existing"):
        assess(path)
    assert not path.exists()
    with pytest.raises(RemoteGapDenied, match="local"):
        assess("libsql://ai-short-drama-factory-txlab-secret.turso.io")
    with pytest.raises(RemoteGapDenied, match="local"):
        assess(":memory:")
    original = fixture(tmp_path)
    sym = tmp_path / "alias.sqlite"
    sym.symlink_to(original)
    with pytest.raises(RemoteGapDenied, match="non-symlink"):
        assess(sym)


def test_cli_failure_redacts_source_and_accepts_only_readonly_confirmation(
    tmp_path, capsys,
):
    path = fixture(tmp_path)
    assert run_cli([
        "--source", str(path), "--confirmation", "TRY_PRODUCTION_CUTOVER",
    ]) == 1
    output = capsys.readouterr()
    assert "details redacted" in output.err
    assert str(path) not in output.err
    assert output.out == ""
    assert run_cli([
        "--source", str(path),
        "--confirmation", "PR31_LOCAL_GAP_REVIEW_ONLY",
    ]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["live_cutover_permitted"] is False
    assert receipt["local_schema_safety_checks_passed"] is True


def test_gap_assessor_cannot_import_cloud_sdk_or_change_source(tmp_path, monkeypatch):
    import builtins
    original_import = builtins.__import__
    def deny_cloud(name, *args, **kwargs):
        if name.startswith((
            "libsql", "turso_serverless", "googleapiclient", "google.genai",
        )):
            raise AssertionError("Unexpected remote SDK import")
        return original_import(name, *args, **kwargs)
    path = fixture(tmp_path)
    before = path.read_bytes()
    monkeypatch.setattr(builtins, "__import__", deny_cloud)
    receipt = assess(path)
    assert path.read_bytes() == before
    assert receipt["turso_connections"] == 0
    assert receipt["paid_provider_calls"] == 0
