"""PR-31b2l0: test the ACTUAL libsql Python SDK, locally and without Secrets.

This module is skipped when libsql is absent in the normal Python/FFmpeg CI.
The dedicated sdk-local job installs libsql==0.1.11 and MUST run these tests.

No libsql:// or HTTPS database URL, no auth tokens, no remote or paid calls,
no real business table or media files. Files live under pytest tmp_path only.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from drama_factory.storage.txlab_multitable_v3 import SCHEMA_V3

libsql = pytest.importorskip("libsql")


def _local_conn(path: Path):
    database = str(path)
    assert "://" not in database and database != ":memory:"
    return libsql.connect(database=database, timeout=5.0)


def _create_local_sdk_schema(path: Path):
    conn = _local_conn(path)
    try:
        # FK enforcement is connection-scoped; it must be set and verified
        # BEFORE starting a transaction or running any write statement.
        conn.execute("PRAGMA foreign_keys=ON")
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

        # Deliberately NEVER call libsql.Connection.executescript(): the SDK
        # implementation has a code path that discards execute_batch errors.
        for ddl in SCHEMA_V3:
            conn.execute(ddl)
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pr31_v3_policy VALUES "
            "('pr31-v3-synthetic-fixture-only',60)"
        )
        conn.execute(
            "INSERT INTO pr31_v3_job VALUES "
            "('synthetic_job_a','fake',NULL,'idempotency-test-only',"
            "'submission_intent',1,NULL)"
        )
        conn.execute(
            "INSERT INTO pr31_v3_job_event VALUES "
            "('synthetic_intent','synthetic_job_a','intent')"
        )
        conn.execute(
            "INSERT INTO pr31_v3_reservation VALUES "
            "('synthetic_budget','synthetic_job_a',"
            "'pr31-v3-synthetic-fixture-only',40,NULL,'held')"
        )
        conn.execute(
            "INSERT INTO pr31_v3_budget_event VALUES "
            "('synthetic_held','synthetic_budget','held')"
        )
        conn.commit()
    finally:
        conn.close()


def _snapshot(path: Path):
    conn = _local_conn(path)
    try:
        return (
            conn.execute(
                "SELECT status,actual_cents FROM pr31_v3_reservation "
                "WHERE id='synthetic_budget'"
            ).fetchone(),
            conn.execute(
                "SELECT status,actual_charge_cents FROM pr31_v3_job "
                "WHERE id='synthetic_job_a'"
            ).fetchone(),
            conn.execute(
                "SELECT COUNT(*) FROM pr31_v3_budget_event"
            ).fetchone()[0],
        )
    finally:
        conn.close()


def _do_billing(conn, *, fail_stage=None):
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT status FROM pr31_v3_reservation "
            "WHERE id='synthetic_budget'"
        ).fetchone()
        if row is None or row[0] != "held":
            raise ValueError("Synthetic invoice cannot be repeated")
        conn.execute(
            "UPDATE pr31_v3_reservation "
            "SET status='reconciled',actual_cents=45 "
            "WHERE id='synthetic_budget' AND status='held'"
        )
        if fail_stage == "after_budget":
            raise ValueError("Synthetic failure after budget row")
        conn.execute(
            "UPDATE pr31_v3_job SET actual_charge_cents=45 "
            "WHERE id='synthetic_job_a' AND generation_intent_recorded=1"
        )
        if fail_stage == "after_job":
            raise ValueError("Synthetic failure after job row")
        conn.execute(
            "INSERT INTO pr31_v3_budget_event VALUES "
            "('synthetic_reconciled','synthetic_budget','reconciled')"
        )
        if fail_stage == "after_audit":
            raise ValueError("Synthetic failure after audit event")
        conn.commit()
    except BaseException:
        conn.rollback()
        raise


@pytest.mark.parametrize("fail_stage", ["after_budget", "after_job", "after_audit"])
def test_actual_libsql_sdk_local_multitable_rollback(tmp_path, fail_stage):
    path = tmp_path / "sdk-local-no-cloud.sqlite"
    _create_local_sdk_schema(path)
    before = _snapshot(path)
    assert before == (("held", None), ("submission_intent", None), 1)
    conn = _local_conn(path)
    try:
        with pytest.raises(ValueError, match="Synthetic failure"):
            _do_billing(conn, fail_stage=fail_stage)
    finally:
        conn.close()
    assert _snapshot(path) == before
    conn = _local_conn(path)
    try:
        _do_billing(conn)
    finally:
        conn.close()
    assert _snapshot(path) == (
        ("reconciled", 45), ("submission_intent", 45), 2,
    )


def test_actual_sdk_local_commit_and_independent_connection_readback(tmp_path):
    path = tmp_path / "sdk-two-connections.sqlite"
    _create_local_sdk_schema(path)
    first = _local_conn(path)
    try:
        _do_billing(first)
    finally:
        first.close()
    second = _local_conn(path)
    try:
        assert second.execute(
            "SELECT COUNT(*) FROM pr31_v3_budget_event "
            "WHERE action='reconciled'"
        ).fetchone()[0] == 1
        assert second.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []
    finally:
        second.close()
    assert _snapshot(path) == (
        ("reconciled", 45), ("submission_intent", 45), 2,
    )


def test_actual_sdk_local_fk_partial_unique_and_appendonly_triggers(tmp_path):
    path = tmp_path / "sdk-constraints.sqlite"
    _create_local_sdk_schema(path)
    conn = _local_conn(path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        # An orphan event MUST be rejected by FK enforcement, not silently
        # inserted because the SDK's new connection defaults to FK OFF.
        with pytest.raises(Exception):
            conn.execute(
                "INSERT INTO pr31_v3_budget_event VALUES "
                "('orphan-event','does-not-exist','bad')"
            )
        conn.rollback()

        conn.execute(
            "UPDATE pr31_v3_job SET provider_task_id='test-task-01' "
            "WHERE id='synthetic_job_a'"
        )
        conn.execute(
            "INSERT INTO pr31_v3_job VALUES "
            "('synthetic_job_b','fake',NULL,'idempotency-other',"
            "'submission_intent',1,NULL)"
        )
        # Two NULL provider_task_id values are fine; duplicate non-NULL IDs
        # in the same provider must be rejected.
        conn.execute(
            "INSERT INTO pr31_v3_job VALUES "
            "('synthetic_job_c','fake',NULL,'idempotency-third',"
            "'submission_intent',1,NULL)"
        )
        with pytest.raises(Exception):
            conn.execute(
                "UPDATE pr31_v3_job SET provider_task_id='test-task-01' "
                "WHERE id='synthetic_job_b'"
            )
        conn.rollback()

        with pytest.raises(Exception):
            conn.execute(
                "UPDATE pr31_v3_budget_event SET action='tampered'"
            )
        conn.rollback()
        with pytest.raises(Exception):
            conn.execute("DELETE FROM pr31_v3_budget_event")
        conn.rollback()
        assert conn.execute("SELECT COUNT(*) FROM pr31_v3_budget_event").fetchone()[0] == 1
    finally:
        conn.close()


def test_actual_sdk_local_lost_ack_prevents_replay(tmp_path):
    path = tmp_path / "sdk-ack-lost.sqlite"
    _create_local_sdk_schema(path)
    first = _local_conn(path)
    try:
        with pytest.raises(ConnectionError, match="Simulated ACK lost"):
            _do_billing(first)
            # The SDK really committed on disk: only its confirmation was
            # simulated as lost. Never call _do_billing() again here.
            raise ConnectionError("Simulated ACK lost")
    finally:
        first.close()
    assert _snapshot(path) == (
        ("reconciled", 45), ("submission_intent", 45), 2,
    )
    second = _local_conn(path)
    try:
        with pytest.raises(ValueError, match="cannot be repeated"):
            _do_billing(second)
    finally:
        second.close()


def test_sdk_local_version_capabilities_and_no_remote_urls(tmp_path):
    path = tmp_path / "sdk-version-only.sqlite"
    conn = _local_conn(path)
    try:
        # The surface needed by our future candidate is execute, commit,
        # rollback, cursor.fetchone(), and explicit close().
        for method in ("execute", "commit", "rollback", "close"):
            assert callable(getattr(conn, method))
        # Do NOT infer remotely supported DDL/transactions from this.
        row = conn.execute("SELECT 1").fetchone()
        assert row[0] == 1
    finally:
        conn.close()
