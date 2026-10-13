"""PR-31b2h: offline ONLY, single-statement SQLite write contention fixture.

This is an isolated, disposable test DB and NOT the production job/budget
ledger or a remote Turso adapter. It evaluates how a guarded UPDATE..RETURNING
reduces the SELECT-after-BEGIN roundtrip that failed in TxLab v2.

All actual paid-worker budgeting requires a durable multi-scope reservation,
append-only audit event, idempotency key, lease and provider-intent fencing.
NONE of those properties is implemented by this counter experiment.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


_MARKER = "isolated-pr31b2h-atomic-sqlite-fixture-v1"
_SCHEMA = """
CREATE TABLE offline_atomic_counter (
    id INTEGER PRIMARY KEY CHECK(id=1),
    marker TEXT NOT NULL UNIQUE,
    counter INTEGER NOT NULL CHECK(counter>=0),
    max_counter INTEGER NOT NULL CHECK(max_counter>0)
)
"""


class OfflineAtomicDenied(ValueError):
    pass


def _path(value: Path) -> Path:
    raw = str(value)
    if "://" in raw or raw == ":memory:":
        raise OfflineAtomicDenied("New local SQLite fixture path only")
    path = Path(value).expanduser().absolute()
    if path.is_symlink() or not path.parent.is_dir() or path.parent.is_symlink():
        raise OfflineAtomicDenied("Regular local fixture directory required")
    return path


def create_offline_atomic_fixture(
    file: Path, *, max_count: int, isolated_test_only: bool = False,
) -> Path:
    """Create a NEW, private 0600 SQLite fixture; never open production data."""
    if isolated_test_only is not True:
        raise OfflineAtomicDenied("Explicit offline test authorization required")
    if type(max_count) is not int or not 1 <= max_count <= 100:
        raise OfflineAtomicDenied("Valid bounded synthetic capacity required")
    path = _path(file)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise OfflineAtomicDenied("Refusing existing file or production source") from exc
    os.close(fd)
    conn = None
    try:
        conn = sqlite3.connect(path, timeout=10)
        conn.execute(_SCHEMA)
        conn.execute(
            "INSERT INTO offline_atomic_counter VALUES (1,?,0,?)",
            (_MARKER, max_count),
        )
        conn.commit()
        return path
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        if conn is not None:
            conn.close()


class OfflineAtomicCounter:
    """Open only a specifically tagged local fixture, never a remote URL."""

    def __init__(self, file: Path, *, isolated_test_only: bool = False):
        if isolated_test_only is not True:
            raise OfflineAtomicDenied("Explicit offline test authorization required")
        self.path = _path(file)
        if not self.path.is_file():
            raise OfflineAtomicDenied("Existing fixture required")
        conn = sqlite3.connect(
            self.path.as_uri() + "?mode=ro", uri=True, timeout=10,
        )
        try:
            try:
                record = conn.execute(
                    "SELECT marker FROM offline_atomic_counter WHERE id=1"
                ).fetchone()
            except sqlite3.Error:
                raise OfflineAtomicDenied("Not an isolated fixture") from None
            if record is None or record[0] != _MARKER:
                raise OfflineAtomicDenied("Unexpected fixture identity")
        finally:
            conn.close()

    def claim_once(self) -> int | None:
        """Exactly one conditional UPDATE statement, no prior SELECT or retry.

        UPDATE..RETURNING is one atomic SQL mutation. It may still encounter
        SQLITE_BUSY; those exceptions are intentionally propagated for review,
        NOT silently retried. No SDK/network/model calls are possible here.
        """
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            record = conn.execute(
                "UPDATE offline_atomic_counter SET counter=counter+1 "
                "WHERE id=1 AND marker=? AND counter<max_counter "
                "RETURNING counter",
                (_MARKER,),
            ).fetchone()
            conn.commit()
            return int(record[0]) if record is not None else None
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def status(self) -> dict:
        conn = sqlite3.connect(
            self.path.as_uri() + "?mode=ro", uri=True, timeout=10,
        )
        try:
            row = conn.execute(
                "SELECT counter,max_counter,marker FROM offline_atomic_counter WHERE id=1"
            ).fetchone()
            if row is None or row[2] != _MARKER:
                raise OfflineAtomicDenied("Fixture identity changed")
            return {
                "mode": "offline_local_sqlite_single_statement_candidate",
                "counter": int(row[0]),
                "capacity": int(row[1]),
                "multi_scope_budget_transaction_verified": False,
                "remote_sql_semantics_verified": False,
                "remote_concurrency_verified": False,
                "production_backend_switched": False,
                "live_cutover_permitted": False,
                "turso_connections": 0,
                "paid_provider_calls": 0,
            }
        finally:
            conn.close()
