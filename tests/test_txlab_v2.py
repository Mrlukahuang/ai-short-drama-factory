"""PR-31b2e: zero-cloud transaction v2 contract and one-use workflow safety."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from drama_factory.storage.libsql_txlab import TxLabStageError
from drama_factory.storage.txlab_v2 import (
    _TABLE, run_cli, run_live_txlab_v2, run_txlab_v2_contract,
)

LAB = "libsql://ai-short-drama-factory-txlab-mrlukahuang.aws-ap-southeast-2.turso.io"
PRODUCTION = "libsql://ai-short-drama-factory-mrlukahuang.aws-ap-southeast-2.turso.io"


def fake_connections(tmp_path):
    path = tmp_path / "disposable-new-v2.db"
    return lambda: sqlite3.connect(path, timeout=15), path


def test_v2_sequential_plus_race_matches_only_confirmed_commits(tmp_path):
    factory, path = fake_connections(tmp_path)
    result = run_txlab_v2_contract(factory, mode="offline_fake")
    assert result["single_new_probe_row_committed"] is True
    assert result["explicit_rollback_verified"] is True
    assert result["sequential_independent_commits"] == 2
    assert result["parallel_workers_attempted"] == 2
    assert result["parallel_commits_observed"] + result["parallel_begin_busy_observed"] == 2
    assert result["all_confirmed_commits_in_readback"] is True
    assert result["primary_key_duplicate_rejected"] is True
    assert result["any_automatic_write_retries"] is False
    assert result["remote_distributed_concurrency_certified"] is False
    assert result["live_cutover_permitted"] is False
    assert result["production_database_touched"] is False
    assert result["new_ai_model_generation_calls"] == 0
    with sqlite3.connect(path) as conn:
        rows = conn.execute(f"SELECT counter FROM {_TABLE}").fetchall()
    assert rows == [(2 + result["parallel_commits_observed"],)]
    serialized = json.dumps(result)
    assert LAB not in serialized
    assert re.search(r"txlabv2_[0-9a-f]{32}", serialized) is None


def test_known_busy_begin_is_recorded_not_retried(tmp_path):
    original, path = fake_connections(tmp_path)
    opened = 0

    class OneBusyConnection:
        def __init__(self, real):
            self.real = real
        def execute(self, sql, params=()):
            if sql == "BEGIN IMMEDIATE":
                raise sqlite3.OperationalError("SQLITE_BUSY: private secret is not printed")
            return self.real.execute(sql, params)
        def commit(self):
            self.real.commit()
        def rollback(self):
            self.real.rollback()
        def close(self):
            self.real.close()

    def factory():
        nonlocal opened
        opened += 1
        conn = original()
        # Master, first and second serial Worker, then two parallel workers.
        # Simulate BUSY at BEGIN for the first parallel contender.
        return OneBusyConnection(conn) if opened == 4 else conn

    result = run_txlab_v2_contract(factory, mode="offline_fake")
    assert opened == 5
    assert result["parallel_commits_observed"] == 1
    assert result["parallel_begin_busy_observed"] == 1
    assert result["all_confirmed_commits_in_readback"] is True
    assert result["any_automatic_write_retries"] is False
    with sqlite3.connect(path) as conn:
        assert conn.execute(f"SELECT counter FROM {_TABLE}").fetchone()[0] == 3


def test_commit_reply_lost_never_retries_and_fails_closed(tmp_path):
    original, path = fake_connections(tmp_path)
    opened = 0

    class AckLost:
        def __init__(self, real):
            self.real = real
        def execute(self, sql, params=()):
            return self.real.execute(sql, params)
        def commit(self):
            self.real.commit()  # Actually committed but the reply is lost!
            raise ConnectionError("connection reset SECRET_TOKEN_123")
        def rollback(self):
            self.real.rollback()
        def close(self):
            self.real.close()

    def factory():
        nonlocal opened
        opened += 1
        conn = original()
        return AckLost(conn) if opened == 2 else conn

    with pytest.raises(TxLabStageError) as fail:
        run_txlab_v2_contract(factory, mode="offline_fake")
    assert fail.value.stage == "worker_commit"
    assert fail.value.category == "connection"
    assert "SECRET_TOKEN_123" not in str(fail.value)
    assert opened == 2  # No other remote connections or automatic retries
    with sqlite3.connect(path) as conn:
        # Master insert and first increment actually committed.
        assert conn.execute(f"SELECT COUNT(*), MAX(counter) FROM {_TABLE}").fetchone() == (1, 1)


def test_remote_target_and_opt_in_gates_fail_before_connections(monkeypatch):
    import drama_factory.storage.txlab_v2 as impl
    calls = []
    monkeypatch.setattr(impl, "_open_lab_connection", lambda *args: calls.append(args))
    monkeypatch.delenv("DRAMA_TXLAB_V2_CONFIRM", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_TXLAB_V2_WRITE", raising=False)
    with pytest.raises(ValueError):
        run_live_txlab_v2(url=LAB, token="fake", operator_approved=True)
    monkeypatch.setenv("DRAMA_TXLAB_V2_CONFIRM", "RUN_ISOLATED_TXLAB_V2_ONE_TIME")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_V2_WRITE", "YES")
    for url, token in ((PRODUCTION, "fake"), (LAB, "")):
        with pytest.raises(ValueError):
            run_live_txlab_v2(url=url, token=token, operator_approved=True)
    assert calls == []


def test_fake_live_mode_only_uses_mocked_lab_sdk(tmp_path, monkeypatch):
    import drama_factory.storage.txlab_v2 as impl
    factory, _ = fake_connections(tmp_path)
    monkeypatch.setenv("DRAMA_TXLAB_V2_CONFIRM", "RUN_ISOLATED_TXLAB_V2_ONE_TIME")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_V2_WRITE", "YES")
    monkeypatch.setattr(impl, "_open_lab_connection", lambda url, token: factory())
    result = run_live_txlab_v2(url=LAB, token="secret_in_test_only", operator_approved=True)
    assert result["mode"] == "isolated_live"
    assert result["only_separate_txlab"] is True
    assert result["engine"] == "libsql"
    assert result["remote_distributed_concurrency_certified"] is False
    assert "secret_in_test_only" not in json.dumps(result)


def test_cli_redacts_sdk_exception_and_fails_without_live_opt_in(monkeypatch, capsys):
    import drama_factory.storage.txlab_v2 as impl
    assert run_cli([]) == 1
    monkeypatch.setenv("DRAMA_TXLAB_DATABASE_URL", LAB)
    monkeypatch.setenv("DRAMA_TXLAB_AUTH_TOKEN", "SECRET_BEARER_IN_ENV")
    monkeypatch.setenv("DRAMA_TXLAB_V2_CONFIRM", "RUN_ISOLATED_TXLAB_V2_ONE_TIME")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_V2_WRITE", "YES")
    monkeypatch.setattr(
        impl, "_open_lab_connection",
        lambda *args: (_ for _ in ()).throw(
            ConnectionError("connection reset; SECRET_BEARER_IN_ENV")
        ),
    )
    assert run_cli(["--live"]) == 1
    output = capsys.readouterr()
    assert "stage=open_master" in output.err
    assert "category=connection" in output.err
    assert "SECRET_BEARER_IN_ENV" not in output.err
    assert "Traceback" not in output.err
    assert output.out == ""


def test_new_manual_workflow_is_locked_until_new_authorization():
    workflow = (
        Path(__file__).resolve().parents[1] /
        ".github/workflows/manual-isolated-libsql-txlab-v2.yml"
    ).read_text()
    assert "workflow_dispatch:" in workflow
    assert "github.ref == 'refs/heads/main'" in workflow
    assert "false && github.ref" in workflow
    assert "inputs.confirmation == 'RUN_ISOLATED_TXLAB_V2_ONE_TIME'" in workflow
    assert "secrets.DRAMA_TXLAB_DATABASE_URL" in workflow
    assert "secrets.DRAMA_TXLAB_AUTH_TOKEN" in workflow
    assert "secrets.DRAMA_TURSO_DATABASE_URL" not in workflow
    assert "secrets.DRAMA_TURSO_AUTH_TOKEN" not in workflow
    assert "DRAMA_ENABLE_TXLAB_V2_WRITE: 'YES'" in workflow
    assert "python -m drama_factory.storage.txlab_v2 --live" in workflow
    assert "contents: read" in workflow
    assert "\n  push:" not in workflow


def test_candidate_module_imports_no_cloud_client(tmp_path, monkeypatch):
    import builtins
    old_import = builtins.__import__
    def forbid_cloud(name, *args, **kwargs):
        if name.startswith(("libsql", "googleapiclient", "turso_serverless")):
            raise AssertionError("unexpected cloud SDK")
        return old_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", forbid_cloud)
    factory, _ = fake_connections(tmp_path)
    output = run_txlab_v2_contract(factory, mode="offline_fake")
    assert output["production_backend_switched"] is False
