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
from drama_factory.storage.txlab_v2 import _TABLE as _TABLE_V2
from drama_factory.storage.txlab_multitable_v3 import (
    create_v3_fixture, reconcile_v3_local,
)

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


def build_factory(path, *, table=False, counters=(), v2_table=False, v2_counters=()):
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
        if v2_table:
            db.execute(
                f"CREATE TABLE {_TABLE_V2} ("
                "probe_id TEXT PRIMARY KEY, counter INTEGER NOT NULL, marker TEXT)"
            )
            for i, counter in enumerate(v2_counters):
                db.execute(
                    f"INSERT INTO {_TABLE_V2} VALUES (?,?,?)",
                    (f"private_v2_id_{i}", counter, "PRIVATE_V2_MARKER"),
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
    assert receipt["v2_test_table_exists"] is False
    assert receipt["v2_aggregate_test_row_counts"] is None
    assert receipt["connection_ping_succeeded"] is True
    assert receipt["database_modified_by_this_check"] is False
    assert receipt["production_database_touched"] is False
    assert receipt["previous_canary_commit_state_fully_known"] is False
    assert all(c.closed for c in opened)
    assert len(opened[0].sql) == 4
    assert receipt["v3_schema_objects_present"] == 0
    assert receipt["v3_schema_names_complete"] is False
    assert receipt["v3_reservation_aggregate"] is None
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
    assert len(opened[0].sql) == 5
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


@pytest.mark.parametrize("v2_counters,expected", [
    ([], (0, 0, 0, 0, 0, 0, 0)),
    ([2], (1, 0, 0, 1, 0, 0, 0)),
    ([3], (1, 0, 0, 0, 1, 0, 0)),
    ([4], (1, 0, 0, 0, 0, 1, 0)),
    ([0, 1, 2, 3, 4, 7], (6, 1, 1, 1, 1, 1, 1)),
])
def test_v2_aggregate_reports_only_counter_distribution(
    tmp_path, monkeypatch, v2_counters, expected,
):
    approve(monkeypatch)
    path = tmp_path / "v2-recovery-audit.db"
    factory, opened = build_factory(
        path, table=True, counters=[1],
        v2_table=True, v2_counters=v2_counters,
    )
    before = path.read_bytes()
    receipt = inspect_txlab_readonly(
        URL, "fake-token-not-to-print", operator_approved=True,
        connection_factory=factory,
    )
    assert path.read_bytes() == before
    assert receipt["test_table_exists"] is True
    assert receipt["aggregate_test_row_counts"]["counter_one_rows"] == 1
    assert receipt["v2_test_table_exists"] is True
    assert tuple(receipt["v2_aggregate_test_row_counts"].values()) == expected
    assert receipt["database_modified_by_this_check"] is False
    assert receipt["previous_canary_commit_state_fully_known"] is False
    assert len(opened[0].sql) == 6
    assert all(query.lstrip().upper().startswith("SELECT ") for query in opened[0].sql)
    assert opened[0].closed is True
    payload = json.dumps(receipt, sort_keys=True)
    for secret in (
        "PRIVATE_V2_MARKER", "private_v2_id", "fake-token-not-to-print",
        "mrlukahuang", str(path),
    ):
        assert secret not in payload


@pytest.mark.parametrize("fail_index,expected", [
    (4, "select_v2_schema"),
    (5, "select_v2_counter_summary"),
])
def test_v2_read_failures_have_fixed_redacted_stage(
    tmp_path, monkeypatch, fail_index, expected,
):
    approve(monkeypatch)
    path = tmp_path / "known-v2.db"
    build_factory(path, table=True, counters=[1], v2_table=True, v2_counters=[2])

    class FailingV2Read:
        def __init__(self):
            self.db = sqlite3.connect(path)
            self.reads = 0
            self.closed = False

        def execute(self, sql, params=()):
            assert sql.strip().upper().startswith("SELECT ")
            self.reads += 1
            if self.reads == fail_index:
                raise RuntimeError("HIDDEN_V2_BEARER_OR_ACCOUNT_ID")
            return self.db.execute(sql, params)

        def close(self):
            self.closed = True
            self.db.close()

    opened = []
    def factory(*_):
        conn = FailingV2Read()
        opened.append(conn)
        return conn

    with pytest.raises(ReadOnlyTxLabFailure) as exc:
        inspect_txlab_readonly(
            URL, "fake-token-not-to-print", operator_approved=True,
            connection_factory=factory,
        )
    assert exc.value.stage == expected
    assert "HIDDEN" not in str(exc.value)
    assert all(instance.closed for instance in opened)


def test_both_v1_and_v2_are_checked_without_cloud_imports(tmp_path, monkeypatch):
    import builtins

    approve(monkeypatch)
    path = tmp_path / "both-v1-v2.db"
    factory, opened = build_factory(
        path, table=True, counters=[1], v2_table=True, v2_counters=[2],
    )
    original = builtins.__import__
    def forbid_cloud(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "googleapiclient")):
            raise AssertionError("Unexpected remote SDK import")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid_cloud)
    receipt = inspect_txlab_readonly(
        URL, "fake-token-not-to-print", operator_approved=True,
        connection_factory=factory,
    )
    assert receipt["v2_aggregate_test_row_counts"]["counter_two_rows"] == 1
    assert receipt["aggregate_test_row_counts"]["counter_one_rows"] == 1
    assert opened[0].closed is True


@pytest.mark.parametrize("reconciled", [False, True])
def test_v3_complete_schema_stable_only_read_aggregates(
    tmp_path, monkeypatch, reconciled,
):
    approve(monkeypatch)
    path = create_v3_fixture(
        tmp_path / "v3-synthetic-only.sqlite", isolated_test_only=True,
    )
    if reconciled:
        reconcile_v3_local(path, isolated_test_only=True)
    opened = []
    def factory(url, token):
        assert url == URL
        assert token == "fake-token-not-to-print"
        conn = StrictReadConn(sqlite3.connect(path))
        opened.append(conn)
        return conn

    before = path.read_bytes()
    receipt = inspect_txlab_readonly(
        URL, "fake-token-not-to-print",
        operator_approved=True, connection_factory=factory,
    )
    assert path.read_bytes() == before
    assert receipt["v3_schema_objects_present"] == 10
    assert receipt["v3_schema_names_complete"] is True
    assert receipt["v3_remote_transaction_semantics_verified"] is False
    assert receipt["v3_reservation_aggregate"] == {
        "total": 1,
        "held": 0 if reconciled else 1,
        "reconciled": 1 if reconciled else 0,
        "charge_45_cents": 1 if reconciled else 0,
        "charge_null": 0 if reconciled else 1,
    }
    assert receipt["v3_job_aggregate"] == {
        "total": 1, "charge_45_cents": 1 if reconciled else 0,
        "charge_null": 0 if reconciled else 1,
        "intent_recorded": 1,
    }
    assert receipt["v3_budget_event_aggregate"] == {
        "total": 2 if reconciled else 1,
        "held": 1,
        "reconciled": 1 if reconciled else 0,
    }
    assert receipt["database_modified_by_this_check"] is False
    assert receipt["production_database_touched"] is False
    assert all(x.closed for x in opened)
    assert len(opened[0].sql) == 7
    assert all(s.lstrip().upper().startswith("SELECT ") for s in opened[0].sql)
    payload = json.dumps(receipt)
    for private in (
        str(path), "fake-token-not-to-print", "synthetic_job_a",
        "synthetic_reservation", "mrlukahuang",
    ):
        assert private not in payload


def test_v3_partial_schema_report_refuses_to_call_missing_tables(
    tmp_path, monkeypatch,
):
    approve(monkeypatch)
    path = tmp_path / "partial-v3-ddl.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE pr31_v3_policy (marker TEXT PRIMARY KEY)")
    opened = []
    def factory(url, token):
        conn = StrictReadConn(sqlite3.connect(path))
        opened.append(conn)
        return conn

    before = path.read_bytes()
    report = inspect_txlab_readonly(
        URL, "fake-token-not-to-print",
        operator_approved=True, connection_factory=factory,
    )
    assert before == path.read_bytes()
    assert report["v3_schema_objects_present"] == 1
    assert report["v3_schema_names_complete"] is False
    assert report["v3_reservation_aggregate"] is None
    assert report["v3_job_aggregate"] is None
    assert report["v3_budget_event_aggregate"] is None
    assert len(opened[0].sql) == 4
    assert all(x.closed for x in opened)


@pytest.mark.parametrize("blocked_sql,expected_stage", [
    ("FROM pr31_v3_reservation", "select_v3_reservation"),
    ("FROM pr31_v3_job", "select_v3_job"),
    ("FROM pr31_v3_budget_event", "select_v3_budget_event"),
])
def test_v3_read_errors_are_redacted_and_do_not_commit(
    tmp_path, monkeypatch, blocked_sql, expected_stage,
):
    approve(monkeypatch)
    path = create_v3_fixture(
        tmp_path / "fault-read-v3.sqlite", isolated_test_only=True,
    )
    class FaultyRead:
        def __init__(self):
            self.db = sqlite3.connect(path)
            self.closed = False
        def execute(self, sql, params=()):
            if blocked_sql in sql:
                raise RuntimeError("SECRET_CREDENTIAL_MUST_NOT_LEAK")
            assert sql.lstrip().upper().startswith("SELECT ")
            return self.db.execute(sql, params)
        def close(self):
            self.closed = True
            self.db.close()
    opened = []
    def factory(*_):
        conn = FaultyRead()
        opened.append(conn)
        return conn

    with pytest.raises(ReadOnlyTxLabFailure) as exc:
        inspect_txlab_readonly(
            URL, "fake-token-not-to-print",
            operator_approved=True, connection_factory=factory,
        )
    assert exc.value.stage == expected_stage
    assert "SECRET" not in str(exc.value)
    assert all(x.closed for x in opened)


def test_v3_catalogue_query_fail_closed_before_any_table_access(tmp_path, monkeypatch):
    approve(monkeypatch)
    path = create_v3_fixture(
        tmp_path / "failed-catalogue-v3.sqlite", isolated_test_only=True,
    )
    class CatalogueDown:
        def __init__(self):
            self.db = sqlite3.connect(path)
        def execute(self, sql, params=()):
            if "name LIKE 'pr31_v3_%'" in sql:
                raise ConnectionError("connection reset PRIVATE_BEARER")
            assert sql.lstrip().upper().startswith("SELECT ")
            return self.db.execute(sql, params)
        def close(self):
            self.db.close()
    with pytest.raises(ReadOnlyTxLabFailure) as exc:
        inspect_txlab_readonly(
            URL, "fake-token-not-to-print", operator_approved=True,
            connection_factory=lambda *_: CatalogueDown(),
        )
    assert exc.value.stage == "select_v3_schema"
    assert "PRIVATE_BEARER" not in str(exc.value)
