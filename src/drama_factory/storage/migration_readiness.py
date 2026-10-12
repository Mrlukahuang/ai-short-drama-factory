"""Read-only local SQLite inventory for the *planning* stage of PR-31.

This intentionally does not import the Turso adapter, instantiate Database
(which would run migrations), copy rows or expose IDs/payloads. It cannot
authorize a live migration even when all offline checks pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

# Specific tables/columns on which the risk inspection depends. A partial or
# older schema is reported as incompatible rather than silently re-initialized.
_REQUIRED_COLUMNS = {
    "columns": ("id",),
    "projects": ("id", "column_id"),
    "episodes": ("id", "project_id"),
    "productions": ("id", "episode_id", "status"),
    "shot_jobs": (
        "id", "status", "generation_intent_recorded", "actual_vendor_charge_usd",
        "provider_task_id", "lease_owner", "lease_expires_at",
    ),
    "shot_job_events": ("id", "shot_job_id"),
    "budget_policies": ("id", "scope", "scope_id", "revision"),
    "job_budget_reservations": ("id", "job_id", "status"),
    "budget_reservation_events": ("id", "reservation_id"),
    "google_existing_files": ("job_id", "recovery_active"),
    "stored_artifacts": ("id", "series_id", "production_id"),
    "drive_artifacts": ("id", "artifact_id", "drive_file_id"),
    "drive_artifact_events": ("id", "drive_copy_id"),
}

# These counts deliberately contain no IDs, names, paths, prompts or content.
_RISK_QUERIES = {
    "leased_jobs": "SELECT COUNT(*) FROM shot_jobs WHERE status='leased'",
    "uncertain_submission_jobs": (
        "SELECT COUNT(*) FROM shot_jobs "
        "WHERE status IN ('submission_intent','submitted')"
    ),
    "unreconciled_vendor_intents": (
        "SELECT COUNT(*) FROM shot_jobs WHERE generation_intent_recorded=1 "
        "AND actual_vendor_charge_usd IS NULL"
    ),
    "held_budget_reservations": (
        "SELECT COUNT(*) FROM job_budget_reservations WHERE status='held'"
    ),
    "active_google_recoveries": (
        "SELECT COUNT(*) FROM google_existing_files WHERE recovery_active=1"
    ),
}

# Even an apparently quiescent source is *not* validated for remote SQL
# atomicity, snapshot consistency across Workers or cutover/rollback.
_UNVALIDATED_REMOTE = (
    "remote_begin_immediate_semantics",
    "remote_budget_reservation_atomicity",
    "remote_worker_lease_and_provider_idempotency",
    "cross_worker_cutover_and_rollback",
)


class MigrationInventoryError(ValueError):
    """No source file will ever be created or updated by the inventory."""


def inspect_local_sqlite(source: Path) -> dict:
    """Read a consistent snapshot of an existing source DB, without writes.

    No sqlite3 Database() constructor is used: that constructor executes
    CREATE / ALTER / UPDATE and must NEVER run on a source during inventory.
    """
    path = Path(source).expanduser().absolute()
    if not path.is_file():
        raise MigrationInventoryError("Existing local SQLite file required")
    # mode=ro fails closed if missing; query_only forbids changes even if a
    # caller later introduces DML by mistake. The source pathname is not logged.
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN")  # consistent read transaction, not BEGIN IMMEDIATE
        try:
            check = list(db.execute("PRAGMA quick_check(10)"))
            integrity_ok = len(check) == 1 and check[0][0] == "ok"
            fk_violations = sum(1 for _ in db.execute("PRAGMA foreign_key_check"))
            entries = [
                (row[0], row[1], row[2], row[3])
                for row in db.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_master "
                    "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
                )
            ]
            fingerprint = hashlib.sha256(
                json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode()
            ).hexdigest()
            tables = {
                row[1] for row in entries if row[0] == "table"
            }
            missing_tables = sorted(set(_REQUIRED_COLUMNS) - tables)
            incomplete_tables = []
            for table, needed in _REQUIRED_COLUMNS.items():
                if table not in tables:
                    continue
                # All identifiers in this PRAGMA are fixed literals defined
                # above, never taken from untrusted schema entries.
                present = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
                if not set(needed).issubset(present):
                    incomplete_tables.append(table)
            valid_schema = not missing_tables and not incomplete_tables
            risks = None
            if valid_schema and integrity_ok:
                risks = {
                    label: int(db.execute(query).fetchone()[0])
                    for label, query in _RISK_QUERIES.items()
                }
            blockers = []
            if not integrity_ok:
                blockers.append("source_integrity_check_failed")
            if fk_violations:
                blockers.append("source_foreign_key_violations")
            if not valid_schema:
                blockers.append("source_schema_incomplete")
            if risks is not None:
                blockers.extend(label for label, count in risks.items() if count)
            return {
                "mode": "local_sqlite_read_only",
                "source_opened_read_only": True,
                "source_modified": False,
                "table_count": len(tables),
                "schema_fingerprint_sha256": fingerprint,
                "schema_compatible_with_current_ledger": valid_schema,
                "missing_required_tables": missing_tables,
                "incomplete_required_tables": incomplete_tables,
                "integrity_ok": integrity_ok,
                "foreign_key_violation_count": fk_violations,
                "risk_counts": risks,
                "offline_snapshot_checks_passed": not blockers,
                "blockers": blockers,
                "unvalidated_remote_requirements": list(_UNVALIDATED_REMOTE),
                "live_migration_authorized": False,
                "live_cutover_permitted": False,
                "turso_connections": 0,
                "new_ai_model_generation_calls": 0,
            }
        finally:
            db.rollback()  # ends read snapshot only
    finally:
        db.close()


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description="Inspect one existing SQLite source without any writes")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--confirmation", required=True,
        help="Must equal INSPECT_LOCAL_SQLITE_READ_ONLY",
    )
    args = parser.parse_args(argv)
    if args.confirmation != "INSPECT_LOCAL_SQLITE_READ_ONLY":
        raise MigrationInventoryError("Explicit read-only inspection confirmation required")
    return inspect_local_sqlite(args.source)


def run_cli(argv=None) -> int:
    try:
        result = main(argv)
    except Exception:
        # File paths, schema/SQL error details and secrets never reach CI logs.
        print("PR-31a SQLite inventory failed (details redacted)", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
