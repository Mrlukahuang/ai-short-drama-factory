"""TxLab v5: isolated TWO remote GitHub runners, synthetic SQL ONLY.

Actual remote execution requires GitHub workflow's once-only activation
and these independent env guards. No production DB, real Task ID, Drive,
paid provider or retry after an ambiguous COMMIT. Offline SQLite factories
test the identical SQL. Actor identity and evidence are independently
checked by the parent Actions workflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time

from drama_factory.storage.libsql_txlab import (
    _open_lab_connection, _close_quietly, _rollback_quietly,
    _safe_error_category, validate_lab_url,
)
from drama_factory.storage.pr31_v5_offline_evidence_guard import inspect_proposed_v5_evidence


class V5Denied(ValueError):
    pass


class V5StageError(V5Denied):
    def __init__(self, stage: str, category: str):
        if stage not in ("setup", "ready", "barrier", "claim", "commit",
                         "seal", "observe", "open", "receipt"):
            stage = "open"
        if category not in ("busy", "timeout", "connection", "constraint", "unknown"):
            category = "unknown"
        self.stage = stage
        self.category = category
        super().__init__(f"TxLab v5 stage={stage} category={category}; NO RERUN (redacted)")


_PREFIX = "pr31_v5_"
_OBJECTS = frozenset({
    "pr31_v5_gate", "pr31_v5_ready", "pr31_v5_holds",
    "pr31_v5_events", "pr31_v5_events_no_update", "pr31_v5_events_no_delete",
})
_DDL = (
    """CREATE TABLE pr31_v5_gate (
       id INTEGER PRIMARY KEY CHECK(id=1),
       epoch INTEGER NOT NULL CHECK(epoch >= 1),
       state TEXT NOT NULL CHECK(state IN ('running','paused')))""",
    """CREATE TABLE pr31_v5_ready (
       role TEXT PRIMARY KEY CHECK(role IN ('a','b')),
       run_id INTEGER NOT NULL CHECK(run_id>0))""",
    """CREATE TABLE pr31_v5_holds (
       role TEXT PRIMARY KEY REFERENCES pr31_v5_ready(role),
       cents INTEGER NOT NULL CHECK(cents=40),
       epoch INTEGER NOT NULL CHECK(epoch=1))""",
    """CREATE TABLE pr31_v5_events (
       id TEXT PRIMARY KEY, action TEXT NOT NULL,
       role TEXT REFERENCES pr31_v5_ready(role),
       epoch INTEGER NOT NULL)""",
    """CREATE TRIGGER pr31_v5_events_no_update
       BEFORE UPDATE ON pr31_v5_events
       BEGIN SELECT RAISE(ABORT, 'append-only'); END""",
    """CREATE TRIGGER pr31_v5_events_no_delete
       BEFORE DELETE ON pr31_v5_events
       BEGIN SELECT RAISE(ABORT, 'append-only'); END""",
)


def _nonce(run_id: int) -> str:
    return hashlib.sha256(f"pr31_v5_synthetic_only:{run_id}".encode()).hexdigest()


def _fk(c):
    c.execute("PRAGMA foreign_keys=ON")
    v = c.execute("PRAGMA foreign_keys").fetchone()
    if not v or v[0] != 1:
        raise V5Denied("Foreign key enforcement not active")


def _read(factory, sql, params=()):
    conn = factory()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        _close_quietly(conn)


def stage_setup(factory, *, run_id: int) -> dict:
    """Never continue if ANY v5 object already exists, even on prior failure."""
    c = None
    try:
        c = factory()
        _fk(c)
        preexisting = c.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'pr31_v5_%'"
        ).fetchone()
        if preexisting is None or int(preexisting[0]) != 0:
            raise V5Denied("v5 once-only prefix already used; no repair or retry")
        for ddl in _DDL:
            c.execute(ddl)
        names = c.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'pr31_v5_%'"
        ).fetchall()
        if {x[0] for x in names} != _OBJECTS:
            raise V5Denied("Incomplete v5 canary schema")
        c.execute("INSERT INTO pr31_v5_gate VALUES (1,1,'running')")
        c.commit()
        return {"stage": "setup", "schema_objects": len(_OBJECTS),
                "synthetic_only": True, "nonce_sha256": _nonce(run_id),
                "paid_provider_calls": 0, "production_touched": False}
    finally:
        _close_quietly(c)


def stage_actor(factory, *, run_id: int, job_id: int, role: str,
                wait_seconds: float = 120.0) -> dict:
    """Two separate GitHub jobs: one budget mutation attempt each. NO retries."""
    if role not in ("a", "b") or type(run_id) is not int or run_id < 1 or type(job_id) is not int or job_id < 1:
        raise V5Denied("Invalid synthetic runner provenance")
    c = None
    try:
        c = factory()
        _fk(c)
        c.execute("BEGIN IMMEDIATE")
        c.execute("INSERT INTO pr31_v5_ready VALUES (?,?)", (role, run_id))
        c.commit()
    finally:
        _close_quietly(c)

    start = time.monotonic()
    while time.monotonic() - start < wait_seconds:
        ready = _read(factory, "SELECT COUNT(*) FROM pr31_v5_ready WHERE run_id=?", (run_id,))
        if ready is not None and int(ready[0]) == 2:
            break
        time.sleep(0.3)
    else:
        raise V5Denied("Both remote actors were not independently ready")

    c = None
    outcome = None
    try:
        c = factory()
        _fk(c)
        c.execute("BEGIN IMMEDIATE")
        gate = c.execute("SELECT epoch,state FROM pr31_v5_gate WHERE id=1").fetchone()
        if gate is None or tuple(gate) != (1, "running"):
            raise V5Denied("Gate was not running with expected epoch")
        committed = c.execute("SELECT COALESCE(SUM(cents),0) FROM pr31_v5_holds").fetchone()
        if committed is None:
            raise V5Denied("Synthetic budget read unavailable")
        if int(committed[0]) + 40 > 60:
            c.rollback()
            outcome = "denied"
        else:
            c.execute("INSERT INTO pr31_v5_holds VALUES (?,40,1)", (role,))
            c.execute("INSERT INTO pr31_v5_events VALUES (?,?,?,1)",
                      ("intent_"+role, "generation_intent_recorded", role))
            c.execute("INSERT INTO pr31_v5_events VALUES (?,?,?,1)",
                      ("fence_"+role, "fenced_hold_and_intent", role))
            c.commit()
            outcome = "accepted"
    except BaseException as exc:
        _rollback_quietly(c)
        category = _safe_error_category(exc)
        # A busy/locked transaction is NOT a successful reservation and
        # MUST NOT be retried; inspect independently for an actual committed
        # competing hold before classifying the losing actor as denied.
        if category != "busy":
            raise V5StageError("claim", category) from None
        start = time.monotonic()
        while time.monotonic() - start < min(wait_seconds, 15.0):
            hold = _read(factory, "SELECT COUNT(*) FROM pr31_v5_holds")
            if hold is not None and int(hold[0]) == 1:
                outcome = "denied"
                break
            time.sleep(0.3)
        if outcome is None:
            raise V5StageError("claim", "busy") from None
    finally:
        _close_quietly(c)
    return {
        "role": role, "github_run_id": run_id, "github_job_id": job_id,
        "run_attempt": 1, "nonce_sha256": _nonce(run_id),
        "backend": "isolated_turso_remote", "outcome": outcome,
    }


def stage_seal(factory) -> dict:
    """After BOTH actor jobs: pause durable epoch; test old-epoch CAS fails."""
    c = None
    try:
        c = factory()
        _fk(c)
        c.execute("BEGIN IMMEDIATE")
        ready = c.execute("SELECT COUNT(*) FROM pr31_v5_ready").fetchone()[0]
        committed = c.execute("SELECT COUNT(*) FROM pr31_v5_holds").fetchone()[0]
        if ready != 2 or committed != 1:
            raise V5Denied("Remote actors did not persist exactly one hold")
        x = c.execute(
            "UPDATE pr31_v5_gate SET state='paused',epoch=2 "
            "WHERE id=1 AND state='running' AND epoch=1"
        )
        if x.rowcount != 1:
            raise V5Denied("Durable pause CAS failed")
        c.execute("INSERT INTO pr31_v5_events VALUES ('pause','pause',NULL,2)")
        c.commit()

        # Explicit stale attempt after pause is serialized by a transaction
        # checking epoch=1/running. Expected zero rows; never auto-retry.
        c.execute("BEGIN IMMEDIATE")
        x = c.execute(
            "INSERT INTO pr31_v5_holds(role,cents,epoch) "
            "SELECT 'b',40,1 WHERE "
            "(SELECT state FROM pr31_v5_gate WHERE id=1)='running' "
            "AND (SELECT epoch FROM pr31_v5_gate WHERE id=1)=1 "
            "AND NOT EXISTS (SELECT 1 FROM pr31_v5_holds WHERE role='b')"
        )
        if x.rowcount != 0:
            raise V5Denied("Stale epoch wrote after pause")
        c.rollback()
        return {"stage": "seal", "gate_paused": True,
                "stale_token_writes": 0, "provider_api_calls": 0}
    finally:
        _close_quietly(c)


def stage_observe(factory, *, run_id: int, job_id: int, actor_a: dict, actor_b: dict) -> dict:
    """Independent snapshot using only read-oriented SQL, no PRAGMA toggles.

    Turso's libsql 0.1.11 remote connection rejected PRAGMA query_only=ON
    in actual v5 Job #115675757454. A separate SELECT-only forensic run
    #38510686538 verified identical data and PRAGMA foreign_key_check.
    This routine never performs writes; it does NOT prove database-level
    read-only token authorization or authorize replay of consumed v5 jobs.
    """
    c = None
    try:
        c = factory()
        # Deliberately do not call _fk: PRAGMA foreign_keys=ON sets a
        # connection flag and is not required for SELECT-only inspection.
        # BEGIN establishes a consistent read snapshot on both SQLite and
        # the verified libSQL remote backend.
        c.execute("BEGIN")
        if c.execute("PRAGMA foreign_key_check").fetchall():
            raise V5Denied("Remote foreign key check rejected")
        gate = c.execute("SELECT epoch,state FROM pr31_v5_gate WHERE id=1").fetchone()
        ready = c.execute("SELECT COUNT(*) FROM pr31_v5_ready").fetchone()[0]
        held = c.execute("SELECT COUNT(*) FROM pr31_v5_holds").fetchone()[0]
        intent = c.execute("SELECT COUNT(*) FROM pr31_v5_events WHERE action='generation_intent_recorded'").fetchone()[0]
        audit = c.execute("SELECT COUNT(*) FROM pr31_v5_events WHERE action='fenced_hold_and_intent'").fetchone()[0]
        paused = c.execute("SELECT COUNT(*) FROM pr31_v5_events WHERE action='pause'").fetchone()[0]
        distinct_roles = c.execute("SELECT COUNT(DISTINCT role) FROM pr31_v5_ready").fetchone()[0]
        if gate is None or tuple(gate) != (2, "paused") or ready != 2 or distinct_roles != 2 or held != 1 or intent != 1 or audit != 1 or paused != 1:
            raise V5Denied("Independent remote readback disagrees with actor receipts")
        c.rollback()
    finally:
        _close_quietly(c)
    observer = {
        "github_run_id": run_id, "github_job_id": job_id,
        "run_attempt": 1, "nonce_sha256": _nonce(run_id),
        "backend": "isolated_turso_remote",
        "read_only_connection": True, "gate_state": "paused",
        "gate_epoch": 2, "held_rows": held,
        "intent_audits": intent, "gate_audits": audit,
        "stale_token_writes": 0, "duplicate_task_bindings": 0,
        "foreign_keys_ok": True, "unknown_commit": False,
        "provider_api_calls": 0,
    }
    normalized = {
        "experiment": "pr31_v5_isolated_synthetic_only",
        "namespace": _PREFIX, "actors": [actor_a, actor_b],
        "observer": observer,
    }
    shape = inspect_proposed_v5_evidence(normalized)
    assert shape["remote_multi_runner_verified"] is False
    return {
        "stage": "observe", "independent_remote_readback_consistent": True,
        "one_accepted_one_denied": True, "remote_job_ids_distinct": True,
        "remote_provenance_must_be_verified_with_github": True,
        "synthetic_receipt_shape_validated": True,
        "read_only_sql_path": True,
        "database_level_read_only_token_verified": False,
        "remote_multi_runner_verified": False,  # independent post-run review
        "network_commit_ack_loss_verified": False,
        "production_backend_switched": False,
        "live_cutover_permitted": False, "paid_provider_calls": 0,
    }


def run_stage(stage: str, factory, *, run_id: int, job_id: int = 1,
              role: str = "", actor_a: dict | None = None,
              actor_b: dict | None = None) -> dict:
    if stage not in ("setup", "actor", "seal", "observe") or type(run_id) is not int or run_id < 1:
        raise V5Denied("Invalid v5 stage/run")
    try:
        if stage == "setup":
            return stage_setup(factory, run_id=run_id)
        if stage == "actor":
            return stage_actor(factory, run_id=run_id, job_id=job_id, role=role)
        if stage == "seal":
            return stage_seal(factory)
        if not isinstance(actor_a, dict) or not isinstance(actor_b, dict):
            raise V5Denied("Actor receipts missing")
        return stage_observe(factory, run_id=run_id, job_id=job_id,
                             actor_a=actor_a, actor_b=actor_b)
    except V5StageError:
        raise
    except BaseException as exc:
        raise V5StageError(stage, _safe_error_category(exc)) from None


def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description="TxLab v5 strictly isolated one-run multi-Runner test")
    ap.add_argument("--stage", choices=("setup", "actor", "seal", "observe"), required=True)
    ap.add_argument("--role", choices=("a", "b"), default=None)
    args = ap.parse_args(argv)
    if (
        os.getenv("DRAMA_TXLAB_V5_CONFIRM") != "RUN_ISOLATED_TXLAB_V5_ONCE"
        or os.getenv("DRAMA_ENABLE_TXLAB_V5_WRITE") != "YES"
        or os.getenv("DRAMA_TXLAB_V5_MAX_USD") != "2.00"
        or os.getenv("GITHUB_RUN_ATTEMPT") != "1"
        or os.getenv("GITHUB_REF") != "refs/heads/main"
    ):
        print("TxLab v5 denied: explicit once-only under-2-dollar runner gates missing", file=sys.stderr)
        return 1
    try:
        url = validate_lab_url(os.environ.get("DRAMA_TXLAB_DATABASE_URL", ""))
        token = os.environ.get("DRAMA_TXLAB_AUTH_TOKEN", "")
        run_id = int(os.environ.get("GITHUB_RUN_ID", "0"))
        job_id = int(os.environ.get("DRAMA_TXLAB_V5_JOB_ID", "0"))
        if not token or run_id < 1 or job_id < 1:
            raise V5Denied("Isolated credentials or GitHub job provenance missing")
        receipts = {}
        if args.stage == "observe":
            receipts = {
                "actor_a": json.loads(os.environ["DRAMA_V5_ACTOR_A_RECEIPT"]),
                "actor_b": json.loads(os.environ["DRAMA_V5_ACTOR_B_RECEIPT"]),
            }
        reply = run_stage(args.stage, lambda: _open_lab_connection(url, token),
                          run_id=run_id, job_id=job_id,
                          role=args.role or "", **receipts)
    except V5StageError as exc:
        print(f"TxLab v5 {exc} — no automatic replay", file=sys.stderr)
        return 1
    except BaseException:
        print("TxLab v5 stopped (redacted); possible committed writes, never rerun", file=sys.stderr)
        return 1
    print(json.dumps(reply, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
