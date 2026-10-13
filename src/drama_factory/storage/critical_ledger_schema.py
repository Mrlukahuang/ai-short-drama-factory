"""PR-31b2j: *local read-only* critical ledger schema portability inventory.

Inventory structure, not source rows. This is not a remote Turso verifier, a
schema migration tool, a source copy, or a cutover permission. It never runs
CREATE/ALTER/UPDATE and does not initialize the source ledger.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path


_CRITICAL_TABLES = (
    "shot_jobs", "shot_job_events", "budget_policies",
    "job_budget_reservations", "budget_reservation_events",
)
_CRITICAL_INDEXES = (
    "idx_shot_jobs_provider_task", "idx_shot_jobs_series_status",
    "idx_shot_events_job", "idx_budget_policies_scope", "idx_job_budget_daily",
)
_EVENT_TRIGGERS = {
    "shot_job_events_immutable_update": ("shot_job_events", "update"),
    "shot_job_events_immutable_delete": ("shot_job_events", "delete"),
    "budget_events_immutable_update": ("budget_reservation_events", "update"),
    "budget_events_immutable_delete": ("budget_reservation_events", "delete"),
}
_FK_RULES = (
    ("shot_job_events", "shot_job_id", "shot_jobs"),
    ("job_budget_reservations", "job_id", "shot_jobs"),
    ("job_budget_reservations", "column_id", "columns"),
    ("job_budget_reservations", "series_id", "projects"),
    ("budget_reservation_events", "reservation_id", "job_budget_reservations"),
)
_UNIQUE_RULES = (
    ("shot_jobs", ("idempotency_key",), "unique_job_idempotency"),
    ("job_budget_reservations", ("job_id",), "unique_reservation_per_job"),
)


class CriticalSchemaDenied(ValueError):
    pass


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _unique_index_exists(conn, table: str, columns: tuple[str, ...]) -> bool:
    for row in conn.execute(f"PRAGMA index_list({_quoted(table)})"):
        # Index list: seq, name, unique, origin, partial.
        if not row[2] or row[4]:
            continue
        index_name = row[1]  # DB catalog value, escaped before interpolating.
        names = tuple(
            entry[2] for entry in conn.execute(
                f"PRAGMA index_info({_quoted(index_name)})"
            )
        )
        if names == columns:
            return True
    return False


def _normalized(sql: str) -> str:
    return re.sub(r"\s+", " ", (sql or "").strip()).lower()


def inspect_critical_local_schema(
    source: Path, *, offline_review_only: bool = False,
) -> dict:
    """Inspect an existing local file using a consistent query-only snapshot."""
    if offline_review_only is not True:
        raise CriticalSchemaDenied("Explicit offline schema review required")
    if "://" in str(source) or str(source) == ":memory:":
        raise CriticalSchemaDenied("Local SQLite file only")
    path = Path(source).expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        raise CriticalSchemaDenied("Existing, non-symlink local SQLite file required")
    # Query-only source: never call Database(), PRAGMA writable_schema,
    # sqlite DDL or DML. This is not an actual remote adapter.
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN")
        entries = {
            (kind, name): (tbl_name, ddl)
            for kind, name, tbl_name, ddl in conn.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
            )
        }
        blockers = []
        integrity = list(conn.execute("PRAGMA quick_check(10)"))
        if len(integrity) != 1 or integrity[0][0] != "ok":
            blockers.append("source_integrity_check_failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            blockers.append("foreign_key_data_violation")

        for table in _CRITICAL_TABLES:
            if ("table", table) not in entries:
                blockers.append("missing_table_" + table)

        for index in _CRITICAL_INDEXES:
            row = entries.get(("index", index))
            if row is None:
                blockers.append("missing_index_" + index)
            elif index == "idx_shot_jobs_provider_task":
                # Unique + partial are essential to avoid duplicate provider
                # task IDs while permitting multiple NULL task IDs.
                ix = next(
                    (record for record in conn.execute(
                        'PRAGMA index_list("shot_jobs")'
                    ) if record[1] == index), None,
                )
                cols = tuple(
                    item[2] for item in conn.execute(
                        'PRAGMA index_info("idx_shot_jobs_provider_task")'
                    )
                )
                if (
                    ix is None or not ix[2] or not ix[4]
                    or cols != ("provider", "provider_task_id")
                    or "where provider_task_id is not null" not in _normalized(row[1])
                ):
                    blockers.append("invalid_unique_partial_provider_task_index")

        for table, cols, label in _UNIQUE_RULES:
            if ("table", table) in entries and not _unique_index_exists(conn, table, cols):
                blockers.append("missing_" + label)

        for table, from_column, to_table in _FK_RULES:
            if ("table", table) not in entries:
                continue
            fks = {
                (row[3], row[2]) for row in conn.execute(
                    f"PRAGMA foreign_key_list({_quoted(table)})"
                )
            }
            if (from_column, to_table) not in fks:
                blockers.append(
                    "missing_foreign_key_" + table + "_" + from_column
                )

        for name, (table, action) in _EVENT_TRIGGERS.items():
            item = entries.get(("trigger", name))
            if item is None:
                blockers.append("missing_append_only_trigger_" + name)
            else:
                target_table, ddl = item
                statement = _normalized(ddl)
                # A same-name no-op trigger is not an append-only guard.
                if (
                    target_table != table
                    or f"before {action} on {table}" not in statement
                    or "raise(abort," not in statement.replace(" ", "")
                    or "append-only" not in statement
                    or " when " in statement
                ):
                    blockers.append("invalid_append_only_trigger_" + name)

        schema_digest = hashlib.sha256(
            json.dumps(
                sorted(
                    (kind, name, table, ddl)
                    for (kind, name), (table, ddl) in entries.items()
                    if kind in ("table", "index", "trigger")
                ),
                ensure_ascii=True, separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return {
            "mode": "offline_readonly_critical_sqlite_schema",
            "source_opened_read_only": True,
            "schema_fingerprint_sha256": schema_digest,
            "checked_critical_tables": len(_CRITICAL_TABLES),
            "checked_explicit_indexes": len(_CRITICAL_INDEXES),
            "checked_append_only_triggers": len(_EVENT_TRIGGERS),
            "checked_foreign_key_edges": len(_FK_RULES),
            "checked_unique_rules": len(_UNIQUE_RULES),
            "local_schema_safety_checks_passed": not blockers,
            "blockers": sorted(set(blockers)),
            "real_remote_schema_import_verified": False,
            "remote_transaction_atomicity_verified": False,
            "remote_multi_worker_concurrency_verified": False,
            "production_backend_switched": False,
            "live_cutover_permitted": False,
            "turso_connections": 0,
            "paid_provider_calls": 0,
        }
    finally:
        conn.rollback()
        conn.close()
