"""Read-only production operations overview for scoped multi-series factories.

No model SDK, network access, worker claim, policy mutation, or API route.
Provider budgets are global across columns and must be labeled accordingly.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal

from drama_factory.db import Database

STATES = (
    "pending", "leased", "submission_intent", "submitted",
    "succeeded", "failed", "cancelled",
)


class OperationsScopeError(ValueError):
    pass


def _when(now: datetime | None) -> datetime:
    stamp = now if now is not None else datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise OperationsScopeError("Aware UTC time is required")
    return stamp.astimezone(timezone.utc)


def _money(value) -> Decimal:
    return Decimal(str(value)) if value is not None else Decimal("0")


def _latest_policy(conn, scope, scope_id):
    row = conn.execute(
        """SELECT scope,scope_id,revision,daily_limit_usd,max_active_jobs,enabled
        FROM budget_policies WHERE scope=? AND scope_id=?
        ORDER BY revision DESC LIMIT 1""", (scope, scope_id),
    ).fetchone()
    return dict(row) if row else None


def _scope_budget(conn, *, scope: str, scope_id: str, day: str) -> dict:
    policy = _latest_policy(conn, scope, scope_id)
    column = {"column": "column_id", "series": "series_id",
              "provider": "provider"}[scope]
    rows = conn.execute(
        f"""SELECT reserved_usd,actual_usd,status FROM job_budget_reservations
        WHERE day_utc=? AND {column}=?""", (day, scope_id),
    ).fetchall()
    held = sum((_money(r["reserved_usd"]) for r in rows
                if r["status"] == "held"), Decimal("0"))
    reconciled = sum((_money(r["actual_usd"]) for r in rows
                      if r["status"] == "reconciled"), Decimal("0"))
    in_flight = sum(r["status"] == "held" for r in rows)
    return {
        "scope": scope, "scope_id": scope_id,
        "global_across_columns": scope == "provider",
        "policy": policy,
        "held_usd": f"{held:.2f}",
        "reconciled_usd": f"{reconciled:.2f}",
        "committed_usd": f"{held + reconciled:.2f}",
        "held_job_count": in_flight,
        "free_authorization_usd": (
            f"{_money(policy['daily_limit_usd']) - held - reconciled:.2f}"
            if policy and policy["enabled"] else None
        ),
    }


def production_operations(
    db: Database, *, column_id: str | None = None,
    series_id: str | None = None, now: datetime | None = None,
) -> dict:
    """Snapshot grouped by series and column with no externally sensitive IDs.

    Returned job identifiers are internal scoped IDs; never expose this function
    through a public API without authorization and tenant filtering.
    """
    clock = _when(now)
    with db.connection() as conn:
        if column_id is not None and conn.execute(
            "SELECT id FROM columns WHERE id=?", (column_id,),
        ).fetchone() is None:
            raise OperationsScopeError("Column does not exist")
        if series_id is not None:
            series = conn.execute(
                "SELECT id,column_id FROM projects WHERE id=?", (series_id,),
            ).fetchone()
            if series is None:
                raise OperationsScopeError("Series does not exist")
            if column_id is not None and series["column_id"] != column_id:
                raise OperationsScopeError("Series is outside selected column")
        where = []
        params = []
        if column_id is not None:
            where.append("p.column_id=?")
            params.append(column_id)
        if series_id is not None:
            where.append("p.id=?")
            params.append(series_id)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        series_rows = conn.execute(
            "SELECT p.id,p.title,p.column_id,c.name AS column_name "
            "FROM projects p JOIN columns c ON p.column_id=c.id"
            + clause + " ORDER BY p.column_id,p.id", tuple(params),
        ).fetchall()
        series_list = []
        involved_providers = set()
        included_columns = set()
        totals = Counter()
        alerts = Counter()
        for series in series_rows:
            sid = series["id"]
            included_columns.add(series["column_id"])
            jobs = conn.execute(
                """SELECT j.id,j.production_id,j.status,j.provider,j.provider_task_id,
                j.generation_intent_recorded,j.actual_vendor_charge_usd,
                j.lease_expires_at,g.recovery_active
                FROM shot_jobs j LEFT JOIN google_existing_files g ON g.job_id=j.id
                WHERE j.series_id=? ORDER BY j.production_id,j.shot_id""",
                (sid,),
            ).fetchall()
            prod_rows = conn.execute(
                """SELECT p.id,p.status FROM productions p
                JOIN episodes e ON e.id=p.episode_id
                WHERE e.project_id=? ORDER BY p.id""", (sid,),
            ).fetchall()
            counts = Counter(j["status"] for j in jobs)
            provider_counts = Counter(j["provider"] for j in jobs)
            for j in jobs:
                involved_providers.add(j["provider"])
                if j["generation_intent_recorded"] and j["actual_vendor_charge_usd"] is None:
                    alerts["vendor_charges_unverified"] += 1
                if (
                    j["status"] == "failed" and j["generation_intent_recorded"]
                    and not j["provider_task_id"]
                ):
                    alerts["paid_submission_uncertain_manual_review"] += 1
                if j["status"] == "submitted" and j["provider_task_id"]:
                    alerts["existing_provider_tasks_to_recover"] += 1
                if j["recovery_active"]:
                    alerts["video_downloads_locked"] += 1
                if j["status"] in ("leased", "submission_intent") and j["lease_expires_at"]:
                    if datetime.fromisoformat(j["lease_expires_at"]).astimezone(
                        timezone.utc
                    ) < clock:
                        alerts["expired_worker_leases"] += 1
            totals.update(counts)
            series_list.append({
                "series_id": sid, "series_title": series["title"],
                "column_id": series["column_id"],
                "production_count": len(prod_rows),
                "production_statuses": dict(Counter(p["status"] for p in prod_rows)),
                "shot_job_count": len(jobs),
                "shot_job_statuses": {s: counts.get(s, 0) for s in STATES},
                "providers": dict(provider_counts),
                "budget": _scope_budget(
                    conn, scope="series", scope_id=sid, day=clock.date().isoformat(),
                ),
            })
        day = clock.date().isoformat()
        return {
            "day_utc": day,
            "filters": {"column_id": column_id, "series_id": series_id},
            "series_count": len(series_list),
            "series": series_list,
            "shot_job_totals": {s: totals.get(s, 0) for s in STATES},
            "alerts": {
                key: alerts.get(key, 0)
                for key in (
                    "vendor_charges_unverified",
                    "paid_submission_uncertain_manual_review",
                    "existing_provider_tasks_to_recover",
                    "video_downloads_locked", "expired_worker_leases",
                )
            },
            "column_budgets": [
                _scope_budget(conn, scope="column", scope_id=cid, day=day)
                for cid in sorted(included_columns)
            ],
            "provider_budgets_global": [
                _scope_budget(conn, scope="provider", scope_id=provider, day=day)
                for provider in sorted(involved_providers)
            ],
            "read_only": True,
            "new_model_generation_calls": 0,
            "billing_scope": "local_authorization_and_manual_evidence_only",
        }
