"""PR-31b2k: disposable LOCAL multi-table SQL compatibility rehearsal.

This is not a remote libSQL adapter. No remote URL, SDK, secrets, production
SQLite source or paid Worker is accepted. The named SQL subset is a candidate
to verify separately in an isolated libSQL TxLab with NEW write permission.

Tests must prove atomicity of budget row + job row + immutable audit even when
a write or COMMIT acknowledgement fails. No automatic write retries.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


class V3OfflineDenied(ValueError):
    pass


class V3CommitUncertain(V3OfflineDenied):
    """An acknowledgement may be lost AFTER a durable commit; never replay."""


_MARKER = "pr31-v3-synthetic-fixture-only"
_TABLES = (
    "pr31_v3_policy", "pr31_v3_job", "pr31_v3_job_event",
    "pr31_v3_reservation", "pr31_v3_budget_event",
)
SCHEMA_V3 = (
    """CREATE TABLE pr31_v3_policy (
        marker TEXT PRIMARY KEY CHECK(marker='pr31-v3-synthetic-fixture-only'),
        ceiling_cents INTEGER NOT NULL CHECK(ceiling_cents=60)
    )""",
    """CREATE TABLE pr31_v3_job (
        id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        provider_task_id TEXT,
        idempotency_key TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL CHECK(status IN ('submission_intent','submitted')),
        generation_intent_recorded INTEGER NOT NULL CHECK(generation_intent_recorded=1),
        actual_charge_cents INTEGER
    )""",
    """CREATE UNIQUE INDEX pr31_v3_unique_task
        ON pr31_v3_job(provider,provider_task_id)
        WHERE provider_task_id IS NOT NULL""",
    """CREATE TABLE pr31_v3_job_event (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL REFERENCES pr31_v3_job(id),
        action TEXT NOT NULL
    )""",
    """CREATE TABLE pr31_v3_reservation (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL UNIQUE REFERENCES pr31_v3_job(id),
        marker TEXT NOT NULL REFERENCES pr31_v3_policy(marker),
        reserved_cents INTEGER NOT NULL CHECK(reserved_cents=40),
        actual_cents INTEGER,
        status TEXT NOT NULL CHECK(status IN ('held','reconciled'))
    )""",
    """CREATE TABLE pr31_v3_budget_event (
        id TEXT PRIMARY KEY,
        reservation_id TEXT NOT NULL REFERENCES pr31_v3_reservation(id),
        action TEXT NOT NULL
    )""",
    """CREATE TRIGGER pr31_v3_job_event_no_update BEFORE UPDATE
        ON pr31_v3_job_event BEGIN
            SELECT RAISE(ABORT,'append-only');
        END""",
    """CREATE TRIGGER pr31_v3_job_event_no_delete BEFORE DELETE
        ON pr31_v3_job_event BEGIN
            SELECT RAISE(ABORT,'append-only');
        END""",
    """CREATE TRIGGER pr31_v3_budget_event_no_update BEFORE UPDATE
        ON pr31_v3_budget_event BEGIN
            SELECT RAISE(ABORT,'append-only');
        END""",
    """CREATE TRIGGER pr31_v3_budget_event_no_delete BEFORE DELETE
        ON pr31_v3_budget_event BEGIN
            SELECT RAISE(ABORT,'append-only');
        END""",
)


def _safe_file(file: Path) -> Path:
    raw = str(file)
    if "://" in raw or raw == ":memory:":
        raise V3OfflineDenied("Local disposable SQLite fixture only")
    path = Path(file).expanduser().absolute()
    if (
        path.is_symlink() or path.parent.is_symlink()
        or not path.parent.is_dir()
    ):
        raise V3OfflineDenied("Regular existing local fixture directory required")
    return path


def _open(path: Path):
    conn = sqlite3.connect(path, timeout=15, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_v3_fixture(file: Path, *, isolated_test_only: bool = False) -> Path:
    """O_EXCL creation: NEVER open or overwrite an existing SQLite source."""
    if isolated_test_only is not True:
        raise V3OfflineDenied("Explicit offline test gate required")
    path = _safe_file(file)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise V3OfflineDenied("Refusing existing file (possible real ledger)") from exc
    os.close(fd)
    conn = None
    try:
        conn = _open(path)
        for sql in SCHEMA_V3:
            conn.execute(sql)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO pr31_v3_policy VALUES (?,60)", (_MARKER,)
        )
        conn.execute(
            "INSERT INTO pr31_v3_job VALUES "
            "('synthetic_job_a','fake',NULL,'synthetic_unique_key',"
            "'submission_intent',1,NULL)"
        )
        conn.execute(
            "INSERT INTO pr31_v3_job_event VALUES "
            "('synthetic_intent_event','synthetic_job_a','intent')"
        )
        conn.execute(
            "INSERT INTO pr31_v3_reservation VALUES "
            "('synthetic_reservation','synthetic_job_a',?,40,NULL,'held')",
            (_MARKER,),
        )
        conn.execute(
            "INSERT INTO pr31_v3_budget_event VALUES "
            "('synthetic_held_event','synthetic_reservation','held')"
        )
        conn.commit()
        return path
    except BaseException:
        if conn is not None:
            conn.rollback()
            conn.close()
            conn = None
        path.unlink(missing_ok=True)
        raise
    finally:
        if conn is not None:
            conn.close()


def _checked(path: Path, *, isolated_test_only: bool):
    if isolated_test_only is not True:
        raise V3OfflineDenied("Explicit offline test gate required")
    path = _safe_file(path)
    if not path.is_file():
        raise V3OfflineDenied("Existing local fixture required")
    conn = _open(path)
    try:
        row = conn.execute(
            "SELECT marker FROM pr31_v3_policy"
        ).fetchone()
        if row is None or row[0] != _MARKER:
            raise V3OfflineDenied("Not a disposable synthetic v3 fixture")
        return conn
    except Exception:
        conn.close()
        raise V3OfflineDenied("Not a disposable synthetic v3 fixture") from None


def inspect_v3_local(file: Path, *, isolated_test_only: bool = False) -> dict:
    """Read only aggregate/synthetic counters, never original user data."""
    conn = _checked(file, isolated_test_only=isolated_test_only)
    try:
        job = conn.execute(
            "SELECT status,generation_intent_recorded,actual_charge_cents "
            "FROM pr31_v3_job WHERE id='synthetic_job_a'"
        ).fetchone()
        reservation = conn.execute(
            "SELECT status,actual_cents FROM pr31_v3_reservation "
            "WHERE id='synthetic_reservation'"
        ).fetchone()
        counts = (
            conn.execute("SELECT COUNT(*) FROM pr31_v3_job_event").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM pr31_v3_budget_event").fetchone()[0],
        )
        if job is None or reservation is None:
            raise V3OfflineDenied("Synthetic fixture state incomplete")
        return {
            "mode": "isolated_sqlite_v3_offline_only",
            "job_state": job[0],
            "intent_recorded": bool(job[1]),
            "job_charge_cents": job[2],
            "reservation_state": reservation[0],
            "budget_charge_cents": reservation[1],
            "job_audit_events": counts[0],
            "budget_audit_events": counts[1],
            "remote_turso_connection_attempts": 0,
            "remote_schema_verified": False,
            "remote_multitable_transaction_verified": False,
            "real_live_migration_authorized": False,
            "production_backend_switched": False,
            "paid_provider_calls": 0,
        }
    finally:
        conn.close()


def reconcile_v3_local(
    file: Path, *, isolated_test_only: bool = False,
    fail_after: str | None = None,
) -> dict:
    """Atomic, one-shot synthetic billing; deliberate fail points never retry.

    `after_commit_ack` simulates an ambiguous transport result AFTER COMMIT.
    It is not a safe retry point, even though the local fixture can inspect it.
    """
    allowed = (None, "after_budget", "after_job", "after_event", "after_commit_ack")
    if fail_after not in allowed:
        raise V3OfflineDenied("Unsupported injection stage")
    conn = _checked(file, isolated_test_only=isolated_test_only)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT r.status,j.status,j.generation_intent_recorded "
            "FROM pr31_v3_reservation r JOIN pr31_v3_job j ON j.id=r.job_id "
            "WHERE r.id='synthetic_reservation'"
        ).fetchone()
        if row != ("held", "submission_intent", 1):
            raise V3OfflineDenied("Already reconciled or no durable intent")
        conn.execute(
            "UPDATE pr31_v3_reservation SET status='reconciled',actual_cents=45 "
            "WHERE id='synthetic_reservation' AND status='held'"
        )
        if fail_after == "after_budget":
            raise V3OfflineDenied("Injected failure after reservation write")
        conn.execute(
            "UPDATE pr31_v3_job SET actual_charge_cents=45 "
            "WHERE id='synthetic_job_a' AND generation_intent_recorded=1"
        )
        if fail_after == "after_job":
            raise V3OfflineDenied("Injected failure after job write")
        conn.execute(
            "INSERT INTO pr31_v3_budget_event VALUES "
            "('synthetic_reconciled_event','synthetic_reservation','reconciled')"
        )
        if fail_after == "after_event":
            raise V3OfflineDenied("Injected failure after audit write")
        conn.commit()
        if fail_after == "after_commit_ack":
            raise V3CommitUncertain(
                "Simulated lost commit acknowledgement: never retry"
            )
        return inspect_v3_local(file, isolated_test_only=True)
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
