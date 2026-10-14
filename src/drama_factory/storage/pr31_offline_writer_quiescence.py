"""PR-31c3b: read-only local writer-quiescence review (NOT resume authority).

This inspects ONLY an existing marked native-SDK disposable SQLite test file.
It is a preflight for human review, not a migration, provider, gate mutation,
or permission to resume ANY production Worker. No remote SDK is imported.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

from drama_factory.storage.libsql_sdk_local_ledger import (
    LocalNativeLibsqlLedger, _MARKER_TABLE, _MARKER_VALUE,
)


class LocalQuiescenceDenied(ValueError):
    """Errors are fixed, never SQL, sensitive job details, paths, or tokens."""


def inspect_offline_writer_quiescence(backend: LocalNativeLibsqlLedger) -> dict:
    """SELECT-only snapshot, deliberately insufficient to approve a resume.

    Checking the durable writer gate alone is not enough: old lease holders,
    unknown submission intent, held spend, stale Task IDs, and missing gate
    audit must block any proposed handoff. No returned flag ever grants
    production or remote write permission.
    """
    if type(backend) is not LocalNativeLibsqlLedger:
        raise LocalQuiescenceDenied("Marked offline test ledger required")
    flags: set[str] = {"operator_review_required"}
    try:
        with closing(sqlite3.connect(
            backend.path.as_uri() + "?mode=ro", uri=True, timeout=5,
        )) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            marker = db.execute(
                f"SELECT value FROM {_MARKER_TABLE}"
            ).fetchone()
            if marker != (_MARKER_VALUE,):
                raise LocalQuiescenceDenied("Offline marker mismatch")
            gate = db.execute(
                "SELECT epoch,state FROM pr31_native_job_fence_gate WHERE id=1"
            ).fetchone()
            if (
                gate is None or type(gate[0]) is not int or gate[0] < 1
                or gate[1] not in ("running", "paused")
            ):
                raise LocalQuiescenceDenied("Offline writer gate missing or invalid")
            epoch, state = gate
            flags.add("writer_gate_paused" if state == "paused" else "writer_gate_running")

            edges = db.execute(
                """SELECT action,epoch FROM pr31_native_job_fence_events
                   WHERE action IN ('pause','resume') ORDER BY id"""
            ).fetchall()
            expected_epoch = 1
            expected_state = "running"
            for action, logged_epoch in edges:
                wanted = "pause" if expected_state == "running" else "resume"
                expected_epoch += 1
                expected_state = "paused" if action == "pause" else "running"
                if action != wanted or logged_epoch != expected_epoch:
                    flags.add("gate_audit_inconsistent")
            if epoch != expected_epoch or state != expected_state:
                flags.add("gate_audit_inconsistent")

            jobs = db.execute(
                """SELECT status,generation_intent_recorded,provider_task_id,
                          lease_owner,lease_expires_at,attempts
                   FROM shot_jobs"""
            ).fetchall()
            for status, intent, task, owner, deadline, attempt in jobs:
                if status in ("leased", "submission_intent", "submitted"):
                    flags.add("unsettled_shot")
                if status == "leased":
                    flags.add("active_or_stale_lease")
                if intent:
                    flags.add("historical_paid_intent")
                if task is not None:
                    flags.add("provider_task_needs_independent_review")
                if intent not in (0, 1) or not isinstance(attempt, int) or attempt < 0:
                    flags.add("shot_ledger_inconsistent")
                if (status in ("leased", "submission_intent", "submitted")) and (
                    not owner or not deadline
                ):
                    flags.add("shot_ledger_inconsistent")
                if status == "pending" and (intent or task is not None):
                    flags.add("shot_ledger_inconsistent")
                if task is not None and not intent:
                    flags.add("shot_ledger_inconsistent")

            reserves = db.execute(
                "SELECT status FROM job_budget_reservations"
            ).fetchall()
            if any(row[0] == "held" for row in reserves):
                flags.add("held_budget_needs_reconciliation")
            if any(row[0] not in ("held", "released", "reconciled") for row in reserves):
                flags.add("budget_ledger_inconsistent")

            # These flags mean no evidence exists to clear the remote/vendor
            # side of a commit. A local candidate still requires human review.
            blocked = any(x not in (
                "operator_review_required", "writer_gate_paused",
            ) for x in flags)
            db.rollback()

    except LocalQuiescenceDenied:
        raise
    except (sqlite3.Error, OSError, TypeError, ValueError):
        raise LocalQuiescenceDenied("Offline read-only review unavailable") from None

    candidate = not blocked and "writer_gate_paused" in flags
    return {
        "mode": "marked_native_sdk_fixture_select_only",
        "flags": sorted(flags),
        "offline_quiescence_candidate_for_review": candidate,
        "safe_to_authorize_resume": False,
        "may_resume_remote_writers": False,
        "may_resume_production_writers": False,
        "may_retry_paid_provider": False,
        "may_release_held_budget": False,
        "sqlite_read_only": True,
        "remote_multi_runner_verified": False,
        "remote_turso_read_attempts": 0,
        "remote_write_calls": 0,
        "paid_provider_calls": 0,
        "live_cutover_permitted": False,
    }
