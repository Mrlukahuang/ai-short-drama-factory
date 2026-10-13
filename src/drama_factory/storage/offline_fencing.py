"""PR-31c2: a LOCAL TEST-ONLY epoch fence for future cross-Worker design.

This intentionally does not touch actual job/approval/budget tables or wire
into FastAPI/Workers. It NEVER connects to libSQL/Turso. Its SQLite database
is a fresh dedicated fixture, not the production ledger. A local SQLite lock
does not protect remote machines or provider requests; this is only a semantic
baseline for a later durable fleet-wide fence implementation.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path

_MARKER = "isolated-pr31c2-local-fixture-only-v1"
_SCHEMA = """
CREATE TABLE offline_fence (
 id INTEGER PRIMARY KEY CHECK(id=1),
 marker TEXT NOT NULL,
 epoch INTEGER NOT NULL CHECK(epoch>=1),
 state TEXT NOT NULL CHECK(state IN ('running','paused'))
);
CREATE TABLE offline_worker_counter (
 id INTEGER PRIMARY KEY CHECK(id=1),
 total INTEGER NOT NULL CHECK(total>=0)
);
CREATE TABLE offline_fence_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 action TEXT NOT NULL,
 epoch INTEGER NOT NULL
);
"""


class OfflineFenceDenied(ValueError):
    pass


def _validate_path(path: Path) -> Path:
    raw = str(path)
    if "://" in raw or raw == ":memory:":
        raise OfflineFenceDenied("Only new local offline fixture files are permitted")
    resolved = Path(path).expanduser().absolute()
    if not resolved.parent.is_dir() or resolved.parent.is_symlink():
        raise OfflineFenceDenied("Existing local fixture directory required")
    if resolved.is_symlink():
        raise OfflineFenceDenied("Symlink fixture path prohibited")
    return resolved


def create_offline_fence(path: Path, *, isolated_test_only: bool = False):
    """Create one NEW local fixture only; refuses all existing DBs."""
    if isolated_test_only is not True:
        raise OfflineFenceDenied("Offline test mode approval required")
    target = _validate_path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise OfflineFenceDenied("Existing file cannot be used as offline fixture") from exc
    os.close(fd)
    try:
        with closing(sqlite3.connect(target)) as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT INTO offline_fence VALUES (1,?,1,'running')", (_MARKER,)
            )
            conn.execute("INSERT INTO offline_worker_counter VALUES (1,0)")
            conn.commit()
        return OfflineFence(target, isolated_test_only=True)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def _event(conn, action: str, epoch: int):
    conn.execute(
        "INSERT INTO offline_fence_events(action,epoch) VALUES (?,?)",
        (action, epoch),
    )


class OfflineFence:
    def __init__(self, path: Path, *, isolated_test_only: bool = False):
        if isolated_test_only is not True:
            raise OfflineFenceDenied("Offline test mode approval required")
        self.path = _validate_path(path)
        if not self.path.is_file():
            raise OfflineFenceDenied("Existing initialized fixture required")
        # Verify marker BEFORE any DDL/DML. An existing real production
        # sqlite3 file without our dedicated marker is always rejected.
        with closing(self._raw()) as conn:
            try:
                row = conn.execute(
                    "SELECT marker FROM offline_fence WHERE id=1"
                ).fetchone()
            except sqlite3.Error as exc:
                raise OfflineFenceDenied("Not an isolated offline fence fixture") from exc
            if row is None or row[0] != _MARKER:
                raise OfflineFenceDenied("Unexpected fence fixture identity")

    def _raw(self):
        # Connect does not initialize schema; only known fixtures are accepted
        # by the constructor before these operations are publicly available.
        return sqlite3.connect(self.path, timeout=15)

    def _transaction(self, method):
        conn = self._raw()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT marker,epoch,state FROM offline_fence WHERE id=1"
            ).fetchone()
            if row is None or row[0] != _MARKER:
                raise OfflineFenceDenied("Offline fixture marker mismatch")
            result = method(conn, int(row[1]), row[2])
            conn.commit()
            return result
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def snapshot(self) -> dict:
        with closing(self._raw()) as conn:
            conn.execute("BEGIN")  # One consistent local read snapshot.
            marker, epoch, state = conn.execute(
                "SELECT marker,epoch,state FROM offline_fence WHERE id=1"
            ).fetchone()
            if marker != _MARKER:
                raise OfflineFenceDenied("Fixture marker mismatch")
            count = conn.execute(
                "SELECT total FROM offline_worker_counter WHERE id=1"
            ).fetchone()[0]
        return {
            "mode": "offline_local_fixture",
            "epoch": epoch,
            "state": state,
            "simulated_worker_writes": count,
            "fleet_writers_fenced": False,
            "production_backend_switched": False,
            "live_cutover_permitted": False,
            "turso_connections": 0,
            "paid_provider_calls": 0,
        }

    def simulate_worker_write(self, acquired_epoch: int) -> int:
        """Atomic local gate-check + FAKE counter mutation. No paid call."""
        if isinstance(acquired_epoch, bool) or not isinstance(acquired_epoch, int):
            raise OfflineFenceDenied("Integer epoch token required")

        def body(conn, epoch, state):
            if state != "running" or epoch != acquired_epoch:
                raise OfflineFenceDenied("Stale epoch or local write gate paused")
            conn.execute(
                "UPDATE offline_worker_counter SET total=total+1 WHERE id=1"
            )
            _event(conn, "fake_write", epoch)
            return conn.execute(
                "SELECT total FROM offline_worker_counter WHERE id=1"
            ).fetchone()[0]
        return self._transaction(body)

    def pause_for_test(self) -> dict:
        """Serializes after committed local writes, never freezes real Workers."""
        def body(conn, epoch, state):
            if state != "running":
                raise OfflineFenceDenied("Already paused")
            next_epoch = epoch + 1
            conn.execute(
                "UPDATE offline_fence SET epoch=?,state='paused' WHERE id=1",
                (next_epoch,),
            )
            _event(conn, "pause", next_epoch)
            return {"epoch": next_epoch, "state": "paused"}
        return self._transaction(body)

    def resume_for_test(self, *, operator_reviewed: bool = False) -> dict:
        if operator_reviewed is not True:
            raise OfflineFenceDenied("Explicit local fake resume review required")

        def body(conn, epoch, state):
            if state != "paused":
                raise OfflineFenceDenied("Fixture is not paused")
            next_epoch = epoch + 1
            conn.execute(
                "UPDATE offline_fence SET epoch=?,state='running' WHERE id=1",
                (next_epoch,),
            )
            _event(conn, "resume", next_epoch)
            return {"epoch": next_epoch, "state": "running"}
        return self._transaction(body)
