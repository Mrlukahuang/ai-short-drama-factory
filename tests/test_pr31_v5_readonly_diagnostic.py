"""v5 read-only diagnosis is independent of consumed writer authorization."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from drama_factory.storage.pr31_v5_readonly_diagnostic import (
    inspect_v5_existing_readonly, cli,
)
from drama_factory.storage.txlab_v5_isolated_dual_runner import (
    stage_setup, stage_actor, stage_seal,
)


def _factory(file):
    def conn():
        result = sqlite3.connect(file, timeout=10)
        result.execute("PRAGMA foreign_keys=ON")
        return result
    return conn


def test_postmortem_reads_fixed_synthetic_ledger_only(tmp_path):
    path = tmp_path / "postmortem-local-only.sqlite"
    factory = _factory(path)
    stage_setup(factory, run_id=900)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(stage_actor, factory, run_id=900, job_id=101, role="a", wait_seconds=8)
        b = pool.submit(stage_actor, factory, run_id=900, job_id=102, role="b", wait_seconds=8)
        assert sorted((a.result(timeout=20)["outcome"], b.result(timeout=20)["outcome"])) == ["accepted","denied"]
    stage_seal(factory)
    before = path.read_bytes()
    result = inspect_v5_existing_readonly(factory)
    assert result["ledger_probes_consistent"] is True
    assert result["prior_query_only_pragma_compatible"] is True
    assert all(x == "ok" for x in result["stages"].values())
    assert result["remote_multi_runner_verified"] is False
    assert result["additional_remote_writes"] == result["paid_provider_calls"] == 0
    assert result["may_retry_original_v5_run"] is False
    assert result["live_cutover_permitted"] is False
    assert path.read_bytes() == before


def test_partial_or_missing_db_is_reported_fail_closed_without_mutation(tmp_path):
    path = tmp_path / "no-schema.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("SELECT 1")
    before = path.read_bytes()
    report = inspect_v5_existing_readonly(_factory(path))
    assert report["ledger_probes_consistent"] is False
    assert report["stages"]["select_one"] == "ok"
    assert report["stages"]["gate"] == "query_unavailable"
    assert report["additional_remote_writes"] == 0
    assert path.read_bytes() == before


def test_unknown_driver_errors_never_echo_exception_text():
    class BadConnection:
        def execute(self, sql):
            raise RuntimeError("PRIVATE_TOKEN SECRET_DATABASE_URL")
        def close(self):
            pass
    x = inspect_v5_existing_readonly(lambda: BadConnection())
    assert x["ledger_probes_consistent"] is False
    assert all(z == "query_unavailable" for z in x["stages"].values())
    assert "SECRET" not in str(x) and "PRIVATE_TOKEN" not in str(x)


def test_cli_requires_new_readonly_specific_credentials_even_for_nonwrite(monkeypatch, capsys):
    for key in (
        "DRAMA_V5_READONLY_CONFIRM", "DRAMA_V5_DIAG_MAX_USD",
        "DRAMA_TXLAB_DATABASE_URL", "DRAMA_TXLAB_AUTH_TOKEN"
    ):
        monkeypatch.delenv(key, raising=False)
    assert cli([]) == 1
    assert "denied" in capsys.readouterr().err.lower()


def test_diagnostic_sql_has_no_dml_or_schema_mutation():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] /
              "src/drama_factory/storage/pr31_v5_readonly_diagnostic.py").read_text("utf-8")
    for forbidden in ('c.execute("INSERT', 'c.execute("UPDATE', 'c.execute("DELETE',
                      'c.execute("DROP', 'c.execute("CREATE',
                      'c.execute("BEGIN IMMEDIATE', 'conn.execute("INSERT',
                      'conn.execute("UPDATE'):
        assert forbidden not in source
    assert "sqlite_master" not in source
    assert "pr31_v5_" in source
