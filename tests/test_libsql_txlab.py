"""Offline contract for isolated disposable libSQL transaction lab only."""
from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from drama_factory.storage.libsql_txlab import (
    TxLabDenied, run_cli, run_live_txlab, run_transaction_contract, validate_lab_url,
)

GOOD = "libsql://ai-short-drama-factory-txlab-mrlukahuang.aws-ap-southeast-2.turso.io"
BAD_PRODUCTION = "libsql://ai-short-drama-factory-mrlukahuang.aws-ap-southeast-2.turso.io"


def sqlite_factory(tmp_path):
    path = tmp_path / "isolated-test.db"
    return lambda: sqlite3.connect(path, timeout=15)


@pytest.mark.parametrize("bad_url", [
    BAD_PRODUCTION,
    "libsql://nz-social-trend-radar-mrlukahuang.aws-ap-southeast-2.turso.io",
    "https://ai-short-drama-factory-txlab-mrlukahuang.aws-ap-southeast-2.turso.io",
    "libsql://admin:password@ai-short-drama-factory-txlab-mrlukahuang.turso.io",
    "libsql://ai-short-drama-factory-txlab-mrlukahuang.turso.io/db",
    "libsql://ai-short-drama-factory-txlab-mrlukahuang.turso.io?auth=leak",
    "libsql://ai-short-drama-factory-txlab-mrlukahuang.turso.io:443",
    "libsql://some-other-project.turso.io",
    "",
])
def test_scope_rejects_non_lab_databases_and_embedded_credentials(bad_url):
    with pytest.raises(TxLabDenied):
        validate_lab_url(bad_url)


def test_isolated_target_only():
    assert validate_lab_url(GOOD) == GOOD


def test_two_independent_sqlite_connections_really_serialize(tmp_path):
    factory = sqlite_factory(tmp_path)
    result = run_transaction_contract(factory, mode="offline_fake")
    assert result["explicit_rollback_verified"] is True
    assert result["two_independent_connection_increments"] is True
    assert result["no_lost_update"] is True
    assert result["primary_key_duplicate_rejected"] is True
    assert result["probe_ids_redacted"] is True
    assert result["production_database_touched"] is False
    assert result["production_backend_switched"] is False
    assert result["live_cutover_permitted"] is False
    assert result["new_ai_model_generation_calls"] == 0
    with factory() as db:
        rows = db.execute("SELECT counter FROM pr31_txlab_transaction_probe_v1").fetchall()
    assert rows == [(2,)]
    dumped = json.dumps(result)
    assert "txlab_" not in dumped
    assert GOOD not in dumped


def test_two_separate_independent_conns_are_opened(tmp_path):
    base = sqlite_factory(tmp_path)
    connections = []
    def factory():
        conn = base()
        connections.append(conn)
        return conn
    result = run_transaction_contract(factory, mode="offline_fake")
    assert result["no_lost_update"] is True
    assert len(connections) == 3
    assert len({id(x) for x in connections}) == 3


def test_missing_live_authorization_and_credentials_cannot_connect(monkeypatch):
    import drama_factory.storage.libsql_txlab as lab

    calls = []
    monkeypatch.setattr(lab, "_open_lab_connection",
                        lambda *args: calls.append(args))
    for key in ("DRAMA_TXLAB_CONFIRM", "DRAMA_ENABLE_TXLAB_WRITE"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(TxLabDenied, match="manual"):
        run_live_txlab(url=GOOD, token="only-a-fake-secret", operator_approved=True)
    assert calls == []
    monkeypatch.setenv("DRAMA_TXLAB_CONFIRM", "RUN_ISOLATED_LIBSQL_TRANSACTION_CANARY")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_WRITE", "YES")
    with pytest.raises(TxLabDenied):
        run_live_txlab(url=BAD_PRODUCTION, token="only-a-fake-secret",
                       operator_approved=True)
    with pytest.raises(TxLabDenied, match="token"):
        run_live_txlab(url=GOOD, token="", operator_approved=True)
    assert calls == []


def test_mock_live_mode_runs_only_after_all_gates(tmp_path, monkeypatch):
    import drama_factory.storage.libsql_txlab as lab

    conn = sqlite_factory(tmp_path)
    monkeypatch.setenv("DRAMA_TXLAB_CONFIRM", "RUN_ISOLATED_LIBSQL_TRANSACTION_CANARY")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_WRITE", "YES")
    monkeypatch.setattr(lab, "_open_lab_connection", lambda url, token: conn())
    result = run_live_txlab(url=GOOD, token="fake_only_token", operator_approved=True)
    assert result["mode"] == "isolated_live"
    assert result["isolated_txlab_name_validated"] is True
    assert result["engine"] == "libsql"
    assert result["production_database_touched"] is False
    assert "fake_only_token" not in json.dumps(result)


def test_failure_does_not_recover_with_an_automatic_remote_retry(tmp_path):
    import drama_factory.storage.libsql_txlab as lab

    normal = sqlite_factory(tmp_path)
    count = 0
    class FailOnSecondConnection:
        def __init__(self, db):
            self.db = db
        def execute(self, sql, params=()):
            if sql == "BEGIN IMMEDIATE":
                raise sqlite3.OperationalError("SDK includes SECRET_BEARER in error")
            return self.db.execute(sql, params)
        def commit(self):
            return self.db.commit()
        def rollback(self):
            return self.db.rollback()
        def close(self):
            return self.db.close()

    def factory():
        nonlocal count
        count += 1
        db = normal()
        return db if count == 1 else FailOnSecondConnection(db)

    with pytest.raises(TxLabDenied, match="Independent connection"):
        run_transaction_contract(factory, mode="offline_fake")
    assert count == 3  # main and each worker; no automatic retries
    with normal() as db:
        result = db.execute(
            "SELECT COUNT(*) FROM pr31_txlab_transaction_probe_v1"
        ).fetchone()[0]
    assert result == 1


def test_cli_never_logs_sdk_error_or_token(tmp_path, monkeypatch, capsys):
    import drama_factory.storage.libsql_txlab as lab

    monkeypatch.setenv("DRAMA_TXLAB_DATABASE_URL", GOOD)
    monkeypatch.setenv("DRAMA_TXLAB_AUTH_TOKEN", "SECRET_TOKEN_MUST_NOT_LEAK")
    monkeypatch.setenv("DRAMA_TXLAB_CONFIRM", "RUN_ISOLATED_LIBSQL_TRANSACTION_CANARY")
    monkeypatch.setenv("DRAMA_ENABLE_TXLAB_WRITE", "YES")
    def failing_connect(*args, **kwargs):
        raise RuntimeError("libsql SDK header SECRET_TOKEN_MUST_NOT_LEAK")
    monkeypatch.setattr(lab, "_open_lab_connection", failing_connect)
    assert run_cli(["--live"]) == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert "SECRET_TOKEN_MUST_NOT_LEAK" not in result.err
    assert "Traceback" not in result.err
    assert "details redacted" in result.err
    assert run_cli([]) == 1


def test_manual_workflow_scope_and_no_automatic_execution():
    from pathlib import Path

    yml = (Path(__file__).resolve().parents[1] /
           ".github/workflows/manual-isolated-libsql-txlab.yml").read_text()
    assert "workflow_dispatch:" in yml
    assert "pull_request:" not in yml
    assert "\n  push:" not in yml
    assert "inputs.confirmation == 'RUN_ISOLATED_LIBSQL_TRANSACTION_CANARY'" in yml
    assert "secrets.DRAMA_TXLAB_DATABASE_URL" in yml
    assert "secrets.DRAMA_TXLAB_AUTH_TOKEN" in yml
    assert "secrets.DRAMA_TURSO_DATABASE_URL" not in yml
    assert "secrets.DRAMA_TURSO_AUTH_TOKEN" not in yml
    assert "secrets.DRAMA_DRIVE_USER_OAUTH_JSON" not in yml
    assert "DRAMA_ENABLE_TXLAB_WRITE: 'YES'" in yml
    assert "contents: read" in yml
    assert "python -m drama_factory.storage.libsql_txlab --live" in yml
