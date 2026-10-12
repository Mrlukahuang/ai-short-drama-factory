"""Internal-only budget policies and SQLite-atomic shot reservations.

Limits cap locally authorized requests, NOT actual vendor billing. An unverified
outbound request holds its reserve until operator reconciliation, so failures
cannot silently free a possibly-charged budget or trigger more generation.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from drama_factory.db import Database, new_id, timestamp


class BudgetDenied(ValueError):
    pass


def _amount(value, *, allow_zero: bool = False) -> Decimal:
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n > Decimal("1000000") or n < 0:
            raise BudgetDenied("Invalid monetary amount")
        if n == 0 and not allow_zero:
            raise BudgetDenied("Amount must be positive")
        if n != n.quantize(Decimal("0.01")):
            raise BudgetDenied("Amounts must have at most two decimal places")
        return n
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BudgetDenied("Invalid money amount") from exc


def _usd(n: Decimal) -> str:
    return f"{n:.2f}"


def _event(conn, reservation_id, action: str, data: dict):
    conn.execute(
        """INSERT INTO budget_reservation_events
        (id,reservation_id,action,details_json,created_at)
        VALUES (?,?,?,?,?)""",
        (new_id("bud_evt"), reservation_id, action,
         json.dumps(data, sort_keys=True, ensure_ascii=False), timestamp()),
    )


def configure_policy(
    db: Database, scope: str, scope_id: str, *,
    daily_limit_usd: str, max_active_jobs: int, enabled: bool = True,
) -> dict:
    """Create an append-only policy revision, never retroactively widen old holds."""
    if scope not in ("column", "series", "provider"):
        raise BudgetDenied("Budget scope must be column, series or provider")
    if not 1 <= max_active_jobs <= 100:
        raise BudgetDenied("Active-job limit must be 1..100")
    if not re.fullmatch(r"[A-Za-z0-9_:-]{2,160}", scope_id):
        raise BudgetDenied("Invalid scope ID")
    limit = _usd(_amount(daily_limit_usd))
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if scope in ("column", "series"):
            table = "columns" if scope == "column" else "projects"
            if conn.execute(f"SELECT id FROM {table} WHERE id=?", (scope_id,)).fetchone() is None:
                raise BudgetDenied("Budget scope does not exist")
        version = conn.execute(
            """SELECT COALESCE(MAX(revision),0)+1 FROM budget_policies
            WHERE scope=? AND scope_id=?""", (scope, scope_id),
        ).fetchone()[0]
        policy_id = new_id("budget")
        conn.execute(
            """INSERT INTO budget_policies
            (id,scope,scope_id,revision,daily_limit_usd,max_active_jobs,enabled,created_at)
            VALUES (?,?,?,?,?,?,?,?)""",
            (policy_id, scope, scope_id, version, limit,
             max_active_jobs, 1 if enabled else 0, timestamp()),
        )
        return dict(conn.execute(
            "SELECT * FROM budget_policies WHERE id=?", (policy_id,),
        ).fetchone())


def _latest(conn, scope: str, scope_id: str):
    policy = conn.execute(
        """SELECT * FROM budget_policies WHERE scope=? AND scope_id=?
        ORDER BY revision DESC LIMIT 1""", (scope, scope_id),
    ).fetchone()
    if policy is None or not policy["enabled"]:
        raise BudgetDenied(f"No active budget policy for {scope}")
    return policy


def reserve_job_budget(
    db: Database, job_id: str, *, estimated_charge_usd: str,
    now: datetime | None = None,
) -> dict:
    """Atomically hold spend across Column + Series + Provider before paid intent."""
    point = now or datetime.now(timezone.utc)
    if point.tzinfo is None:
        raise BudgetDenied("Timestamp must include timezone")
    day = point.astimezone(timezone.utc).date().isoformat()
    proposed = _amount(estimated_charge_usd)
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT j.*,p.column_id FROM shot_jobs j
            JOIN projects p ON p.id=j.series_id WHERE j.id=?""", (job_id,),
        ).fetchone()
        if row is None or row["status"] != "leased" or row["generation_intent_recorded"]:
            raise BudgetDenied("Budget may be reserved only for a leased, not-yet-submitted job")
        if row["lease_expires_at"] < point.astimezone(timezone.utc).isoformat():
            raise BudgetDenied("Worker lease expired before budget reservation")
        if proposed > _amount(row["max_acknowledged_spend_usd"]):
            raise BudgetDenied("Estimate exceeds operator's acknowledged maximum")
        existing = conn.execute(
            "SELECT * FROM job_budget_reservations WHERE job_id=?", (job_id,),
        ).fetchone()
        if existing:
            if existing["status"] == "held" and _amount(existing["reserved_usd"]) == proposed:
                return dict(existing)
            raise BudgetDenied("Existing reservation is immutable; new job required")

        scopes = [("column", row["column_id"]), ("series", row["series_id"]),
                  ("provider", row["provider"])]
        policies = [_latest(conn, scope, value) for scope, value in scopes]
        # Consume both unfinished hold values and already documented real charges.
        active_rows = conn.execute(
            """SELECT r.reserved_usd,r.actual_usd,r.status,
               r.column_id,r.series_id,r.provider
               FROM job_budget_reservations r WHERE r.day_utc=?""", (day,),
        ).fetchall()
        for (scope, scope_id), policy in zip(scopes, policies):
            relevant = [
                item for item in active_rows
                if item[{"column": "column_id", "series": "series_id",
                         "provider": "provider"}[scope]] == scope_id
            ]
            held = [item for item in relevant if item["status"] == "held"]
            costs = [
                (_amount(item["reserved_usd"]) if item["status"] == "held"
                 else _amount(item["actual_usd"], allow_zero=True))
                for item in relevant if item["status"] in ("held", "reconciled")
            ]
            spent = sum(costs, Decimal("0"))
            if spent + proposed > _amount(policy["daily_limit_usd"]):
                raise BudgetDenied(f"{scope} daily budget would be exceeded")
            if len(held) >= policy["max_active_jobs"]:
                raise BudgetDenied(f"{scope} active job limit reached")
        reservation_id = new_id("reserve")
        snap = [
            {"scope": s, "scope_id": sid, "policy_id": p["id"],
             "revision": p["revision"]} for (s, sid), p in zip(scopes, policies)
        ]
        conn.execute(
            """INSERT INTO job_budget_reservations
            (id,job_id,column_id,series_id,provider,day_utc,reserved_usd,
             status,policy_snapshot_json,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (reservation_id, job_id, row["column_id"], row["series_id"],
             row["provider"], day, _usd(proposed), "held",
             json.dumps(snap, sort_keys=True), timestamp(), timestamp()),
        )
        _event(conn, reservation_id, "held", {
            "reserved_usd": _usd(proposed), "day_utc": day, "policies": snap,
            "verified_vendor_charge": False,
        })
        return dict(conn.execute(
            "SELECT * FROM job_budget_reservations WHERE id=?", (reservation_id,),
        ).fetchone())


def release_unsubmitted_reservation(
    db: Database, job_id: str, *, operator_reviewed: bool,
) -> dict:
    """Only release if no billable submission intent was ever recorded."""
    if operator_reviewed is not True:
        raise BudgetDenied("Manual review is required")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT r.*,j.generation_intent_recorded FROM job_budget_reservations r
            JOIN shot_jobs j ON j.id=r.job_id WHERE r.job_id=?""", (job_id,),
        ).fetchone()
        if row is None or row["status"] != "held":
            raise BudgetDenied("No active reservation")
        if row["generation_intent_recorded"]:
            raise BudgetDenied("A paid request may exist; cannot release unverified reserve")
        conn.execute(
            "UPDATE job_budget_reservations SET status='released',updated_at=? WHERE id=?",
            (timestamp(), row["id"]),
        )
        _event(conn, row["id"], "released_before_submission", {
            "new_model_requests": 0,
        })
        return dict(conn.execute(
            "SELECT * FROM job_budget_reservations WHERE id=?", (row["id"],),
        ).fetchone())


def record_operator_verified_charge(
    db: Database, job_id: str, *, amount_usd: str,
    evidence_reference: str, reviewer: str,
) -> dict:
    """Manually record vendor billing evidence; not automatic supplier verification."""
    charged = _amount(amount_usd, allow_zero=True)
    if not 3 <= len(evidence_reference) <= 500 or not 2 <= len(reviewer) <= 120:
        raise BudgetDenied("Billing evidence reference and reviewer are mandatory")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT r.*,j.generation_intent_recorded FROM job_budget_reservations r
            JOIN shot_jobs j ON j.id=r.job_id WHERE r.job_id=?""", (job_id,),
        ).fetchone()
        if row is None or row["status"] != "held" or not row["generation_intent_recorded"]:
            raise BudgetDenied("A held reservation with generation intent is required")
        conn.execute(
            """UPDATE job_budget_reservations SET status='reconciled', actual_usd=?,
            evidence_reference=?,reviewed_by=?,updated_at=? WHERE id=?""",
            (_usd(charged), evidence_reference, reviewer, timestamp(), row["id"]),
        )
        conn.execute(
            "UPDATE shot_jobs SET actual_vendor_charge_usd=?,updated_at=? WHERE id=?",
            (_usd(charged), timestamp(), job_id),
        )
        _event(conn, row["id"], "operator_entered_vendor_charge", {
            "amount_usd": _usd(charged),
            "over_reserved_amount": charged > _amount(row["reserved_usd"]),
            "evidence_reference": evidence_reference, "reviewer": reviewer,
        })
        return dict(conn.execute(
            "SELECT * FROM job_budget_reservations WHERE id=?", (row["id"],),
        ).fetchone())
