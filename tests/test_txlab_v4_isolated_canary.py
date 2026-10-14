"""TxLab v4 canary: zero-cloud contract before an authorized single run."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from drama_factory.storage.txlab_v4_isolated_canary import (
    _NAMES, _PREFIX, _schema, run_live_v4, run_v4_contract,
    V4CanaryDenied, V4StageFailure,
)


def _factory(path: Path):
    def factory():
        conn = sqlite3.connect(path, timeout=15)
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    return factory


def test_local_v4_schema_and_atomic_contract(tmp_path):
    factory = _factory(tmp_path / "v4-offline-only.sqlite")
    receipt = run_v4_contract(factory)
    assert receipt["schema_objects_verified"] == 22
    assert receipt["isolated_v4_lab_verified"] is False
    assert receipt["synthetic_three_scope_budget_held"] is True
    assert receipt["synthetic_claim_intent_task_atomic"] is True
    assert receipt["rollback_and_independent_readback_verified"] is True
    assert receipt["local_or_serial_epoch_pause_verified"] is True
    for key in (
        "full_production_schema_verified",
        "remote_multiworker_concurrency_verified",
        "network_commit_ack_loss_verified", "vendor_billing_verified",
        "production_database_touched", "production_backend_switched",
        "live_cutover_permitted",
    ):
        assert receipt[key] is False
    assert receipt["paid_provider_calls"] == 0
    assert "synthetic_v4" not in json.dumps(receipt)
    with sqlite3.connect(tmp_path / "v4-offline-only.sqlite") as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'pr31_v4_%'"
        )}
        assert names == _NAMES
        assert conn.execute("SELECT COUNT(*) FROM pr31_v4_shot_jobs").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM pr31_v4_job_budget_reservations").fetchone()[0] == 1


def test_repeat_is_denied_before_any_additional_ddl_or_dml(tmp_path):
    factory = _factory(tmp_path / "v4-one-shot.sqlite")
    run_v4_contract(factory)
    with pytest.raises(V4StageFailure) as exc:
        run_v4_contract(factory)
    assert exc.value.stage == "preflight"
    with sqlite3.connect(tmp_path / "v4-one-shot.sqlite") as conn:
        assert conn.execute("SELECT COUNT(*) FROM pr31_v4_shot_jobs").fetchone()[0] == 1


def test_live_requires_both_independent_gates_and_validated_url(tmp_path, monkeypatch):
    factory = _factory(tmp_path / "v4-live-gates.sqlite")
    isolated = "libsql://ai-short-drama-factory-txlab-local-only.turso.io"
    for key in ("DRAMA_TXLAB_V4_CONFIRM", "DRAMA_ENABLE_TXLAB_V4_WRITE"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(V4CanaryDenied, match="approval"):
        run_live_v4(isolated, "fake", operator_approved=True, connection_factory=factory)
    monkeypatch.setenv("DRAMA_TXLAB_V4_CONFIRM", "RUN_ISOLATED_TXLAB_V4_ONCE")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_V4_WRITE", "YES")
    for bad in ("libsql://ai-short-drama-factory.turso.io", "file:///tmp/test.db", "https://example.com"):
        with pytest.raises(V4CanaryDenied, match="isolated"):
            run_live_v4(bad, "fake", operator_approved=True, connection_factory=factory)
    with pytest.raises(V4CanaryDenied, match="credentials"):
        run_live_v4(isolated, "", operator_approved=True, connection_factory=factory)
    assert run_live_v4(
        isolated, "fake", operator_approved=True, connection_factory=factory
    )["isolated_v4_lab_verified"] is True


def test_v4_schema_does_not_reuse_v1_v2_v3_or_original_names():
    sql = "\n".join(_schema()).lower()
    assert len(_schema()) == 22
    assert all(statement.strip().upper().startswith(("CREATE TABLE","CREATE INDEX","CREATE UNIQUE INDEX","CREATE TRIGGER")) for statement in _schema())
    assert all("pr31_v4_" in ddl for ddl in _schema())
    for bad in ("drop table", "create table if not exists",
                "pr31_v3_", "pr31_txlab_v2_", "production_database_url",
                "drama_drive_receipts"):
        assert bad not in sql
    assert not any(name in _NAMES for name in (
        "shot_jobs","budget_policies","job_budget_reservations",
    ))
    assert all(name.startswith(_PREFIX) for name in _NAMES)


def test_v4_rejects_invalid_mode_without_connection():
    with pytest.raises(V4CanaryDenied):
        run_v4_contract(lambda: (_ for _ in ()).throw(AssertionError("opened")), mode="remote")


def test_after_seed_sqlite_error_stays_redacted_and_never_auto_retries(tmp_path):
    path = tmp_path / "v4-inject.sqlite"
    class FailingConnection:
        def __init__(self, inner):
            self.inner = inner
        def execute(self, sql, *args):
            if "INSERT INTO pr31_v4_job_budget_reservations VALUES" in sql:
                raise ConnectionError("PRIVATE_FAKE_TEST_SECRET should never leak")
            return self.inner.execute(sql, *args)
        def commit(self):
            return self.inner.commit()
        def rollback(self):
            return self.inner.rollback()
        def close(self):
            return self.inner.close()
    factory = _factory(path)
    with pytest.raises(V4StageFailure) as exc:
        run_v4_contract(lambda: FailingConnection(factory()))
    assert exc.value.stage == "rollback_write"
    assert exc.value.category == "unknown"
    assert "PRIVATE_FAKE_TEST_SECRET" not in str(exc.value)
    # Seed may already have committed, so even on error, no rerun.
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM pr31_v4_shot_jobs").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM pr31_v4_job_budget_reservations"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT status FROM pr31_v4_shot_jobs"
        ).fetchone()[0] == "pending"
