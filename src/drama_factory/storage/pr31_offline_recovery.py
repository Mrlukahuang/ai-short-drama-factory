"""PR-31b2o2: redacted, SELECT-only review of a disposable native-SDK ledger.

An existing marked test fixture is mandatory. This never connects to Turso,
constructs a production Database, writes to the ledger, or retries a Provider.
The review receipt is deliberately insufficient to authorize a paid request.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from drama_factory.storage.libsql_sdk_local_ledger import (
    LocalNativeLibsqlLedger, _MARKER_TABLE, _MARKER_VALUE,
)


class OfflineRecoveryDenied(ValueError):
    """Safe failure without exposing SQL, source path or business identifiers."""


def _utc_point(now: datetime | None) -> datetime:
    point = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(point, datetime) or point.tzinfo is None or point.utcoffset() is None:
        raise OfflineRecoveryDenied("Timezone-aware inspection time required")
    return point.astimezone(timezone.utc)


def _costs_match(job_charge, reservation_charge) -> bool:
    if job_charge is None or reservation_charge is None:
        return False
    try:
        left, right = Decimal(str(job_charge)), Decimal(str(reservation_charge))
        return left.is_finite() and right.is_finite() and left >= 0 and left == right
    except (InvalidOperation, TypeError, ValueError):
        return False


def inspect_offline_job_recovery(
    backend: LocalNativeLibsqlLedger, job_id: str, *,
    now: datetime | None = None,
) -> dict:
    """Return decision flags only. No rows, IDs, amounts, tokens or paths.

    No recommendation from this function authorizes a new paid submission.
    READ-ONLY mode is enforced at the SQLite connection, not by convention.
    """
    if type(backend) is not LocalNativeLibsqlLedger:
        raise OfflineRecoveryDenied("Marked native-SDK offline fixture required")
    if not isinstance(job_id, str) or not job_id or len(job_id) > 160:
        raise OfflineRecoveryDenied("Valid test job key required")
    point = _utc_point(now)
    flags: set[str] = {"safe_to_inspect_only", "needs_operator_review"}

    try:
        # Adapter constructor already verified the marker. Revalidate INSIDE
        # the read snapshot in case the backing file changed since construction.
        with closing(sqlite3.connect(backend.path.as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN")
            marker = conn.execute(
                f"SELECT value FROM {_MARKER_TABLE}"
            ).fetchone()
            if marker != (_MARKER_VALUE,):
                raise OfflineRecoveryDenied("Test fixture marker mismatch")
            job = conn.execute(
                """SELECT status,attempts,max_attempts,generation_intent_recorded,
                          provider_task_id,lease_owner,lease_expires_at,
                          actual_vendor_charge_usd
                   FROM shot_jobs WHERE id=?""", (job_id,),
            ).fetchone()
            if job is None:
                flags.add("missing_job")
            else:
                status, attempts, max_attempts, intent, task_id, owner, expiry, charge = job
                reserve = conn.execute(
                    """SELECT status,actual_usd FROM job_budget_reservations
                       WHERE job_id=?""", (job_id,),
                ).fetchone()
                intent_events = conn.execute(
                    """SELECT COUNT(*) FROM shot_job_events
                       WHERE shot_job_id=? AND action='generation_intent_recorded'""",
                    (job_id,),
                ).fetchone()[0]
                charge_events = conn.execute(
                    """SELECT COUNT(*) FROM budget_reservation_events
                       WHERE reservation_id IN (
                         SELECT id FROM job_budget_reservations WHERE job_id=?
                       ) AND action='operator_entered_vendor_charge'""",
                    (job_id,),
                ).fetchone()[0]

                if reserve and reserve[0] == "held":
                    flags.add("held_budget")
                if intent:
                    flags.add("intent_uncertain" if not task_id else "existing_provider_task")
                if task_id and not intent:
                    flags.add("inconsistent_ledger")
                if status in ("submission_intent", "submitted") and not intent:
                    flags.add("inconsistent_ledger")
                if intent and (intent_events != 1 or reserve is None):
                    flags.add("inconsistent_ledger")
                if not intent and intent_events:
                    flags.add("inconsistent_ledger")
                if reserve and reserve[0] == "reconciled":
                    if intent and charge_events == 1 and _costs_match(charge, reserve[1]):
                        flags.add("charge_reconciled")
                    else:
                        flags.add("inconsistent_ledger")
                elif charge is not None or charge_events:
                    flags.add("inconsistent_ledger")
                if status in ("leased", "submission_intent", "submitted"):
                    if not owner or not expiry:
                        flags.add("inconsistent_ledger")
                    else:
                        try:
                            expire_at = datetime.fromisoformat(expiry)
                            if expire_at.tzinfo is None or expire_at.utcoffset() is None:
                                raise ValueError("missing zone")
                            if expire_at.astimezone(timezone.utc) <= point:
                                flags.add("lease_expired")
                        except (ValueError, TypeError, OverflowError):
                            flags.add("inconsistent_ledger")
                if status == "failed":
                    flags.add("failed_job")
                if attempts > max_attempts or attempts < 0:
                    flags.add("inconsistent_ledger")
            conn.rollback()  # End read snapshot; never replay prior transaction.
    except OfflineRecoveryDenied:
        raise
    except (sqlite3.Error, OSError, TypeError, ValueError):
        raise OfflineRecoveryDenied("Offline read-only inspection unavailable") from None

    return {
        "mode": "marked_native_sdk_fixture_select_only",
        "flags": sorted(flags),
        "safe_to_inspect_only": True,
        "needs_operator_review": True,
        "may_resubmit_paid_provider": False,
        "may_release_held_budget": False,
        "readonly_snapshot": True,
        "remote_network_recovery_verified": False,
        "cross_runner_fencing_verified": False,
        "production_backend_switched": False,
        "live_cutover_permitted": False,
        "remote_write_calls": 0,
        "paid_provider_calls": 0,
    }
