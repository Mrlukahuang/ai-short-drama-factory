"""PR-31b2o5: synthetic-only provider task receipt fencing (LOCAL TEST).

Not a real provider integration, never calls one. Accepts only SYNTHETIC_*
task identifiers in a marker-whitelisted native libSQL temporary SQLite DB.
The experiment does NOT authorize a new billable task, remote migration,
or production Worker use.
"""
from __future__ import annotations

import re
from datetime import datetime

from drama_factory.jobs import shots
from drama_factory.storage.pr31_native_fenced_job_lab import (
    LocalClaimToken, NativeFenceLabDenied, _backend, _gate, _gate_event, _time,
)


_SYNTHETIC_TASK_PATTERN = re.compile(r"SYNTHETIC_[A-Za-z0-9_-]{8,80}\Z")


def fenced_bind_synthetic_provider_task_local(
    backend, token: LocalClaimToken, synthetic_task_id: str, *,
    now: datetime | None = None,
) -> dict:
    """Atomic existing-intent -> synthetic-task binding, no provider request.

    Following an ambiguous COMMIT result, callers MUST reconcile read-only;
    this function intentionally rejects replay even with the same task ID.
    """
    db = _backend(backend)
    if not isinstance(synthetic_task_id, str) or not _SYNTHETIC_TASK_PATTERN.fullmatch(synthetic_task_id):
        raise NativeFenceLabDenied("A synthetic-only task reference is required")
    if (
        type(token) is not LocalClaimToken
        or type(token.attempt) is not int or token.attempt < 1
        or type(token.epoch) is not int or token.epoch < 1
        or not isinstance(token.job_id, str) or not token.job_id
        or not isinstance(token.worker_id, str) or not token.worker_id
        or not isinstance(token.lease_expires_at, str) or not token.lease_expires_at
    ):
        raise NativeFenceLabDenied("Valid local claim tuple required")
    instant = _time(now).isoformat()

    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        epoch, state = _gate(conn)
        if epoch != token.epoch or state != "running":
            raise NativeFenceLabDenied("Writer gate epoch expired or paused")
        row = conn.execute(
            """SELECT status,generation_intent_recorded,provider_task_id,
                      provider,lease_owner,lease_expires_at,attempts
               FROM shot_jobs WHERE id=?""",
            (token.job_id,),
        ).fetchone()
        if (
            row is None or row["status"] != "submission_intent"
            or row["generation_intent_recorded"] != 1
            or row["provider_task_id"] is not None
            or row["lease_owner"] != token.worker_id
            or row["attempts"] != token.attempt
            or row["lease_expires_at"] != token.lease_expires_at
            or row["lease_expires_at"] <= instant
        ):
            raise NativeFenceLabDenied("Synthetic receipt has stale or uncertain claim")

        reservation = conn.execute(
            "SELECT id,status FROM job_budget_reservations WHERE job_id=?",
            (token.job_id,),
        ).fetchone()
        if reservation is None or reservation["status"] != "held":
            raise NativeFenceLabDenied("Synthetic receipt requires held reservation")
        intent_events = conn.execute(
            "SELECT COUNT(*) FROM shot_job_events "
            "WHERE shot_job_id=? AND action='generation_intent_recorded'",
            (token.job_id,),
        ).fetchone()[0]
        hold_events = conn.execute(
            "SELECT COUNT(*) FROM budget_reservation_events "
            "WHERE reservation_id=? AND action='held'",
            (reservation["id"],),
        ).fetchone()[0]
        if intent_events != 1 or hold_events != 1:
            raise NativeFenceLabDenied("Missing durable budget or intent audit")

        if conn.execute(
            """SELECT id FROM shot_jobs
               WHERE provider=? AND provider_task_id=?""",
            (row["provider"], synthetic_task_id),
        ).fetchone() is not None:
            raise NativeFenceLabDenied("Duplicate synthetic provider task reference")

        changed = conn.execute(
            """UPDATE shot_jobs SET status='submitted',provider_task_id=?,updated_at=?
               WHERE id=? AND status='submission_intent'
               AND generation_intent_recorded=1 AND provider_task_id IS NULL
               AND lease_owner=? AND attempts=? AND lease_expires_at=?
               AND lease_expires_at>?""",
            (synthetic_task_id, instant, token.job_id, token.worker_id,
             token.attempt, token.lease_expires_at, instant),
        )
        if changed.rowcount != 1:
            raise NativeFenceLabDenied("Synthetic task binding CAS failed")
        shots._event(
            conn, token.job_id, "provider_task_recorded",
            "submission_intent", "submitted", {
                "provider_task_id": synthetic_task_id, "synthetic_only": True,
                "offline_fence_epoch": epoch, "offline_claim_attempt": token.attempt,
            },
        )
        _gate_event(conn, "fenced_synthetic_task_bound", epoch)
        return {
            "status": "submitted",
            "synthetic_task_bound": True,
            "task_was_generated": False,
            "authorizes_paid_provider_call": False,
            "may_retry_submission": False,
            "remote_provider_queried": False,
            "remote_cross_runner_verified": False,
            "production_backend_switched": False,
            "paid_provider_calls": 0,
            "live_cutover_permitted": False,
        }
