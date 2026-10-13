"""v3 lab candidate is offline tested; remote manual workflow must stay LOCKED."""
from __future__ import annotations

import builtins
import json
import sqlite3
from pathlib import Path

import pytest

from drama_factory.storage.txlab_multitable_v3_live import (
    V3LabDenied, V3LabStageFailure,
    run_cli, run_live_v3, run_v3_lab_contract,
)

LAB = "libsql://ai-short-drama-factory-txlab-mrlukahuang.aws-ap-southeast-2.turso.io"
PRODUCTION = "libsql://ai-short-drama-factory-mrlukahuang.aws-ap-southeast-2.turso.io"


def factory_at(tmp_path):
    path = tmp_path / "local-v3-synthetic-only.sqlite"
    opened = []
    def factory():
        conn = sqlite3.connect(path, timeout=10, isolation_level=None)
        opened.append(conn)
        return conn
    return factory, path, opened


def _table_count(path):
    with sqlite3.connect(path) as db:
        return db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'pr31_v3_%'"
        ).fetchone()[0]


def _committed_view(path):
    with sqlite3.connect(path) as db:
        r = db.execute(
            "SELECT r.status,r.actual_cents,j.actual_charge_cents,"
            "(SELECT COUNT(*) FROM pr31_v3_budget_event) "
            "FROM pr31_v3_reservation r "
            "JOIN pr31_v3_job j ON r.job_id=j.id"
        ).fetchone()
    return r


def test_v3_five_tables_and_multi_table_commit_works_without_cloud(tmp_path):
    factory, path, opened = factory_at(tmp_path)
    receipt = run_v3_lab_contract(factory)
    assert receipt["mode"] == "offline_fake"
    assert receipt["schema_object_count"] == 10
    assert receipt["rollback_multitable_verified"] is True
    assert receipt["committed_multitable_readback_verified"] is True
    assert receipt["foreign_key_constraints_verified"] is True
    assert receipt["partial_unique_provider_task_verified"] is True
    assert receipt["append_only_triggers_verified"] is True
    assert receipt["no_auto_retry"] is True
    assert receipt["isolated_v3_lab_verified"] is False
    assert receipt["remote_multiworker_concurrency_verified"] is False
    assert receipt["full_production_schema_verified"] is False
    assert receipt["production_database_touched"] is False
    assert receipt["live_cutover_permitted"] is False
    assert receipt["paid_provider_calls"] == 0
    assert _table_count(path) == 10
    assert _committed_view(path) == ("reconciled", 45, 45, 2)
    dumped = json.dumps(receipt, sort_keys=True)
    assert str(path) not in dumped
    assert LAB not in dumped
    assert "synthetic_job_a" not in dumped
    assert len(opened) == 2


def test_existing_partial_or_complete_v3_schema_denied_before_any_write(tmp_path):
    factory, path, _ = factory_at(tmp_path)
    run_v3_lab_contract(factory)
    before = path.read_bytes()
    with pytest.raises(V3LabStageFailure) as exc:
        run_v3_lab_contract(factory)
    assert exc.value.stage == "preflight"
    assert path.read_bytes() == before
    assert _committed_view(path) == ("reconciled", 45, 45, 2)
    assert _table_count(path) == 10


def test_partial_ddl_error_never_auto_repairs_or_overwrites(tmp_path):
    normal, path, _ = factory_at(tmp_path)
    calls = []

    class FaultyConn:
        def __init__(self, db):
            self.db = db
        def execute(self, sql, params=()):
            if sql.lstrip().startswith("CREATE TABLE pr31_v3_job"):
                calls.append("failed_schema")
                raise sqlite3.OperationalError("SQLITE_BUSY: secret bearer ALPHA")
            return self.db.execute(sql, params)
        def commit(self):
            return self.db.commit()
        def rollback(self):
            return self.db.rollback()
        def close(self):
            return self.db.close()

    with pytest.raises(V3LabStageFailure) as error:
        run_v3_lab_contract(lambda: FaultyConn(normal()))
    assert error.value.stage == "schema"
    assert error.value.category == "busy"
    assert "ALPHA" not in str(error.value)
    assert calls == ["failed_schema"]
    assert _table_count(path) == 1  # v3 policy table DDL already committed
    prev = path.read_bytes()
    with pytest.raises(V3LabStageFailure) as repeated:
        run_v3_lab_contract(normal)
    assert repeated.value.stage == "preflight"
    assert path.read_bytes() == prev


def test_commit_ack_lost_is_reported_unsafe_and_never_replayed(tmp_path):
    normal, path, opened = factory_at(tmp_path)

    class CommitReplyLost:
        def __init__(self, db):
            self.db = db
            self.commits = 0
        def execute(self, sql, params=()):
            return self.db.execute(sql, params)
        def commit(self):
            self.commits += 1
            self.db.commit()
            if self.commits == 3:
                raise ConnectionError("connection reset SECRET_BEARER_BETA")
        def rollback(self):
            self.db.rollback()
        def close(self):
            self.db.close()

    with pytest.raises(V3LabStageFailure) as error:
        run_v3_lab_contract(lambda: CommitReplyLost(normal()))
    assert error.value.stage == "bill_commit"
    assert error.value.category == "connection"
    assert "SECRET_BEARER_BETA" not in str(error.value)
    assert len(opened) == 1  # no second connect after ambiguous COMMIT
    assert _committed_view(path) == ("reconciled", 45, 45, 2)
    with pytest.raises(V3LabStageFailure) as second:
        run_v3_lab_contract(normal)
    assert second.value.stage == "preflight"
    assert _committed_view(path) == ("reconciled", 45, 45, 2)


def test_vendor_network_error_does_not_masquerade_as_fk_enforcement(tmp_path):
    normal, path, _ = factory_at(tmp_path)

    class FakeDisconnectOnNegative:
        def __init__(self, db):
            self.db = db
        def execute(self, sql, params=()):
            if "orphan_test_event" in sql:
                raise ConnectionError("network error: SECRET_BEARER_DELTA")
            return self.db.execute(sql, params)
        def commit(self):
            self.db.commit()
        def rollback(self):
            self.db.rollback()
        def close(self):
            self.db.close()

    with pytest.raises(V3LabStageFailure) as error:
        run_v3_lab_contract(lambda: FakeDisconnectOnNegative(normal()))
    assert error.value.stage == "check_fk"
    assert error.value.category == "unknown"
    assert "SECRET_BEARER_DELTA" not in str(error.value)
    assert _committed_view(path) == ("reconciled", 45, 45, 2)
    assert _table_count(path) == 10


def test_real_live_adapter_cannot_connect_without_NEW_authorization(monkeypatch):
    import drama_factory.storage.txlab_multitable_v3_live as live
    calls = []
    monkeypatch.setattr(live, "_open_lab_connection", lambda *args: calls.append(args))
    monkeypatch.delenv("DRAMA_TXLAB_V3_CONFIRM", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_TXLAB_V3_WRITE", raising=False)
    with pytest.raises(V3LabDenied):
        run_live_v3(LAB, "fake-only", operator_approved=True)
    monkeypatch.setenv("DRAMA_TXLAB_V3_CONFIRM", "RUN_ISOLATED_TXLAB_V3_ONCE")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_V3_WRITE", "YES")
    with pytest.raises(V3LabDenied):
        run_live_v3(LAB, "fake-only", operator_approved=False)
    with pytest.raises(V3LabDenied):
        run_live_v3(PRODUCTION, "fake-only", operator_approved=True)
    with pytest.raises(V3LabDenied):
        run_live_v3(LAB, "", operator_approved=True)
    assert calls == []


def test_mocked_live_run_does_not_require_network(tmp_path, monkeypatch):
    factory, _, _ = factory_at(tmp_path)
    monkeypatch.setenv("DRAMA_TXLAB_V3_CONFIRM", "RUN_ISOLATED_TXLAB_V3_ONCE")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_V3_WRITE", "YES")
    receipt = run_live_v3(
        LAB, "test-credential-only", operator_approved=True,
        connection_factory=factory,
    )
    assert receipt["mode"] == "isolated_live"
    assert receipt["isolated_v3_lab_verified"] is True
    assert receipt["production_database_touched"] is False
    assert "test-credential-only" not in json.dumps(receipt)


def test_cli_output_does_not_disclose_error_or_token(monkeypatch, capsys):
    import drama_factory.storage.txlab_multitable_v3_live as live
    monkeypatch.setenv("DRAMA_TXLAB_DATABASE_URL", LAB)
    monkeypatch.setenv("DRAMA_TXLAB_AUTH_TOKEN", "SUPER_PRIVATE_TEST_ONLY_TOKEN")
    monkeypatch.setenv("DRAMA_TXLAB_V3_CONFIRM", "RUN_ISOLATED_TXLAB_V3_ONCE")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_V3_WRITE", "YES")
    monkeypatch.setattr(
        live, "_open_lab_connection",
        lambda *args: (_ for _ in ()).throw(
            ConnectionError("connection reset SUPER_PRIVATE_TEST_ONLY_TOKEN")
        )
    )
    assert run_cli(["--live"]) == 1
    out = capsys.readouterr()
    assert "stage=open" in out.err
    assert "category=connection" in out.err
    assert "SUPER_PRIVATE_TEST_ONLY_TOKEN" not in out.err
    assert "Traceback" not in out.err
    assert out.out == ""


def test_authorized_manual_workflow_rejects_rerun_and_production_secrets():
    workflow = (
        Path(__file__).resolve().parents[1] /
        ".github/workflows/manual-isolated-libsql-txlab-v3.yml"
    ).read_text()
    assert "workflow_dispatch:" in workflow
    assert "false && github.ref" not in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "github.run_attempt == 1" in workflow
    assert 'GITHUB_RUN_ATTEMPT" != "1"' in workflow
    assert 'GITHUB_REF" != "refs/heads/main"' in workflow
    assert "github.run_attempt == 1" in workflow
    assert "inputs.confirmation == 'RUN_ISOLATED_TXLAB_V3_ONCE'" in workflow
    assert "GITHUB_RUN_ATTEMPT" in workflow
    assert "manual-isolated-libsql-txlab-v3.yml/runs?event=workflow_dispatch" in workflow
    assert "GH_TOKEN: ${{ github.token }}" in workflow
    assert "first_run_id" in workflow
    assert "per_page=100" in workflow
    assert "cancel-in-progress: false" in workflow
    assert 'dispatch_count" != "1"' in workflow
    assert 'first_run_id" != "$GITHUB_RUN_ID"' in workflow
    assert "secrets.DRAMA_TXLAB_DATABASE_URL" in workflow
    assert "secrets.DRAMA_TXLAB_AUTH_TOKEN" in workflow
    assert "secrets.DRAMA_TURSO_DATABASE_URL" not in workflow
    assert "secrets.DRAMA_TURSO_AUTH_TOKEN" not in workflow
    assert "secrets.DRAMA_DRIVE_USER_OAUTH_JSON" not in workflow
    assert "actions: read" in workflow
    assert "contents: read" in workflow
    assert "DRAMA_ENABLE_TXLAB_V3_WRITE: 'YES'" in workflow
    assert "python -m drama_factory.storage.txlab_multitable_v3_live --live" in workflow
    assert "\n  push:" not in workflow


def test_runner_never_imports_remote_client_when_offline(tmp_path, monkeypatch):
    original_import = builtins.__import__
    def forbid(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "googleapiclient")):
            raise AssertionError("Unexpected remote SDK import")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", forbid)
    factory, _, _ = factory_at(tmp_path)
    result = run_v3_lab_contract(factory)
    assert result["mode"] == "offline_fake"
    assert result["no_auto_retry"] is True
