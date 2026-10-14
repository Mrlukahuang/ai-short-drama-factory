"""v5 old workflow stays locked; observer logic is SQL read-only & portable."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from drama_factory.storage.txlab_v5_isolated_dual_runner import (
    stage_setup, stage_actor, stage_seal, stage_observe,
)


class SelectOnlyConnection:
    """Act like the remote SDK: reject any connection-setting PRAGMA or DML.

    The only allowed statements are fixed read paths. This is an in-process
    safety simulation, NOT proof of real server-issued read-only credentials.
    """
    def __init__(self, wrapped):
        self.wrapped = wrapped
        self.statements = []

    def execute(self, sql, params=()):
        if (
            sql != "BEGIN"
            and sql != "PRAGMA foreign_key_check"
            and not sql.lstrip().upper().startswith("SELECT ")
        ):
            raise ValueError("query_only PRAGMA unsupported by remote libsql")
        self.statements.append(sql)
        return self.wrapped.execute(sql, params)

    def rollback(self):
        return self.wrapped.rollback()

    def close(self):
        return self.wrapped.close()


def _connect_local(path):
    conn = sqlite3.connect(path, timeout=12)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _run_preexisting_synthetic_snapshot(db_path):
    factory = lambda: _connect_local(db_path)
    stage_setup(factory, run_id=7701)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(stage_actor, factory, run_id=7701, job_id=301, role="a", wait_seconds=10)
        b = pool.submit(stage_actor, factory, run_id=7701, job_id=302, role="b", wait_seconds=10)
        receipts = (a.result(timeout=30), b.result(timeout=30))
    assert sorted(x["outcome"] for x in receipts) == ["accepted", "denied"]
    stage_seal(factory)
    return receipts


def test_observer_works_when_remote_query_only_pragma_is_unsupported(tmp_path):
    path = tmp_path / "synthetic-v5-local.sqlite"
    a, b = _run_preexisting_synthetic_snapshot(path)
    before = path.read_bytes()
    read_statements = []

    def only_reads():
        conn = SelectOnlyConnection(_connect_local(path))
        original = conn.close
        def record_and_close():
            read_statements.extend(conn.statements)
            original()
        conn.close = record_and_close
        return conn

    receipt = stage_observe(only_reads, run_id=7701, job_id=303,
                            actor_a=a, actor_b=b)
    assert receipt["independent_remote_readback_consistent"] is True
    assert receipt["read_only_sql_path"] is True
    assert receipt["database_level_read_only_token_verified"] is False
    assert receipt["remote_multi_runner_verified"] is False
    assert receipt["live_cutover_permitted"] is False
    assert receipt["paid_provider_calls"] == 0
    assert "BEGIN" in read_statements
    assert "PRAGMA foreign_key_check" in read_statements
    assert "PRAGMA query_only=ON" not in read_statements
    assert not any("INSERT" in x or "UPDATE" in x for x in read_statements)
    assert path.read_bytes() == before


def test_observer_fails_closed_if_foreign_key_integrity_fails(tmp_path):
    path = tmp_path / "synthetic-invalid-fk.sqlite"
    a, b = _run_preexisting_synthetic_snapshot(path)
    # Deliberately create an orphan FK, in setup phase of the TEST, not in
    # the read-only observer or any real remote environment.
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("INSERT INTO pr31_v5_holds VALUES ('z',40,1)")
    with pytest.raises(Exception, match="Remote foreign key check rejected"):
        stage_observe(lambda: SelectOnlyConnection(_connect_local(path)),
                      run_id=7701, job_id=303, actor_a=a, actor_b=b)


def test_observer_rejects_forged_actor_receipts_with_select_only_session(tmp_path):
    path = tmp_path / "synthetic-forged-evidence.sqlite"
    a, b = _run_preexisting_synthetic_snapshot(path)
    fake_b = dict(b, github_job_id=a["github_job_id"])
    from drama_factory.storage.pr31_v5_offline_evidence_guard import V5EvidenceDenied
    with pytest.raises(V5EvidenceDenied):
        stage_observe(lambda: SelectOnlyConnection(_connect_local(path)),
                      run_id=7701, job_id=303, actor_a=a, actor_b=fake_b)
