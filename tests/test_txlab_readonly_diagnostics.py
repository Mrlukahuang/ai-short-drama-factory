"""Offline tests for safe TxLab postfailure investigation: never writes or retries."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from drama_factory.storage.txlab_readonly_diagnostics import (
    ReadOnlyTxLabFailure, inspect_txlab_readonly, run_cli,
)
from drama_factory.storage.libsql_txlab import _TABLE

URL = "libsql://ai-short-drama-factory-txlab-mrlukahuang.aws-ap-southeast-2.turso.io"
PROD_URL = "libsql://ai-short-drama-factory-mrlukahuang.aws-ap-southeast-2.turso.io"


class StrictReadConn:
    def __init__(self, db):
        self.db = db
        self.sql = []
        self.closed = False

    def execute(self, sql, params=()):
        assert sql.lstrip().upper().startswith("SELECT "), "Read-only tool attempted a write"
        self.sql.append(sql)
        return self.db.execute(sql, params)

    def close(self):
        self.closed = True
        self.db.close()


def build_factory(path, *, table=False, counters=()):
    with sqlite3.connect(path) as db:
        if table:
            db.execute(
                f"CREATE TABLE {_TABLE} ("
                "probe_id TEXT PRIMARY KEY, counter INTEGER NOT NULL, marker TEXT)"
            )
            for i, counter in enumerate(counters):
                db.execute(
                    f"INSERT INTO {_TABLE} VALUES (?,?,?)",
                    (f"secret_probe_{i}", counter, "SECRET_MARKER"),
                )
    instances = []
    def factory(url, token):
        assert url == URL
        assert token == "fake-token-not-to-print"
        item = StrictReadConn(sqlite3.connect(path))
        instances.append(item)
        return item
    return factory, instances


def approve(monkeypatch):
    monkeypatch.setenv("DRAMA_TXLAB_READONLY_CONFIRM", "CHECK_ISOLATED_TXLAB_READ_ONLY")


def test_no_ddl_or_dml_when_lab_table_missing(tmp_path, monkeypatch):
    approve(monkeypatch)
    dbpath = tmp_path / "fresh.db"
    factory, opened = build_factory(dbpath)
    prior = dbpath.read_bytes()
    receipt = inspect_txlab_readonly(
        URL, "fake-token-not-to-print", operator_approved=True,
        connection_factory=factory,
    )
    assert prior == dbpath.read_bytes()
    assert receipt["test_table_exists"] is False
    assert receipt["aggregate_test_row_counts"] is None
    assert receipt["connection_ping_succeeded"] is True
    assert receipt["database_modified_by_this_check"] is False
    assert receipt["production_database_touched"] is False
    assert receipt["previous_canary_commit_state_fully_known"] is False
    assert all(c.closed for c in opened)
    assert len(opened[0].sql) == 2
    assert all(sql.startswith("SELECT ") for sql in opened[0].sql)


@pytest.mark.parametrize("counters,counts", [
    ([], (0, 0, 0, 0, 0)),
    ([0], (1, 1, 0, 0, 0)),
    ([2], (1, 0, 0, 1, 0)),
    ([0, 1, 2, 3, 4], (5, 1, 1, 1, 2)),
])
def test_aggregate_only_exposes_no_probe_ids(tmp_path, monkeypatch, counters, counts):
    approve(monkeypatch)
    dbpath = tmp_path / "canary-previously-started.db"
    factory, opened = build_factory(dbpath, table=True, counters=counters)
    prior = dbpath.read_bytes()
    receipt = inspect_txlab_readonly(
        URL, "fake-token-not-to-print", operator_approved=True,
        connection_factory=factory,
    )
    assert dbpath.read_bytes() == prior
    assert receipt["test_table_exists"] is True
    values = receipt["aggregate_test_row_counts"]
    assert tuple(values.values()) == counts
    payload = json.dumps(receipt)
    for secret in (
        "fake-token-not-to-print", "SECRET_MARKER", "secret_probe_",
        "mrlukahuang", str(dbpath),
    ):
        assert secret not in payload
    assert len(opened[0].sql) == 3
    assert all(x.closed for x in opened)


def test_missing_confirmation_or_prod_url_fails_before_connection(monkeypatch):
    calls = []
    def forbidden(*args):
        calls.append(args)
        raise AssertionError("Never connect to production")
    monkeypatch.delenv("DRAMA_TXLAB_READONLY_CONFIRM", raising=False)
    with pytest.raises(ReadOnlyTxLabFailure) as exc:
        inspect_txlab_readonly(
            URL, "fake-token", operator_approved=True,
            connection_factory=forbidden,
        )
    assert exc.value.stage == "target_validation"
    approve(monkeypatch)
    for url, token in ((PROD_URL, "fake-token"), (URL, "")):
        with pytest.raises(ReadOnlyTxLabFailure) as exc:
            inspect_txlab_readonly(
                url, token, operator_approved=True,
                connection_factory=forbidden,
            )
        assert exc.value.stage == "target_validation"
    assert calls == []


def test_connect_failure_only_leaks_safe_stage(monkeypatch, capsys):
    import drama_factory.storage.txlab_readonly_diagnostics as diag
    approve(monkeypatch)
    monkeypatch.setenv("DRAMA_TXLAB_DATABASE_URL", URL)
    monkeypatch.setenv("DRAMA_TXLAB_AUTH_TOKEN", "TEST_SECRET_NOT_TO_LEAK")
    def failing_connect(*args):
        raise RuntimeError("TEST_SECRET_NOT_TO_LEAK and user ID sensitive")
    monkeypatch.setattr(diag, "_open_lab_connection", failing_connect)
    assert run_cli(["--live"]) == 1
    report = capsys.readouterr()
    assert report.out == ""
    assert "stage=connect" in report.err
    assert "TEST_SECRET_NOT_TO_LEAK" not in report.err
    assert "Traceback" not in report.err
    assert "details redacted" in report.err


@pytest.mark.parametrize("fail_index,expected", [
    (1, "select_ping"),
    (2, "select_schema"),
    (3, "select_counter_summary"),
])
def test_sql_errors_only_expose_fixed_stage(tmp_path, monkeypatch, fail_index, expected):
    approve(monkeypatch)
    dbpath = tmp_path / "test.db"
    build_factory(dbpath, table=True, counters=[0])
    class FailedConn:
        def __init__(self):
            self.db = sqlite3.connect(dbpath)
            self.n = 0
        def execute(self, sql, params=()):
            self.n += 1
            if self.n == fail_index:
                raise RuntimeError("SECRET AUTH TOKEN should never be displayed")
            return self.db.execute(sql, params)
        def close(self):
            self.db.close()
    with pytest.raises(ReadOnlyTxLabFailure) as exc:
        inspect_txlab_readonly(
            URL, "fake-token-not-to-print", operator_approved=True,
            connection_factory=lambda *_: FailedConn(),
        )
    assert exc.value.stage == expected
    assert "SECRET" not in str(exc.value)


def test_manual_workflow_only_uses_txlab_secrets_and_select_tool():
    text = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/manual-txlab-readonly-diagnostics.yml"
    ).read_text()
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "\n  push:" not in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "inputs.confirmation == 'CHECK_ISOLATED_TXLAB_READ_ONLY'" in text
    assert "secrets.DRAMA_TXLAB_DATABASE_URL" in text
    assert "secrets.DRAMA_TXLAB_AUTH_TOKEN" in text
    assert "secrets.DRAMA_TURSO_DATABASE_URL" not in text
    assert "secrets.DRAMA_TURSO_AUTH_TOKEN" not in text
    assert "DRAMA_ENABLE_TXLAB_WRITE" not in text
    assert "python -m drama_factory.storage.txlab_readonly_diagnostics --live" in text
    assert "python -m drama_factory.storage.libsql_txlab --live" not in text
    assert "contents: read" in text
