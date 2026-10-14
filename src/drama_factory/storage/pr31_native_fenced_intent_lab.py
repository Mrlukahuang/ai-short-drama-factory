"""PR-31b2o4: atomic local budget hold + generation intent behind an epoch fence.

An experiment on marked disposable native-libSQL SQLite fixtures ONLY.
Do not install this method in a live Worker or interpret its receipt as
permission to call a billable Provider. The local SDK does not establish
Turso remote or multiple-GitHub-Runner transaction semantics.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from drama_factory.db import new_id, timestamp
from drama_factory.jobs import budgets, shots
from drama_factory.storage.pr31_native_fenced_job_lab import (
    LocalClaimToken, NativeFenceLabDenied, _backend, _gate, _gate_event, _time,
)


def fenced_hold_and_record_intent_local(
    backend, token: LocalClaimToken, *, estimated_charge_usd: str,
    now: datetime | None = None,
) -> dict:
    """Commit all 3 budget gates, hold, intent and audits or nothing at all.

    After ANY ambiguous response, this function must not be replayed.
    Even confirmed success cannot authorize an actual paid Provider call:
    there is no provider idempotency or external-side-effect handoff here.
    """
    db = _backend(backend)
    if (
        type(token) is not LocalClaimToken
        or type(token.attempt) is not int or token.attempt < 1
        or type(token.epoch) is not int or token.epoch < 1
        or not isinstance(token.job_id, str) or not token.job_id
        or not isinstance(token.worker_id, str) or not token.worker_id
        or not isinstance(token.lease_expires_at, str) or not token.lease_expires_at
    ):
        raise NativeFenceLabDenied("Valid marked-fixture claim token required")
    point = _time(now)
    instant = point.isoformat()
    day = point.date().isoformat()
    try:
        proposed = budgets._amount(estimated_charge_usd)
    except budgets.BudgetDenied:
        raise NativeFenceLabDenied("Invalid synthetic budget estimate") from None

    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        epoch, state = _gate(conn)
        if state != "running" or epoch != token.epoch:
            raise NativeFenceLabDenied("Writer gate closed or epoch obsolete")

        row = conn.execute(
            """SELECT j.*,p.column_id FROM shot_jobs j
               JOIN projects p ON p.id=j.series_id WHERE j.id=?""",
            (token.job_id,),
        ).fetchone()
        if (
            row is None or row["status"] != "leased"
            or row["generation_intent_recorded"] != 0
            or row["provider_task_id"] is not None
            or row["lease_owner"] != token.worker_id
            or row["attempts"] != token.attempt
            or row["lease_expires_at"] != token.lease_expires_at
            or not row["lease_expires_at"] or row["lease_expires_at"] <= instant
        ):
            raise NativeFenceLabDenied("Stale, expired or already submitted claim")

        # Fail closed if this job has EVER reserved budget, even if an old
        # reservation was later released; no implicit new billable attempt.
        if conn.execute(
            "SELECT id FROM job_budget_reservations WHERE job_id=?",
            (token.job_id,),
        ).fetchone() is not None:
            raise NativeFenceLabDenied("Existing reservation requires manual review")

        try:
            if proposed > budgets._amount(row["max_acknowledged_spend_usd"]):
                raise NativeFenceLabDenied("Estimate exceeds acknowledged maximum")
            scopes = [
                ("column", row["column_id"]),
                ("series", row["series_id"]),
                ("provider", row["provider"]),
            ]
            policies = [budgets._latest(conn, scope, scope_id) for scope, scope_id in scopes]
            active = conn.execute(
                """SELECT reserved_usd,actual_usd,status,column_id,series_id,provider
                   FROM job_budget_reservations WHERE day_utc=?""",
                (day,),
            ).fetchall()
            for (scope, scope_id), policy in zip(scopes, policies):
                matching = [
                    x for x in active
                    if x[{"column": "column_id", "series": "series_id",
                          "provider": "provider"}[scope]] == scope_id
                ]
                held = [x for x in matching if x["status"] == "held"]
                total = sum(
                    (
                        budgets._amount(x["reserved_usd"]) if x["status"] == "held"
                        else budgets._amount(x["actual_usd"], allow_zero=True)
                    )
                    for x in matching if x["status"] in ("held", "reconciled")
                ) if matching else Decimal("0")
                if total + proposed > budgets._amount(policy["daily_limit_usd"]):
                    raise NativeFenceLabDenied("Synthetic daily budget would be exceeded")
                if len(held) >= policy["max_active_jobs"]:
                    raise NativeFenceLabDenied("Synthetic active-job budget cap reached")
        except budgets.BudgetDenied:
            raise NativeFenceLabDenied("Synthetic budget policy denied") from None

        reservation_id = new_id("reserve")
        snapshots = [
            {"scope": s, "scope_id": sid, "policy_id": p["id"],
             "revision": p["revision"]}
            for (s, sid), p in zip(scopes, policies)
        ]
        conn.execute(
            """INSERT INTO job_budget_reservations
               (id,job_id,column_id,series_id,provider,day_utc,reserved_usd,
                status,policy_snapshot_json,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                reservation_id, token.job_id, row["column_id"], row["series_id"],
                row["provider"], day, budgets._usd(proposed), "held",
                budgets.json.dumps(snapshots, sort_keys=True), timestamp(), timestamp(),
            ),
        )
        budgets._event(conn, reservation_id, "held", {
            "reserved_usd": budgets._usd(proposed),
            "day_utc": day, "policies": snapshots,
            "verified_vendor_charge": False, "offline_fence_epoch": epoch,
        })

        # Exact CAS for claim generation, epoch already serialized with the
        # gate in the *same* BEGIN IMMEDIATE transaction. A second call can
        # never transition the same job or silently reserve another amount.
        changed = conn.execute(
            """UPDATE shot_jobs
               SET status='submission_intent',
                   generation_intent_recorded=1,updated_at=?
               WHERE id=? AND status='leased' AND generation_intent_recorded=0
               AND lease_owner=? AND attempts=? AND lease_expires_at=?
               AND lease_expires_at>? AND provider_task_id IS NULL""",
            (
                instant, token.job_id, token.worker_id, token.attempt,
                token.lease_expires_at, instant,
            ),
        )
        if changed.rowcount != 1:
            raise NativeFenceLabDenied("Claim CAS did not match current lease")
        shots._event(conn, token.job_id, "generation_intent_recorded",
                     "leased", "submission_intent", {
            "may_have_been_billed": True,
            "offline_fence_epoch": epoch,
            "offline_claim_attempt": token.attempt,
        })
        _gate_event(conn, "fenced_hold_and_intent", epoch)

        # The commit happens when the context manager exits. The receipt
        # is NEVER an authorization to send a billable external request.
        return {
            "status": "submission_intent",
            "reservation_status": "held",
            "requires_external_provider_reconciliation": True,
            "authorizes_paid_provider_call": False,
            "may_automatically_retry": False,
            "paid_provider_calls": 0,
            "remote_cross_runner_verified": False,
            "live_cutover_permitted": False,
        }
