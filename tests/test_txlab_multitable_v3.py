"""No-cloud v3 feature proof: cross-table atomicity and schema integrity."""
from __future__ import annotations

import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from drama_factory.db import Database
from drama_factory.storage.txlab_multitable_v3 import (
    SCHEMA_V3, V3CommitUncertain, V3OfflineDenied,
    create_v3_fixture, inspect_v3_local, reconcile_v3_local,
)


def fixture(tmp_path):
    return create_v3_fixture(
        tmp_path / "never-reuse-a-production-file.sqlite",
        isolated_test_only=True,
    )


def baseline(path):
    return inspect_v3_local(path, isolated_test_only=True)


def test_one_synthetic_billing_transaction_updates_two_tables_and_one_audit(tmp_path):
    path = fixture(tmp_path)
    original = baseline(path)
    assert original["reservation_state"] == "held"
    assert original["job_state"] == "submission_intent"
    assert original["budget_charge_cents"] is None
    assert original["job_charge_cents"] is None
    assert original["job_audit_events"] == 1
    assert original["budget_audit_events"] == 1
    assert original["intent_recorded"] is True

    final = reconcile_v3_local(path, isolated_test_only=True)
    assert final["reservation_state"] == "reconciled"
    assert final["budget_charge_cents"] == final["job_charge_cents"] == 45
    assert final["job_audit_events"] == 1
    assert final["budget_audit_events"] == 2
    assert final["remote_schema_verified"] is False
    assert final["remote_multitable_transaction_verified"] is False
    assert final["real_live_migration_authorized"] is False
    assert final["production_backend_switched"] is False
    assert final["remote_turso_connection_attempts"] == 0
    assert final["paid_provider_calls"] == 0
    with pytest.raises(V3OfflineDenied, match="Already reconciled"):
        reconcile_v3_local(path, isolated_test_only=True)
    assert baseline(path) == final


@pytest.mark.parametrize("stage", [
    "after_budget", "after_job", "after_event",
])
def test_every_multitable_failure_rolls_back_all_columns_and_audit(tmp_path, stage):
    path = fixture(tmp_path)
    before = baseline(path)
    with pytest.raises(V3OfflineDenied, match="Injected failure"):
        reconcile_v3_local(path, isolated_test_only=True, fail_after=stage)
    after = baseline(path)
    assert after == before
    assert after["budget_charge_cents"] is None
    assert after["job_charge_cents"] is None
    assert after["budget_audit_events"] == 1
    assert reconcile_v3_local(path, isolated_test_only=True)["budget_audit_events"] == 2


def test_ack_lost_after_real_local_commit_must_not_be_replayed(tmp_path):
    path = fixture(tmp_path)
    with pytest.raises(V3CommitUncertain, match="never retry"):
        reconcile_v3_local(path, isolated_test_only=True, fail_after="after_commit_ack")
    snapshot = baseline(path)
    assert snapshot["budget_charge_cents"] == 45
    assert snapshot["job_charge_cents"] == 45
    assert snapshot["budget_audit_events"] == 2
    with pytest.raises(V3OfflineDenied, match="Already reconciled"):
        reconcile_v3_local(path, isolated_test_only=True)
    assert baseline(path) == snapshot


def test_two_independent_reviewers_cannot_both_reconcile(tmp_path):
    path = fixture(tmp_path)
    gate = Barrier(2)

    def reviewer(_):
        gate.wait(timeout=15)
        try:
            receipt = reconcile_v3_local(path, isolated_test_only=True)
            return "committed" if receipt["reservation_state"] == "reconciled" else "invalid"
        except V3OfflineDenied:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reviewer, (1, 2)))
    assert sorted(results) == ["committed", "rejected"]
    assert baseline(path)["budget_audit_events"] == 2


@pytest.mark.parametrize("table", ["pr31_v3_job_event", "pr31_v3_budget_event"])
def test_immutable_audit_update_and_delete_trigger_fails(tmp_path, table):
    path = fixture(tmp_path)
    with sqlite3.connect(path) as conn:
        for sql in (
            f"UPDATE {table} SET action='tampered'",
            f"DELETE FROM {table}",
        ):
            with pytest.raises(sqlite3.IntegrityError, match="append-only"):
                conn.execute(sql)
            conn.rollback()
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1


def test_nonnull_provider_task_unique_index_but_multiple_nulls_allowed(tmp_path):
    path = fixture(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute(
            "INSERT INTO pr31_v3_job VALUES "
            "('synthetic_job_b','fake',NULL,'synthetic_unique_2','submission_intent',1,NULL)"
        )
        db.execute(
            "UPDATE pr31_v3_job SET provider_task_id='tasks/offline-01' "
            "WHERE id='synthetic_job_a'"
        )
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            db.execute(
                "UPDATE pr31_v3_job SET provider_task_id='tasks/offline-01' "
                "WHERE id='synthetic_job_b'"
            )
        db.rollback()
        rows = db.execute(
            "SELECT COUNT(*) FROM pr31_v3_job WHERE provider_task_id IS NOT NULL"
        ).fetchone()[0]
        assert rows == 0


def test_fk_and_check_constraints_refuse_corruption(tmp_path):
    path = fixture(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        for sql in (
            "INSERT INTO pr31_v3_budget_event VALUES "
            "('orphan-event','missing-reservation','bad')",
            "INSERT INTO pr31_v3_reservation VALUES "
            "('orphan-budget','missing-job','pr31-v3-synthetic-fixture-only',40,NULL,'held')",
            "UPDATE pr31_v3_job SET generation_intent_recorded=0 "
            "WHERE id='synthetic_job_a'",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
            db.rollback()
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_new_file_only_requires_gate_and_never_touches_old_production_sqlite(tmp_path):
    destination = tmp_path / "fresh-local-only.sqlite"
    with pytest.raises(V3OfflineDenied, match="gate"):
        create_v3_fixture(destination)
    assert not destination.exists()
    source = tmp_path / "existing-real-like.sqlite"
    Database(source)
    previous = source.read_bytes()
    with pytest.raises(V3OfflineDenied, match="existing file"):
        create_v3_fixture(source, isolated_test_only=True)
    with pytest.raises(V3OfflineDenied, match="Not a disposable"):
        inspect_v3_local(source, isolated_test_only=True)
    assert source.read_bytes() == previous
    alias = tmp_path / "alias"
    alias.symlink_to(source)
    with pytest.raises(V3OfflineDenied, match="Regular"):
        create_v3_fixture(alias, isolated_test_only=True)
    for bad in ("libsql://ai-short-drama-factory.turso.io", ":memory:"):
        with pytest.raises(V3OfflineDenied, match="Local"):
            create_v3_fixture(bad, isolated_test_only=True)
    assert not destination.exists()


def test_real_dedicated_sql_names_never_overlap_prior_canaries_or_production(tmp_path):
    path = fixture(tmp_path)
    with sqlite3.connect(path) as db:
        names = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
    assert names == {
        "pr31_v3_policy", "pr31_v3_job", "pr31_v3_job_event",
        "pr31_v3_reservation", "pr31_v3_budget_event",
    }
    assert all("pr31_v3_" in ddl for ddl in SCHEMA_V3)
    assert not any(
        "pr31_txlab_transaction_probe_v1" in ddl
        or "pr31_txlab_v2_probe_v1" in ddl
        or "drama_drive_receipts_v1" in ddl
        or "DROP TABLE" in ddl.upper()
        for ddl in SCHEMA_V3
    )
    result = json.dumps(baseline(path))
    assert str(path) not in result
    assert "synthetic_job_a" not in result
    assert "real_live_migration_authorized" in result


def test_no_remote_sdk_or_runner_workflow_during_offline_rehearsal(tmp_path, monkeypatch):
    import builtins
    original = builtins.__import__

    def forbid(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "googleapiclient")):
            raise AssertionError("No external SDK in offline v3 fixture")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid)
    path = fixture(tmp_path)
    assert baseline(path)["remote_turso_connection_attempts"] == 0
    assert reconcile_v3_local(path, isolated_test_only=True)["paid_provider_calls"] == 0
