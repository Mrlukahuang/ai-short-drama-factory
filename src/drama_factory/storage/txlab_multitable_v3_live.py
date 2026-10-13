"""PR-31b2l1: one-use isolated TxLab v3 multi-table contract candidate.

IMPORTANT: the only workflow invoking this module is permanently DISABLED
until a separate, fresh operator authorization and reviewed enabling PR.
Never use the original short-drama or any other Turso database. Nothing is
imported from user data or the production ledger. No retry/drop/cleanup.

A remotely ambiguous commit or partial DDL is an irreversible STOP requiring
later independent SELECT-only diagnosis before any new write permission.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from drama_factory.storage.libsql_txlab import (
    _close_quietly, _open_lab_connection, _rollback_quietly,
    _safe_error_category, validate_lab_url,
)
from drama_factory.storage.txlab_multitable_v3 import SCHEMA_V3

_CONFIRM = "RUN_ISOLATED_TXLAB_V3_ONCE"
_NAMES = frozenset({
    "pr31_v3_policy", "pr31_v3_job", "pr31_v3_job_event",
    "pr31_v3_reservation", "pr31_v3_budget_event",
    "pr31_v3_unique_task",
    "pr31_v3_job_event_no_update", "pr31_v3_job_event_no_delete",
    "pr31_v3_budget_event_no_update", "pr31_v3_budget_event_no_delete",
})
_STAGES = frozenset({
    "open", "enable_fk", "preflight", "schema", "schema_verify",
    "seed_begin", "seed_insert", "seed_commit",
    "rollback_begin", "rollback_budget", "rollback_job",
    "rollback_audit", "rollback_transaction", "rollback_verify",
    "bill_begin", "bill_budget", "bill_job", "bill_audit", "bill_commit",
    "readback_open", "readback_verify",
    "check_fk", "check_unique", "check_immutable",
})


class V3LabDenied(ValueError):
    pass


class V3LabStageFailure(V3LabDenied):
    """Fixed enums only; do not stringify vendor errors or secret-bearing SQL."""

    def __init__(self, stage: str, category: str):
        self.stage = stage if stage in _STAGES else "preflight"
        self.category = category if category in {
            "busy", "timeout", "connection", "constraint", "unknown"
        } else "unknown"
        super().__init__(f"stage={self.stage} category={self.category} (details redacted)")


def _foreign_keys(conn) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    if row is None or int(row[0]) != 1:
        raise V3LabDenied("Foreign-key checks were not enabled")


def _check_snapshot(conn, *, reconciled: bool) -> None:
    row = conn.execute(
        "SELECT r.status,r.actual_cents,j.status,j.actual_charge_cents,"
        "(SELECT COUNT(*) FROM pr31_v3_budget_event) "
        "FROM pr31_v3_reservation r "
        "JOIN pr31_v3_job j ON j.id=r.job_id "
        "WHERE r.id='synthetic_reservation' AND j.id='synthetic_job_a'"
    ).fetchone()
    expected = (
        ("reconciled", 45, "submission_intent", 45, 2)
        if reconciled else ("held", None, "submission_intent", None, 1)
    )
    if row is None or tuple(row) != expected:
        raise V3LabDenied("Multi-table synthetic state does not match expected commit")


def _require_rejected(conn, sql: str, *, reason: str) -> None:
    """Constraint failure must be REAL; network/timeout is not acceptance."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        try:
            conn.execute(sql)
        except Exception as exc:
            # Never expose exception text; parse solely to establish whether
            # the expected server constraint caused this exact rejection.
            msg = str(exc).lower()
            accepted = {
                "fk": "foreign key constraint failed" in msg,
                "unique": "unique constraint failed" in msg,
                "immutable": "append-only" in msg,
            }[reason]
            if not accepted:
                raise V3LabDenied("Unrelated error cannot prove database constraint") from None
        else:
            raise V3LabDenied("Expected schema constraint was not enforced")
    finally:
        _rollback_quietly(conn)


def run_v3_lab_contract(conn_factory, *, mode: str = "offline_fake") -> dict:
    """Exactly one new v3 fixture, sequential transactions, no concurrency.

    ALL operations are through a caller-provided DB-API-like connection
    factory; offline CI only supplies sqlite3 connections on a temporary file.
    DDL success alone is NOT evidence until catalog is read back. A failed
    partially installed schema is intentionally left for operator inspection.
    """
    if mode not in ("offline_fake", "isolated_live"):
        raise V3LabDenied("Invalid isolated TxLab v3 execution mode")
    stage = "open"
    master = None
    reader = None
    try:
        master = conn_factory()
        stage = "enable_fk"
        _foreign_keys(master)

        # This MUST precede all v3 DDL/DML. Never overwrite a previous failed
        # one-use lab run; no CREATE IF NOT EXISTS or DROP in this candidate.
        stage = "preflight"
        existing = master.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'pr31_v3_%'"
        ).fetchone()
        if existing is None or int(existing[0]) != 0:
            raise V3LabDenied("Existing v3 schema; never reuse or clean up automatically")

        for ddl in SCHEMA_V3:
            stage = "schema"
            master.execute(ddl)  # intentionally NOT executescript
        stage = "schema_verify"
        objects = master.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'pr31_v3_%'"
        ).fetchall()
        if {row[0] for row in objects} != _NAMES or len(objects) != len(_NAMES):
            raise V3LabDenied("Incomplete or incompatible v3 schema objects")
        master.commit()

        stage = "seed_begin"
        master.execute("BEGIN IMMEDIATE")
        stage = "seed_insert"
        master.execute(
            "INSERT INTO pr31_v3_policy VALUES ('pr31-v3-synthetic-fixture-only',60)"
        )
        master.execute(
            "INSERT INTO pr31_v3_job VALUES "
            "('synthetic_job_a','fake',NULL,'v3-unique-synthetic',"
            "'submission_intent',1,NULL)"
        )
        master.execute(
            "INSERT INTO pr31_v3_job_event VALUES "
            "('synthetic_intent_event','synthetic_job_a','intent')"
        )
        master.execute(
            "INSERT INTO pr31_v3_reservation VALUES "
            "('synthetic_reservation','synthetic_job_a',"
            "'pr31-v3-synthetic-fixture-only',40,NULL,'held')"
        )
        master.execute(
            "INSERT INTO pr31_v3_budget_event VALUES "
            "('synthetic_held_event','synthetic_reservation','held')"
        )
        stage = "seed_commit"
        master.commit()

        # Verify an intentionally interrupted multi-table transaction leaves
        # absolutely no second charge or immutable audit event.
        stage = "rollback_begin"
        master.execute("BEGIN IMMEDIATE")
        try:
            stage = "rollback_budget"
            master.execute(
                "UPDATE pr31_v3_reservation SET status='reconciled',actual_cents=45 "
                "WHERE id='synthetic_reservation' AND status='held'"
            )
            stage = "rollback_job"
            master.execute(
                "UPDATE pr31_v3_job SET actual_charge_cents=45 "
                "WHERE id='synthetic_job_a' AND generation_intent_recorded=1"
            )
            stage = "rollback_audit"
            master.execute(
                "INSERT INTO pr31_v3_budget_event VALUES "
                "('synthetic_discarded_audit','synthetic_reservation','cancelled')"
            )
        finally:
            stage = "rollback_transaction"
            master.rollback()
        stage = "rollback_verify"
        _check_snapshot(master, reconciled=False)

        # One real synthetic charge reconciliation. This is NOT a Provider
        # request and is explicitly scoped to the new v3 test tables only.
        stage = "bill_begin"
        master.execute("BEGIN IMMEDIATE")
        stage = "bill_budget"
        master.execute(
            "UPDATE pr31_v3_reservation SET status='reconciled',actual_cents=45 "
            "WHERE id='synthetic_reservation' AND status='held'"
        )
        stage = "bill_job"
        master.execute(
            "UPDATE pr31_v3_job SET actual_charge_cents=45 "
            "WHERE id='synthetic_job_a' AND generation_intent_recorded=1"
        )
        stage = "bill_audit"
        master.execute(
            "INSERT INTO pr31_v3_budget_event VALUES "
            "('synthetic_reconciled_event','synthetic_reservation','reconciled')"
        )
        stage = "bill_commit"
        master.commit()

        # Use a fresh connection, again FK=ON, to prove committed cross-table
        # state rather than relying on a potentially uncommitted session.
        stage = "readback_open"
        reader = conn_factory()
        _foreign_keys(reader)
        stage = "readback_verify"
        _check_snapshot(reader, reconciled=True)
        fk_violations = reader.execute("PRAGMA foreign_key_check").fetchall()
        if fk_violations:
            raise V3LabDenied("Foreign-key data violation detected")

        # Negative tests under explicit rollback. NEVER interpret unrelated
        # SDK/network failure as evidence of a DB constraint.
        stage = "check_fk"
        _require_rejected(
            master,
            "INSERT INTO pr31_v3_budget_event VALUES "
            "('orphan_test_event','not_existing','orphan')",
            reason="fk",
        )
        stage = "check_unique"
        master.execute("BEGIN IMMEDIATE")
        try:
            master.execute(
                "UPDATE pr31_v3_job SET provider_task_id='tasks/v3-synthetic' "
                "WHERE id='synthetic_job_a'"
            )
            master.execute(
                "INSERT INTO pr31_v3_job VALUES "
                "('synthetic_job_b','fake',NULL,'v3-unique-second',"
                "'submission_intent',1,NULL)"
            )
            try:
                master.execute(
                    "UPDATE pr31_v3_job SET provider_task_id='tasks/v3-synthetic' "
                    "WHERE id='synthetic_job_b'"
                )
            except Exception as exc:
                if "unique constraint failed" not in str(exc).lower():
                    raise V3LabDenied("Unrelated error cannot prove unique index") from None
            else:
                raise V3LabDenied("Partial unique provider task index not enforced")
        finally:
            _rollback_quietly(master)
        stage = "check_immutable"
        _require_rejected(
            master,
            "UPDATE pr31_v3_budget_event SET action='tampered' "
            "WHERE id='synthetic_held_event'",
            reason="immutable",
        )
        _require_rejected(
            master,
            "DELETE FROM pr31_v3_job_event "
            "WHERE id='synthetic_intent_event'",
            reason="immutable",
        )
        _check_snapshot(reader, reconciled=True)

        return {
            "mode": mode,
            "schema_object_count": len(_NAMES),
            "fk_enabled_on_both_connections": True,
            "rollback_multitable_verified": True,
            "committed_multitable_readback_verified": True,
            "foreign_key_constraints_verified": True,
            "partial_unique_provider_task_verified": True,
            "append_only_triggers_verified": True,
            "no_auto_retry": True,
            "isolated_v3_lab_verified": mode == "isolated_live",
            "remote_multiworker_concurrency_verified": False,
            "full_production_schema_verified": False,
            "production_database_touched": False,
            "production_backend_switched": False,
            "live_cutover_permitted": False,
            "paid_provider_calls": 0,
        }
    except V3LabStageFailure:
        raise
    except BaseException as exc:
        _rollback_quietly(master)
        raise V3LabStageFailure(stage, _safe_error_category(exc)) from None
    finally:
        _close_quietly(reader)
        _close_quietly(master)


def run_live_v3(
    url: str, token: str, *, operator_approved: bool = False,
    connection_factory=None,
) -> dict:
    """Gated entry for FUTURE authorization only; current workflow is locked."""
    if (
        operator_approved is not True
        or os.environ.get("DRAMA_TXLAB_V3_CONFIRM") != _CONFIRM
        or os.environ.get("DRAMA_ENABLE_TXLAB_V3_WRITE") != "YES"
    ):
        raise V3LabDenied("New one-use v3 operator permission required")
    try:
        validate_lab_url(url)
    except (ValueError, TypeError):
        # Stable v3 denial type, while preserving the strict existing
        # isolated-host validator and never exposing URL/credentials.
        raise V3LabDenied("Only independently scoped TxLab v3 host allowed") from None
    if not token:
        raise V3LabDenied("Dedicated isolated TxLab credentials required")
    factory = connection_factory or (lambda: _open_lab_connection(url, token))
    return run_v3_lab_contract(factory, mode="isolated_live")


def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Future single-use TxLab v3 compatibility canary (LOCKED)"
    )
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        print("TxLab v3 live test is not authorized (details redacted)", file=sys.stderr)
        return 1
    try:
        receipt = run_live_v3(
            os.getenv("DRAMA_TXLAB_DATABASE_URL", ""),
            os.getenv("DRAMA_TXLAB_AUTH_TOKEN", ""),
            operator_approved=True,
        )
    except V3LabStageFailure as exc:
        print(
            f"TxLab v3 stopped stage={exc.stage} category={exc.category}; "
            "write/commit may already have happened; DO NOT retry (redacted)",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print(
            "TxLab v3 denied; DO NOT retry (details redacted)", file=sys.stderr
        )
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
