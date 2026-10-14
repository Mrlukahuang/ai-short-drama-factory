"""TxLab v4: ONE isolated remote canary, modeled on REAL shot/budget schema.

v4 tables have a dedicated pr31_v4_ prefix. Five central business tables
copy their columns and constraints from db.SCHEMA; four synthetic parent
stubs replace private source content. No source data, external API request,
production ledger, or paid Provider is ever read, copied, or modified.

This module only runs from an independently authorized, single-use manual
workflow. Offline unit tests inject local SQLite/native SDK connections.
NO retry of uncertain commits or partial DDL.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from drama_factory.storage.libsql_txlab import (
    _close_quietly, _open_lab_connection, _rollback_quietly,
    _safe_error_category, validate_lab_url,
)

_CONFIRM = "RUN_ISOLATED_TXLAB_V4_ONCE"
_PREFIX = "pr31_v4_"
_TABLES = (
    "columns", "projects", "productions", "episodes", "gate",
    "shot_jobs", "shot_job_events", "budget_policies",
    "job_budget_reservations", "budget_reservation_events", "gate_events",
)
_INDEXES = ("unique_task", "series_status", "job_events", "policy_scope", "budget_daily")
_TRIGGERS = (
    "shot_update_immutable", "shot_delete_immutable",
    "budget_update_immutable", "budget_delete_immutable",
    "gate_update_immutable", "gate_delete_immutable",
)
_NAMES = frozenset(_PREFIX + x for x in _TABLES + _INDEXES + _TRIGGERS)
_STAGES = frozenset((
    "open", "foreign_keys", "preflight", "schema", "schema_readback",
    "seed_begin", "seed_write", "seed_commit", "rollback_begin",
    "rollback_write", "rollback_verify", "atomic_begin", "atomic_write",
    "atomic_commit", "readback_connect", "readback_check",
    "gate_pause_begin", "gate_pause_commit", "gate_check",
    "constraints", "final_readback",
))


class V4CanaryDenied(ValueError):
    pass


class V4StageFailure(V4CanaryDenied):
    """Fixed safe stage/category only: no SDK exception or SQL in CI logs."""

    def __init__(self, stage: str, category: str):
        self.stage = stage if stage in _STAGES else "open"
        self.category = category if category in (
            "busy", "timeout", "connection", "constraint", "unknown"
        ) else "unknown"
        super().__init__(f"stage={self.stage} category={self.category} (redacted)")


def _schema():
    """Dedicated table names; core columns and constraints match db.SCHEMA.

    Parent tables are deliberately synthetic stubs; full source database
    compatibility is NOT claimed. No CREATE IF NOT EXISTS / no DROP.
    """
    return (
        "CREATE TABLE pr31_v4_columns (id TEXT PRIMARY KEY)",
        "CREATE TABLE pr31_v4_projects (id TEXT PRIMARY KEY, column_id TEXT NOT NULL REFERENCES pr31_v4_columns(id))",
        "CREATE TABLE pr31_v4_productions (id TEXT PRIMARY KEY)",
        "CREATE TABLE pr31_v4_episodes (id TEXT PRIMARY KEY)",
        """CREATE TABLE pr31_v4_gate (
            id INTEGER PRIMARY KEY CHECK(id=1),
            epoch INTEGER NOT NULL CHECK(epoch>=1),
            state TEXT NOT NULL CHECK(state IN ('running','paused')))""",
        """CREATE TABLE pr31_v4_shot_jobs (
            id TEXT PRIMARY KEY,
            production_id TEXT NOT NULL REFERENCES pr31_v4_productions(id),
            episode_id TEXT NOT NULL REFERENCES pr31_v4_episodes(id),
            series_id TEXT NOT NULL REFERENCES pr31_v4_projects(id),
            shot_id TEXT NOT NULL,
            provider TEXT NOT NULL,model_id TEXT NOT NULL,
            input_sha256 TEXT NOT NULL,idempotency_key TEXT NOT NULL UNIQUE,
            max_acknowledged_spend_usd TEXT NOT NULL,
            actual_vendor_charge_usd TEXT DEFAULT NULL,
            status TEXT NOT NULL CHECK(status IN
                ('pending','leased','submission_intent','submitted','succeeded','failed','cancelled')),
            generation_intent_recorded INTEGER NOT NULL DEFAULT 0
                CHECK(generation_intent_recorded IN (0,1)),
            attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0),
            max_attempts INTEGER NOT NULL DEFAULT 2 CHECK(max_attempts BETWEEN 1 AND 5),
            provider_task_id TEXT,
            lease_owner TEXT,lease_expires_at TEXT,
            result_sha256 TEXT,result_path TEXT,
            last_error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
            UNIQUE(production_id,shot_id))""",
        """CREATE TABLE pr31_v4_shot_job_events (
            id TEXT PRIMARY KEY,
            shot_job_id TEXT NOT NULL REFERENCES pr31_v4_shot_jobs(id),
            action TEXT NOT NULL,
            previous_state TEXT,next_state TEXT NOT NULL,
            details_json TEXT NOT NULL,created_at TEXT NOT NULL)""",
        """CREATE TABLE pr31_v4_budget_policies (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL CHECK(scope IN ('column','series','provider')),
            scope_id TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),
            daily_limit_usd TEXT NOT NULL,
            max_active_jobs INTEGER NOT NULL CHECK(max_active_jobs BETWEEN 1 AND 100),
            enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
            created_at TEXT NOT NULL,UNIQUE(scope,scope_id,revision))""",
        """CREATE TABLE pr31_v4_job_budget_reservations (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL UNIQUE REFERENCES pr31_v4_shot_jobs(id),
            column_id TEXT NOT NULL REFERENCES pr31_v4_columns(id),
            series_id TEXT NOT NULL REFERENCES pr31_v4_projects(id),
            provider TEXT NOT NULL,day_utc TEXT NOT NULL,
            reserved_usd TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('held','released','reconciled')),
            actual_usd TEXT,evidence_reference TEXT,reviewed_by TEXT,
            policy_snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""",
        """CREATE TABLE pr31_v4_budget_reservation_events (
            id TEXT PRIMARY KEY,
            reservation_id TEXT NOT NULL REFERENCES pr31_v4_job_budget_reservations(id),
            action TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL)""",
        """CREATE TABLE pr31_v4_gate_events (
            id TEXT PRIMARY KEY,epoch INTEGER NOT NULL,
            action TEXT NOT NULL)""",
        """CREATE UNIQUE INDEX pr31_v4_unique_task
            ON pr31_v4_shot_jobs(provider,provider_task_id)
            WHERE provider_task_id IS NOT NULL""",
        """CREATE INDEX pr31_v4_series_status
            ON pr31_v4_shot_jobs(series_id,status,created_at)""",
        """CREATE INDEX pr31_v4_job_events
            ON pr31_v4_shot_job_events(shot_job_id,created_at)""",
        """CREATE INDEX pr31_v4_policy_scope
            ON pr31_v4_budget_policies(scope,scope_id,revision)""",
        """CREATE INDEX pr31_v4_budget_daily
            ON pr31_v4_job_budget_reservations(day_utc,column_id,series_id,provider,status)""",
        """CREATE TRIGGER pr31_v4_shot_update_immutable
            BEFORE UPDATE ON pr31_v4_shot_job_events
            BEGIN SELECT RAISE(ABORT,'append-only'); END""",
        """CREATE TRIGGER pr31_v4_shot_delete_immutable
            BEFORE DELETE ON pr31_v4_shot_job_events
            BEGIN SELECT RAISE(ABORT,'append-only'); END""",
        """CREATE TRIGGER pr31_v4_budget_update_immutable
            BEFORE UPDATE ON pr31_v4_budget_reservation_events
            BEGIN SELECT RAISE(ABORT,'append-only'); END""",
        """CREATE TRIGGER pr31_v4_budget_delete_immutable
            BEFORE DELETE ON pr31_v4_budget_reservation_events
            BEGIN SELECT RAISE(ABORT,'append-only'); END""",
        """CREATE TRIGGER pr31_v4_gate_update_immutable
            BEFORE UPDATE ON pr31_v4_gate_events
            BEGIN SELECT RAISE(ABORT,'append-only'); END""",
        """CREATE TRIGGER pr31_v4_gate_delete_immutable
            BEFORE DELETE ON pr31_v4_gate_events
            BEGIN SELECT RAISE(ABORT,'append-only'); END""",
    )


def _fk(conn):
    conn.execute("PRAGMA foreign_keys=ON")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    if row is None or int(row[0]) != 1:
        raise V4CanaryDenied("Foreign-key check unavailable")


def _snapshot(conn, *, final: bool):
    job = conn.execute(
        "SELECT status,attempts,lease_owner,generation_intent_recorded,"
        "provider_task_id FROM pr31_v4_shot_jobs WHERE id='synthetic_v4_job_a'"
    ).fetchone()
    hold = conn.execute(
        "SELECT status,reserved_usd FROM pr31_v4_job_budget_reservations "
        "WHERE id='synthetic_v4_reservation'"
    ).fetchone()
    gate = conn.execute("SELECT epoch,state FROM pr31_v4_gate WHERE id=1").fetchone()
    counts = (
        conn.execute("SELECT COUNT(*) FROM pr31_v4_shot_job_events").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM pr31_v4_budget_reservation_events").fetchone()[0],
        conn.execute("SELECT COUNT(*) FROM pr31_v4_gate_events").fetchone()[0],
    )
    if final:
        expected_job = ("submitted", 1, "synthetic_v4_worker", 1, "SYNTHETIC_V4_TASK_001")
        expected_hold = ("held", "0.40")
        expected_gate = (2, "paused")
        expected_counts = (3, 1, 2)
    else:
        expected_job = ("pending", 0, None, 0, None)
        expected_hold = None
        expected_gate = (1, "running")
        expected_counts = (0, 0, 0)
    if (
        job is None or tuple(job) != expected_job
        or (tuple(hold) if hold else None) != expected_hold
        or gate is None or tuple(gate) != expected_gate
        or counts != expected_counts
    ):
        raise V4CanaryDenied("Isolated test ledger readback inconsistent")
    if conn.execute("PRAGMA foreign_key_check").fetchall():
        raise V4CanaryDenied("Synthetic foreign key integrity failed")


def _execute_atomic_lab_step(conn, point: str, expiry: str, day: str):
    """One transaction: conditional claim, hold, intent, synthetic task, audits."""
    gate = conn.execute("SELECT epoch,state FROM pr31_v4_gate WHERE id=1").fetchone()
    if gate is None or tuple(gate) != (1, "running"):
        raise V4CanaryDenied("Epoch precondition failed")
    changed = conn.execute(
        """UPDATE pr31_v4_shot_jobs SET status='leased',attempts=attempts+1,
           lease_owner='synthetic_v4_worker',lease_expires_at=?,updated_at=?
           WHERE id='synthetic_v4_job_a' AND status='pending' AND attempts=0""",
        (expiry, point),
    )
    if changed.rowcount != 1:
        raise V4CanaryDenied("Atomic claim failed")
    conn.execute(
        """INSERT INTO pr31_v4_shot_job_events VALUES
           ('synthetic_v4_claim_event','synthetic_v4_job_a','claimed',
            'pending','leased','{}',?)""", (point,),
    )
    policies = conn.execute(
        "SELECT scope,daily_limit_usd,max_active_jobs FROM pr31_v4_budget_policies "
        "WHERE enabled=1"
    ).fetchall()
    if (
        len(policies) != 3
        or {p[0] for p in policies} != {"column","series","provider"}
        or any(p[1] != "0.60" or int(p[2]) < 1 for p in policies)
    ):
        raise V4CanaryDenied("Three-scope synthetic budget gate failed")
    if conn.execute(
        "SELECT COUNT(*) FROM pr31_v4_job_budget_reservations "
        "WHERE status='held'"
    ).fetchone()[0] != 0:
        raise V4CanaryDenied("Existing synthetic hold blocked")
    conn.execute(
        """INSERT INTO pr31_v4_job_budget_reservations VALUES
           ('synthetic_v4_reservation','synthetic_v4_job_a',
            'synthetic_v4_column','synthetic_v4_series','fake',?,
            '0.40','held',NULL,NULL,NULL,'[]',?,?)""", (day,point,point),
    )
    conn.execute(
        """INSERT INTO pr31_v4_budget_reservation_events VALUES
           ('synthetic_v4_held_event','synthetic_v4_reservation','held','{}',?)""",
        (point,),
    )
    changed = conn.execute(
        """UPDATE pr31_v4_shot_jobs SET status='submission_intent',
           generation_intent_recorded=1,updated_at=?
           WHERE id='synthetic_v4_job_a' AND status='leased'
           AND attempts=1 AND lease_owner='synthetic_v4_worker'
           AND lease_expires_at=? AND lease_expires_at>?""",
        (point,expiry,point),
    )
    if changed.rowcount != 1:
        raise V4CanaryDenied("Budget/intent CAS failed")
    conn.execute(
        """INSERT INTO pr31_v4_shot_job_events VALUES
           ('synthetic_v4_intent_event','synthetic_v4_job_a',
            'generation_intent_recorded','leased','submission_intent','{}',?)""",
        (point,),
    )
    changed = conn.execute(
        """UPDATE pr31_v4_shot_jobs SET status='submitted',
           provider_task_id='SYNTHETIC_V4_TASK_001',updated_at=?
           WHERE id='synthetic_v4_job_a' AND status='submission_intent'
           AND generation_intent_recorded=1 AND attempts=1
           AND lease_owner='synthetic_v4_worker' AND lease_expires_at=?""",
        (point,expiry),
    )
    if changed.rowcount != 1:
        raise V4CanaryDenied("Synthetic receipt CAS failed")
    conn.execute(
        """INSERT INTO pr31_v4_shot_job_events VALUES
           ('synthetic_v4_task_event','synthetic_v4_job_a','provider_task_recorded',
            'submission_intent','submitted','{}',?)""", (point,),
    )
    conn.execute(
        """INSERT INTO pr31_v4_gate_events VALUES
           ('synthetic_v4_step_event',1,'fenced_synthetic_transaction')""",
    )


def run_v4_contract(conn_factory, *, mode: str = "offline_fake") -> dict:
    """Single serial fixture with independently reopened readback; no retries."""
    if mode not in ("offline_fake", "isolated_live"):
        raise V4CanaryDenied("Invalid lab contract mode")
    stage = "open"
    master = reader = None
    try:
        master = conn_factory()
        stage = "foreign_keys"
        _fk(master)
        stage = "preflight"
        present = master.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'pr31_v4_%'"
        ).fetchone()
        if present is None or int(present[0]) != 0:
            raise V4CanaryDenied("Existing v4 schema: one-use lab not empty")
        stage = "schema"
        for ddl in _schema():
            master.execute(ddl)  # Never executescript; verify each DDL.
        stage = "schema_readback"
        actual = master.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'pr31_v4_%'"
        ).fetchall()
        if len(actual) != len(_NAMES) or {x[0] for x in actual} != _NAMES:
            raise V4CanaryDenied("Incomplete or mismatched v4 test schema")
        master.commit()
        point = datetime.now(timezone.utc)
        now, expiry = point.isoformat(), (point + timedelta(minutes=3)).isoformat()
        day = point.date().isoformat()
        stage = "seed_begin"
        master.execute("BEGIN IMMEDIATE")
        stage = "seed_write"
        for sql in (
            "INSERT INTO pr31_v4_columns VALUES ('synthetic_v4_column')",
            "INSERT INTO pr31_v4_projects VALUES ('synthetic_v4_series','synthetic_v4_column')",
            "INSERT INTO pr31_v4_productions VALUES ('synthetic_v4_production')",
            "INSERT INTO pr31_v4_episodes VALUES ('synthetic_v4_episode')",
            "INSERT INTO pr31_v4_gate VALUES (1,1,'running')",
        ):
            master.execute(sql)
        master.execute(
            """INSERT INTO pr31_v4_shot_jobs
               (id,production_id,episode_id,series_id,shot_id,provider,
                model_id,input_sha256,idempotency_key,max_acknowledged_spend_usd,
                status,created_at,updated_at)
               VALUES ('synthetic_v4_job_a','synthetic_v4_production',
                'synthetic_v4_episode','synthetic_v4_series',
                'synthetic_v4_shot','fake','synthetic',
                'synthetic_sha256','synthetic_v4_unique_key','0.60','pending',?,?)""",
            (now, now),
        )
        for scope,scope_id in (
            ("column","synthetic_v4_column"),
            ("series","synthetic_v4_series"),
            ("provider","fake"),
        ):
            master.execute(
                """INSERT INTO pr31_v4_budget_policies VALUES
                   (?,?,?,1,'0.60',1,1,?)""",
                ("synthetic_v4_policy_"+scope, scope, scope_id, now),
            )
        stage = "seed_commit"
        master.commit()
        _snapshot(master, final=False)

        # Deliberately update several tables and then ROLLBACK to verify
        # no orphan reservation, intent or append-only audit survives.
        stage = "rollback_begin"
        master.execute("BEGIN IMMEDIATE")
        try:
            stage = "rollback_write"
            _execute_atomic_lab_step(master, now, expiry, day)
        finally:
            _rollback_quietly(master)
        stage = "rollback_verify"
        _snapshot(master, final=False)

        stage = "atomic_begin"
        master.execute("BEGIN IMMEDIATE")
        stage = "atomic_write"
        _execute_atomic_lab_step(master, now, expiry, day)
        stage = "atomic_commit"
        master.commit()

        stage = "readback_connect"
        reader = conn_factory()
        _fk(reader)
        # At this point gate still running, inspect the three business tables
        # and all event counts before exercising a pause.
        status = reader.execute(
            "SELECT status FROM pr31_v4_shot_jobs WHERE id='synthetic_v4_job_a'"
        ).fetchone()
        hold = reader.execute(
            "SELECT status FROM pr31_v4_job_budget_reservations "
            "WHERE id='synthetic_v4_reservation'"
        ).fetchone()
        if status is None or status[0] != "submitted" or hold is None or hold[0] != "held":
            raise V4CanaryDenied("New connection cannot see committed state")

        stage = "gate_pause_begin"
        master.execute("BEGIN IMMEDIATE")
        gate_update = master.execute(
            "UPDATE pr31_v4_gate SET epoch=2,state='paused' "
            "WHERE id=1 AND epoch=1 AND state='running'"
        )
        if gate_update.rowcount != 1:
            raise V4CanaryDenied("Gate pause epoch update failed")
        master.execute(
            """INSERT INTO pr31_v4_gate_events VALUES
               ('synthetic_v4_pause_event',2,'pause')"""
        )
        stage = "gate_pause_commit"
        master.commit()
        stage = "gate_check"
        stale = master.execute(
            "UPDATE pr31_v4_shot_jobs SET last_error='should_not_write' "
            "WHERE id='synthetic_v4_job_a' AND attempts=1 "
            "AND (SELECT state FROM pr31_v4_gate WHERE id=1)='running' "
            "AND (SELECT epoch FROM pr31_v4_gate WHERE id=1)=1"
        )
        if stale.rowcount != 0:
            raise V4CanaryDenied("Old epoch wrote after pause")
        master.rollback()
        stage = "constraints"
        # Do not alter the committed task; constraint probes always rollback.
        master.execute("BEGIN IMMEDIATE")
        try:
            master.execute(
                """INSERT INTO pr31_v4_shot_jobs
                   (id,production_id,episode_id,series_id,shot_id,provider,
                    model_id,input_sha256,idempotency_key,max_acknowledged_spend_usd,
                    status,provider_task_id,created_at,updated_at)
                   VALUES ('synthetic_v4_job_b','synthetic_v4_production',
                    'synthetic_v4_episode','synthetic_v4_series',
                    'synthetic_v4_shot_b','fake','synthetic','fake',
                    'synthetic_v4_unique_key_b','0.60','submitted',
                    'SYNTHETIC_V4_TASK_001',?,?)""", (now, now),
            )
        except Exception as exc:
            if "unique constraint failed" not in str(exc).lower():
                raise V4CanaryDenied("Unexpected unique-index test error") from None
        else:
            raise V4CanaryDenied("Duplicate provider Task ID accepted")
        finally:
            _rollback_quietly(master)
        # Extra constraint checks are side-effect-free if rejected, rollback.
        for sql, fragment in (
            ("UPDATE pr31_v4_shot_job_events SET action='tampered' "
             "WHERE id='synthetic_v4_claim_event'", "append-only"),
            ("DELETE FROM pr31_v4_budget_reservation_events "
             "WHERE id='synthetic_v4_held_event'", "append-only"),
            ("INSERT INTO pr31_v4_shot_job_events VALUES "
             "('orphan_v4','not_a_job','fake',NULL,'failed','{}',?)", "foreign key constraint failed"),
        ):
            master.execute("BEGIN IMMEDIATE")
            try:
                if "?" in sql:
                    master.execute(sql, (now,))
                else:
                    master.execute(sql)
            except Exception as exc:
                if fragment not in str(exc).lower():
                    raise V4CanaryDenied("Unrelated constraint test failure") from None
            else:
                raise V4CanaryDenied("Expected constraint not enforced")
            finally:
                _rollback_quietly(master)

        stage = "final_readback"
        # Close and reopen to avoid assuming driver refresh or stale read.
        _close_quietly(reader)
        reader = conn_factory()
        _fk(reader)
        _snapshot(reader, final=True)
        return {
            "mode": mode,
            "isolated_v4_lab_verified": mode == "isolated_live",
            "exact_core_business_table_columns_rehearsed": True,
            "full_production_schema_verified": False,
            "schema_objects_verified": len(_NAMES),
            "synthetic_three_scope_budget_held": True,
            "synthetic_claim_intent_task_atomic": True,
            "rollback_and_independent_readback_verified": True,
            "local_or_serial_epoch_pause_verified": True,
            "remote_multiworker_concurrency_verified": False,
            "server_clock_lease_verified": False,
            "network_commit_ack_loss_verified": False,
            "vendor_billing_verified": False,
            "production_database_touched": False,
            "production_backend_switched": False,
            "live_cutover_permitted": False,
            "paid_provider_calls": 0,
            "no_automatic_retry": True,
        }
    except V4StageFailure:
        raise
    except BaseException as exc:
        _rollback_quietly(master)
        raise V4StageFailure(stage, _safe_error_category(exc)) from None
    finally:
        _close_quietly(reader)
        _close_quietly(master)


def run_live_v4(url: str, token: str, *, operator_approved: bool = False,
                connection_factory=None) -> dict:
    if (
        operator_approved is not True
        or os.getenv("DRAMA_TXLAB_V4_CONFIRM") != _CONFIRM
        or os.getenv("DRAMA_ENABLE_TXLAB_V4_WRITE") != "YES"
    ):
        raise V4CanaryDenied("New one-time TxLab v4 approval gate required")
    try:
        validate_lab_url(url)
    except (ValueError, TypeError):
        raise V4CanaryDenied("Only separately named isolated TxLab host permitted") from None
    if not token:
        raise V4CanaryDenied("Dedicated isolated TxLab credentials required")
    return run_v4_contract(
        connection_factory or (lambda: _open_lab_connection(url, token)),
        mode="isolated_live",
    )


def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Single-use TxLab v4 isolated canary")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        print("TxLab v4 requires separately gated manual dispatch (redacted)", file=sys.stderr)
        return 1
    try:
        receipt = run_live_v4(
            os.getenv("DRAMA_TXLAB_DATABASE_URL", ""),
            os.getenv("DRAMA_TXLAB_AUTH_TOKEN", ""),
            operator_approved=True,
        )
    except V4StageFailure as exc:
        print(
            f"TxLab v4 stopped stage={exc.stage} category={exc.category}; "
            "commit/DDL may have happened, DO NOT RERUN (redacted)",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print("TxLab v4 denied: do not retry (details redacted)", file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
