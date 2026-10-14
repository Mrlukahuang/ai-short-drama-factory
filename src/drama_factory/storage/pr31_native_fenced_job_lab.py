"""PR-31b2o3: isolated native-libSQL LOCAL claim/epoch/CAS experiment.

This is intentionally NOT wired into the production worker or API. Only
LocalNativeLibsqlLedger, which requires a disposable SQLite test marker, can
enter. A local transaction cannot prove cross-Runner or remote Turso fencing,
and these functions never contact a provider, Drive or cloud database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from drama_factory.jobs import shots
from drama_factory.storage.libsql_sdk_local_ledger import (
    LocalNativeLibsqlLedger, _MARKER_TABLE, _MARKER_VALUE,
)


class NativeFenceLabDenied(ValueError):
    """Do not expose business rows, tokens, file paths, or SQL on denial."""


@dataclass(frozen=True)
class LocalClaimToken:
    """Opaque-to-callers attempt/epoch tuple, for disposable fixtures ONLY."""
    job_id: str
    worker_id: str
    attempt: int
    epoch: int
    lease_expires_at: str


def _backend(value):
    if type(value) is not LocalNativeLibsqlLedger:
        raise NativeFenceLabDenied("Disposable native-SDK fixture required")
    return value


def _time(now: datetime | None) -> datetime:
    point = datetime.now(timezone.utc) if now is None else now
    if not isinstance(point, datetime) or point.tzinfo is None or point.utcoffset() is None:
        raise NativeFenceLabDenied("Timezone-aware UTC clock required")
    return point.astimezone(timezone.utc)


def _fixture(conn):
    row = conn.execute(f"SELECT value FROM {_MARKER_TABLE}").fetchone()
    if row is None or row[0] != _MARKER_VALUE:
        raise NativeFenceLabDenied("Marked disposable fixture required")


def _gate(conn):
    _fixture(conn)
    row = conn.execute(
        "SELECT epoch,state FROM pr31_native_job_fence_gate WHERE id=1"
    ).fetchone()
    if row is None:
        raise NativeFenceLabDenied("Offline lab gate missing")
    return int(row[0]), row[1]


def _gate_event(conn, action: str, epoch: int):
    conn.execute(
        "INSERT INTO pr31_native_job_fence_events(action,epoch) VALUES (?,?)",
        (action, epoch),
    )


def init_local_native_fence_lab(
    backend: LocalNativeLibsqlLedger, *, isolated_test_only: bool = False,
) -> dict:
    """Create schema exclusively in an existing marker-whitelisted local DB.

    Never runs migrations against a real project source; not a public setup
    method for remote use and not an authorization for external requests.
    """
    db = _backend(backend)
    if isolated_test_only is not True:
        raise NativeFenceLabDenied("Explicit offline fixture setup required")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _fixture(conn)
        # Deliberately use individual execute: native libsql executescript()
        # has historically not reliably surfaced all DDL failures.
        conn.execute("""CREATE TABLE IF NOT EXISTS pr31_native_job_fence_gate (
            id INTEGER PRIMARY KEY CHECK(id=1),
            epoch INTEGER NOT NULL CHECK(epoch>=1),
            state TEXT NOT NULL CHECK(state IN ('running','paused'))
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS pr31_native_job_fence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL, epoch INTEGER NOT NULL
        )""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS pr31_native_gate_events_no_update
            BEFORE UPDATE ON pr31_native_job_fence_events
            BEGIN SELECT RAISE(ABORT,'fence events are append-only'); END""")
        conn.execute("""CREATE TRIGGER IF NOT EXISTS pr31_native_gate_events_no_delete
            BEFORE DELETE ON pr31_native_job_fence_events
            BEGIN SELECT RAISE(ABORT,'fence events are append-only'); END""")
        row = conn.execute(
            "SELECT epoch,state FROM pr31_native_job_fence_gate WHERE id=1"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO pr31_native_job_fence_gate(id,epoch,state) "
                "VALUES (1,1,'running')"
            )
        elif row[0] < 1 or row[1] not in ("running", "paused"):
            raise NativeFenceLabDenied("Invalid existing lab gate")
    return {
        "offline_fixture_only": True,
        "remote_runner_fencing_verified": False,
        "production_worker_modified": False,
        "paid_provider_calls": 0,
        "live_cutover_permitted": False,
    }


def fenced_claim_local_job(
    backend: LocalNativeLibsqlLedger, worker_id: str, *,
    production_id: str | None = None,
    lease_seconds: int = 90, now: datetime | None = None,
) -> LocalClaimToken | None:
    """In one local BEGIN IMMEDIATE: gate read, claim, shot+gate audit."""
    if not isinstance(worker_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{2,80}", worker_id):
        raise NativeFenceLabDenied("Invalid offline worker name")
    if type(lease_seconds) is not int or not 10 <= lease_seconds <= 3600:
        raise NativeFenceLabDenied("Invalid local lease duration")
    if production_id is not None and (not isinstance(production_id, str) or not production_id):
        raise NativeFenceLabDenied("Invalid production scope")
    db, point = _backend(backend), _time(now)
    instant = point.isoformat()
    expiry = (point + timedelta(seconds=lease_seconds)).isoformat()
    with db.connection() as conn:
        # A *pre-transaction* native libSQL lock collision can reject one
        # racing worker before any CAS, audit or provider intent exists.
        # Recognize only this exact known SDK busy result at BEGIN. Never
        # retry or suppress a later SQL/COMMIT error: its outcome may be
        # durable but unknown to the caller.
        try:
            conn.execute("BEGIN IMMEDIATE")
        except ValueError as exc:
            if str(exc) == "database is locked":
                raise NativeFenceLabDenied("Offline pretransaction write lock unavailable") from None
            raise
        epoch, state = _gate(conn)
        if state != "running":
            raise NativeFenceLabDenied("Offline writer gate paused")
        sql = "SELECT id,attempts FROM shot_jobs WHERE status='pending' AND attempts<max_attempts"
        params: tuple = ()
        if production_id:
            sql += " AND production_id=?"
            params = (production_id,)
        sql += " ORDER BY created_at,id LIMIT 1"
        job = conn.execute(sql, params).fetchone()
        if job is None:
            return None
        new_attempt = job["attempts"] + 1
        updated = conn.execute(
            """UPDATE shot_jobs SET status='leased', attempts=attempts+1,
               lease_owner=?,lease_expires_at=?,updated_at=?
               WHERE id=? AND status='pending' AND attempts=? AND attempts<max_attempts""",
            (worker_id, expiry, instant, job["id"], job["attempts"]),
        )
        if updated.rowcount != 1:
            raise NativeFenceLabDenied("Local claim lost compare-and-swap")
        shots._event(conn, job["id"], "claimed", "pending", "leased", {
            "worker": worker_id,
            "lease_expires_at": expiry,
            "offline_fence_epoch": epoch,
            "offline_claim_attempt": new_attempt,
        })
        _gate_event(conn, "fenced_claim", epoch)
        return LocalClaimToken(job["id"], worker_id, new_attempt, epoch, expiry)


def fenced_fail_unsubmitted_local_job(
    backend: LocalNativeLibsqlLedger, token: LocalClaimToken, *,
    now: datetime | None = None,
) -> dict:
    """Atomic local CAS + two audits; NEVER affects submitted/paid-intent work."""
    if type(token) is not LocalClaimToken or type(token.attempt) is not int or token.attempt < 1:
        raise NativeFenceLabDenied("Valid local lease token required")
    if type(token.epoch) is not int or token.epoch < 1:
        raise NativeFenceLabDenied("Valid local epoch required")
    if not isinstance(token.job_id, str) or not token.job_id:
        raise NativeFenceLabDenied("Missing local job key")
    if not isinstance(token.worker_id, str) or not token.worker_id:
        raise NativeFenceLabDenied("Missing local worker name")
    db, point = _backend(backend), _time(now)
    instant = point.isoformat()
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        epoch, state = _gate(conn)
        if epoch != token.epoch or state != "running":
            raise NativeFenceLabDenied("Writer epoch invalidated")
        before = conn.execute(
            "SELECT status,generation_intent_recorded FROM shot_jobs WHERE id=?",
            (token.job_id,),
        ).fetchone()
        if before is None or before["status"] != "leased" or before["generation_intent_recorded"]:
            raise NativeFenceLabDenied("Not a safely unsubmitted leased job")
        # The identical worker name is NOT sufficient: compare immutable
        # claim generation plus lease deadline and gate epoch transactionally.
        changed = conn.execute(
            """UPDATE shot_jobs SET status='failed',
               last_error='Offline local test interruption',updated_at=?
               WHERE id=? AND status='leased' AND generation_intent_recorded=0
               AND lease_owner=? AND attempts=? AND lease_expires_at>?
               AND lease_expires_at=?""",
            (instant, token.job_id, token.worker_id, token.attempt,
             instant, token.lease_expires_at),
        )
        if changed.rowcount != 1:
            raise NativeFenceLabDenied("Expired or stale local claim token")
        shots._event(conn, token.job_id, "failed", "leased", "failed", {
            "offline_only": True,
            "generation_intent_recorded": False,
            "offline_fence_epoch": epoch,
            "offline_claim_attempt": token.attempt,
        })
        _gate_event(conn, "fenced_unsubmitted_failure", epoch)
        return {
            "state": "failed",
            "committed_only_after_context_exit": True,
            "paid_provider_calls": 0,
            "remote_cross_runner_verified": False,
        }


def set_local_writer_gate(
    backend: LocalNativeLibsqlLedger, *, pause: bool,
    operator_reviewed: bool = False,
) -> dict:
    """Local test pause/resume bumps epoch within same transaction as audit."""
    if type(pause) is not bool:
        raise NativeFenceLabDenied("Explicit gate operation required")
    if not pause and operator_reviewed is not True:
        raise NativeFenceLabDenied("Operator review required for local resume")
    db = _backend(backend)
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        epoch, state = _gate(conn)
        expected, next_state, action = (
            ("running", "paused", "pause") if pause else ("paused", "running", "resume")
        )
        if state != expected:
            raise NativeFenceLabDenied("Unexpected local writer gate state")
        next_epoch = epoch + 1
        result = conn.execute(
            "UPDATE pr31_native_job_fence_gate SET epoch=?,state=? "
            "WHERE id=1 AND epoch=? AND state=?",
            (next_epoch, next_state, epoch, expected),
        )
        if result.rowcount != 1:
            raise NativeFenceLabDenied("Local writer gate conflict")
        _gate_event(conn, action, next_epoch)
        return {"epoch": next_epoch, "state": next_state, "production_fenced": False}
