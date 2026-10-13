"""Deterministic single-writer contention on a NEW local SQLite fixture only."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from drama_factory.storage.txlab_retry_policy import assess_txlab_retry


def test_no_wait_parallel_writers_produce_busy_not_silent_lost_update(tmp_path):
    path = tmp_path / "pr31b2d-isolated-sqlite-only.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE progress (id INTEGER PRIMARY KEY, count INTEGER NOT NULL)")
        db.execute("INSERT INTO progress VALUES (1,0)")
    began, rejected = Event(), Event()

    def first_writer():
        with sqlite3.connect(path, timeout=0, isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            began.set()
            assert rejected.wait(timeout=10)
            db.execute("UPDATE progress SET count=count+1 WHERE id=1")
            db.commit()

    def concurrent_writer():
        assert began.wait(timeout=10)
        with sqlite3.connect(path, timeout=0, isolation_level=None) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as exc:
                assert ("locked" in str(exc).lower() or "busy" in str(exc).lower())
                return "SQLITE_BUSY_AT_BEGIN"
            finally:
                rejected.set()
        raise AssertionError("Expected deterministic immediate writer lock conflict")

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first_writer)
        b = pool.submit(concurrent_writer)
        assert b.result(timeout=15) == "SQLITE_BUSY_AT_BEGIN"
        a.result(timeout=15)

    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count FROM progress WHERE id=1").fetchone()[0] == 1

    decision = assess_txlab_retry(
        stage="worker_begin", error_category="busy",
        begin_definitively_rejected=True, write_sql_executed=False,
        prior_retry_attempts=0,
    )
    assert decision.may_retry_pre_begin is True
    assert decision.maximum_additional_attempts == 1
    assert decision.review_required is False

    # Explicit, controlled OFFLINE rerun only after the prior transaction ends.
    # This is NOT an automatically called retry in the application.
    with sqlite3.connect(path, timeout=0, isolation_level=None) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE progress SET count=count+1 WHERE id=1")
        db.commit()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count FROM progress WHERE id=1").fetchone()[0] == 2


@pytest.mark.parametrize("kwargs,reason", [
    (
        dict(stage="worker_commit", error_category="busy",
             begin_definitively_rejected=False, write_sql_executed=True,
             prior_retry_attempts=0),
        "transaction_or_commit_uncertain",
    ),
    (
        dict(stage="worker_update", error_category="busy",
             begin_definitively_rejected=False, write_sql_executed=True,
             prior_retry_attempts=0),
        "transaction_or_commit_uncertain",
    ),
    (
        dict(stage="worker_begin", error_category="timeout",
             begin_definitively_rejected=False, write_sql_executed=False,
             prior_retry_attempts=0),
        "not_confirmed_lock_busy",
    ),
    (
        dict(stage="worker_begin", error_category="busy",
             begin_definitively_rejected=False, write_sql_executed=False,
             prior_retry_attempts=0),
        "begin_outcome_not_proven_safe",
    ),
    (
        dict(stage="worker_begin", error_category="busy",
             begin_definitively_rejected=True, write_sql_executed=True,
             prior_retry_attempts=0),
        "begin_outcome_not_proven_safe",
    ),
    (
        dict(stage="worker_begin", error_category="busy",
             begin_definitively_rejected=True, write_sql_executed=False,
             prior_retry_attempts=1),
        "bounded_retry_limit_reached",
    ),
    (
        dict(stage="worker_begin", error_category="busy",
             begin_definitively_rejected=True, write_sql_executed=False,
             prior_retry_attempts=-1),
        "invalid_attempt_counter",
    ),
])
def test_all_ambiguous_or_over_limit_states_block_retry(kwargs, reason):
    result = assess_txlab_retry(**kwargs)
    assert result.may_retry_pre_begin is False
    assert result.review_required is True
    assert result.maximum_additional_attempts == 0
    assert result.reason == reason


def test_this_policy_is_local_pure_data_and_never_imports_libsql(monkeypatch):
    import builtins
    original = builtins.__import__

    def forbid_remote(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "googleapiclient")):
            raise AssertionError("unexpected remote SDK import")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid_remote)
    result = assess_txlab_retry(
        stage="worker_begin", error_category="busy",
        begin_definitively_rejected=True, write_sql_executed=False,
        prior_retry_attempts=0,
    )
    assert result.may_retry_pre_begin is True
    # No connection, no writes, no Secrets and no actual retry made here.
