"""PR-31b2n: ACTUAL business DDL on native libsql==0.1.11, LOCAL only.

This builds an entirely disposable in-memory SQLite *catalog* from the
repository's real db.SCHEMA (never reads a production file or payload).
Individual whitelisted CREATE statements are then executed by the native
libSQL SDK in a new pytest temp-file DB. No remote connection or Secrets.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from drama_factory.db import SCHEMA

libsql = pytest.importorskip("libsql")

_TABLES = (
    "columns", "projects", "episodes", "productions",
    "shot_jobs", "shot_job_events", "budget_policies",
    "job_budget_reservations", "budget_reservation_events",
)
_INDEXES = (
    "idx_columns_slug", "idx_shot_jobs_series_status",
    "idx_shot_jobs_provider_task", "idx_shot_events_job",
    "idx_budget_policies_scope", "idx_job_budget_daily",
)
_TRIGGERS = (
    "shot_job_events_immutable_update",
    "shot_job_events_immutable_delete",
    "budget_events_immutable_update",
    "budget_events_immutable_delete",
)
_NOW = "2026-10-14T00:00:00+00:00"


def _real_production_ddl():
    """Extract named, actual source DDL; never synthesize weaker mock tables."""
    with sqlite3.connect(":memory:") as reference:
        reference.executescript(SCHEMA)  # trusted source in test-only sqlite3
        entries = {
            (kind, name): sql for kind, name, sql in reference.execute(
                "SELECT type,name,sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%'"
            )
        }
    assert len(_TABLES) == 9
    assert len(_INDEXES) == 6
    assert len(_TRIGGERS) == 4
    # Creation order must follow FK parent tables, then secondary structures.
    return [
        entries[(kind, name)]
        for kind, names in (
            ("table", _TABLES), ("index", _INDEXES), ("trigger", _TRIGGERS)
        )
        for name in names
    ]


def _conn(path: Path):
    assert "://" not in str(path)
    assert path.parent.is_dir()
    connection = libsql.connect(database=str(path), timeout=5.0)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    except BaseException:
        connection.close()
        raise
    return connection


def _create_real_schema(path: Path):
    conn = _conn(path)
    try:
        for ddl in _real_production_ddl():
            assert not ddl.lstrip().upper().startswith("DROP")
            conn.execute(ddl)  # native SDK: NEVER executescript()
        conn.commit()
    finally:
        conn.close()


def _seed_real_ledger(path: Path):
    _create_real_schema(path)
    conn = _conn(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO columns "
            "(id,slug,name,description,default_visual_style,created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("col_test", "original-test", "Synthetic column", "Test", "anime", _NOW),
        )
        conn.execute(
            "INSERT INTO projects "
            "(id,title,premise,visual_style,ratio,created_at,column_id) "
            "VALUES (?,?,?,?,?,?,?)",
            ("series_test", "Original synthetic title", "Test only",
             "anime", "9:16", _NOW, "col_test"),
        )
        conn.execute(
            "INSERT INTO episodes "
            "(id,project_id,episode_number,title,body_json,created_at)"
            " VALUES (?,?,?,?,?,?)",
            ("episode_test", "series_test", 1, "Original episode", "{}", _NOW),
        )
        conn.execute(
            "INSERT INTO productions "
            "(id,episode_id,status,created_at,updated_at) VALUES (?,?,?,?,?)",
            ("run_test", "episode_test", "approved", _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO shot_jobs "
            "(id,production_id,episode_id,series_id,shot_id,provider,model_id,"
            "input_sha256,idempotency_key,max_acknowledged_spend_usd,status,"
            "generation_intent_recorded,lease_owner,lease_expires_at,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("job_test", "run_test", "episode_test", "series_test", "S01",
             "google", "fake_model", "f" * 64, "original-key-1", "1.00",
             "submission_intent", 1, "worker_fake", "2026-11-01T00:00:00+00:00",
             _NOW, _NOW),
        )
        for scope, scope_id, key in (
            ("column", "col_test", "policy-col"),
            ("series", "series_test", "policy-series"),
            ("provider", "google", "policy-provider"),
        ):
            conn.execute(
                "INSERT INTO budget_policies "
                "(id,scope,scope_id,revision,daily_limit_usd,max_active_jobs,enabled,created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (key, scope, scope_id, 1, "1.00", 2, 1, _NOW),
            )
        conn.execute(
            "INSERT INTO job_budget_reservations "
            "(id,job_id,column_id,series_id,provider,day_utc,reserved_usd,"
            "status,policy_snapshot_json,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("reserve_test", "job_test", "col_test", "series_test",
             "google", "2026-10-14", "0.40", "held", "[]", _NOW, _NOW),
        )
        conn.execute(
            "INSERT INTO shot_job_events "
            "(id,shot_job_id,action,previous_state,next_state,details_json,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            ("intent_event", "job_test", "generation_intent_recorded",
             "leased", "submission_intent", "{}", _NOW),
        )
        conn.execute(
            "INSERT INTO budget_reservation_events "
            "(id,reservation_id,action,details_json,created_at) "
            "VALUES (?,?,?,?,?)",
            ("held_event", "reserve_test", "held", "{}", _NOW),
        )
        conn.commit()
    finally:
        conn.close()


def _snapshot(path):
    conn = _conn(path)
    try:
        return (
            conn.execute(
                "SELECT status,actual_usd FROM job_budget_reservations "
                "WHERE id='reserve_test'"
            ).fetchone(),
            conn.execute(
                "SELECT status,actual_vendor_charge_usd FROM shot_jobs "
                "WHERE id='job_test'"
            ).fetchone(),
            conn.execute(
                "SELECT COUNT(*) FROM budget_reservation_events"
            ).fetchone()[0],
        )
    finally:
        conn.close()


def _reconcile(conn, *, fail_at=None):
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT status FROM job_budget_reservations WHERE id='reserve_test'"
        ).fetchone()
        if row is None or row[0] != "held":
            raise ValueError("Already recorded; do not replay")
        conn.execute(
            "UPDATE job_budget_reservations "
            "SET status='reconciled',actual_usd='0.55',"
            "evidence_reference='synthetic-review',reviewed_by='offline-operator' "
            "WHERE id='reserve_test'"
        )
        if fail_at == "reservation":
            raise ValueError("Synthetic reservation failure")
        conn.execute(
            "UPDATE shot_jobs SET actual_vendor_charge_usd='0.55' "
            "WHERE id='job_test'"
        )
        if fail_at == "job":
            raise ValueError("Synthetic job failure")
        conn.execute(
            "INSERT INTO budget_reservation_events "
            "(id,reservation_id,action,details_json,created_at) "
            "VALUES ('reconciled_event','reserve_test',"
            "'operator_entered_vendor_charge','{}',?)", (_NOW,),
        )
        if fail_at == "audit":
            raise ValueError("Synthetic audit failure")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


def test_actual_production_schema_subset_works_in_native_libsql_local(tmp_path):
    path = tmp_path / "real-shape-only.sqlite"
    _seed_real_ledger(path)
    conn = _conn(path)
    try:
        found = {
            (row[0], row[1]) for row in conn.execute(
                "SELECT type,name FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert len(found) == 19  # 9 real tables, 6 named indexes, 4 triggers
        assert {("table", t) for t in _TABLES}.issubset(found)
        assert {("index", i) for i in _INDEXES}.issubset(found)
        assert {("trigger", t) for t in _TRIGGERS}.issubset(found)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert len(conn.execute("PRAGMA table_info(shot_jobs)").fetchall()) >= 23
        assert len(conn.execute("PRAGMA table_info(job_budget_reservations)").fetchall()) >= 13
    finally:
        conn.close()
    assert _snapshot(path) == (
        ("held", None), ("submission_intent", None), 1,
    )


@pytest.mark.parametrize("stage", ["reservation", "job", "audit"])
def test_native_libsql_actual_business_columns_rollback_all_or_nothing(tmp_path, stage):
    path = tmp_path / "real-shape-rollback.sqlite"
    _seed_real_ledger(path)
    baseline = _snapshot(path)
    conn = _conn(path)
    try:
        with pytest.raises(ValueError, match="Synthetic"):
            _reconcile(conn, fail_at=stage)
    finally:
        conn.close()
    assert _snapshot(path) == baseline
    conn = _conn(path)
    try:
        _reconcile(conn)
    finally:
        conn.close()
    assert _snapshot(path) == (
        ("reconciled", "0.55"), ("submission_intent", "0.55"), 2,
    )


def test_actual_business_schema_fks_uniques_and_audit_are_enforced(tmp_path):
    path = tmp_path / "real-shape-constraints.sqlite"
    _seed_real_ledger(path)
    conn = _conn(path)
    try:
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO budget_reservation_events "
                "(id,reservation_id,action,details_json,created_at) "
                "VALUES ('orphan','nonexistent','bogus','{}',?)", (_NOW,),
            )
        conn.rollback()
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO job_budget_reservations "
                "(id,job_id,column_id,series_id,provider,day_utc,reserved_usd,"
                "status,policy_snapshot_json,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("duplicate_reserve", "job_test", "col_test", "series_test",
                 "google", "2026-10-14", "0.40", "held", "[]", _NOW, _NOW),
            )
        conn.rollback()
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO budget_policies "
                "(id,scope,scope_id,revision,daily_limit_usd,max_active_jobs,enabled,created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                ("duplicate-revision", "column", "col_test", 1, "1.00", 2, 1, _NOW),
            )
        conn.rollback()
        for sql in (
            "UPDATE shot_job_events SET action='tampered'",
            "DELETE FROM budget_reservation_events",
        ):
            with pytest.raises(Exception):
                conn.execute(sql)
            conn.rollback()
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute(
            "SELECT COUNT(*) FROM budget_reservation_events"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_native_sdk_tuple_rows_need_explicit_named_row_adapter_before_worker_switch(tmp_path):
    """Current jobs code indexes by row['status'], unlike SDK's PyTuple."""
    path = tmp_path / "real-shape-native-tuple.sqlite"
    _seed_real_ledger(path)
    conn = _conn(path)
    try:
        cursor = conn.execute(
            "SELECT status,actual_vendor_charge_usd FROM shot_jobs WHERE id=?",
            ("job_test",),
        )
        row = cursor.fetchone()
        assert type(row) is tuple
        assert row[0] == "submission_intent"
        with pytest.raises(TypeError):
            row["status"]
        assert tuple(col[0] for col in cursor.description) == (
            "status", "actual_vendor_charge_usd",
        )
        # No Worker switch until a separate mapping/fencing adapter is tested.
    finally:
        conn.close()
