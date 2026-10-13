"""PR-31b2m: fail-closed, local READ-ONLY production-vs-v3 migration gap gate.

No remote SDK/DB, source initializer, data migration, write or real media.
The v3 result is a fixed reference to a VERIFIED past GitHub Actions run,
not a fresh remote query or evidence for our actual production schema.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from drama_factory.storage.critical_ledger_schema import inspect_critical_local_schema
from drama_factory.storage.migration_readiness import inspect_local_sqlite

_REMOTE_V3_PROOF = "38417337745"
_REQUIRED_EXTRA_TABLES = (
    "stored_artifacts", "cloud_artifacts", "cloud_artifact_events",
    "drive_artifacts", "drive_artifact_events", "google_existing_files",
)
_REQUIRED_EXTRA_INDEXES = (
    "idx_stored_artifacts_production", "idx_cloud_artifacts_local",
    "idx_drive_artifacts_source",
)
_REQUIRED_EXTRA_TRIGGERS = {
    "cloud_events_immutable_update": ("cloud_artifact_events", "update"),
    "cloud_events_immutable_delete": ("cloud_artifact_events", "delete"),
    "drive_events_no_update": ("drive_artifact_events", "update"),
    "drive_events_no_delete": ("drive_artifact_events", "delete"),
}
_REQUIRED_EXTRA_FKS = (
    ("stored_artifacts", "production_id", "productions"),
    ("stored_artifacts", "episode_id", "episodes"),
    ("stored_artifacts", "series_id", "projects"),
    ("stored_artifacts", "shot_job_id", "shot_jobs"),
    ("cloud_artifacts", "artifact_id", "stored_artifacts"),
    ("cloud_artifact_events", "cloud_copy_id", "cloud_artifacts"),
    ("drive_artifacts", "artifact_id", "stored_artifacts"),
    ("drive_artifact_events", "drive_copy_id", "drive_artifacts"),
    ("google_existing_files", "job_id", "shot_jobs"),
)
_REQUIRED_COLUMNS = {
    "shot_jobs": (
        "lease_owner", "lease_expires_at", "attempts", "max_attempts",
        "generation_intent_recorded", "idempotency_key",
        "provider_task_id", "actual_vendor_charge_usd",
        "max_acknowledged_spend_usd",
    ),
    "budget_policies": (
        "scope", "scope_id", "revision", "daily_limit_usd",
        "max_active_jobs", "enabled",
    ),
    "job_budget_reservations": (
        "job_id", "reserved_usd", "actual_usd", "policy_snapshot_json",
        "evidence_reference", "reviewed_by", "status",
    ),
    "stored_artifacts": ("object_key", "sha256", "size_bytes", "shot_job_id"),
    "cloud_artifacts": ("artifact_id", "target_id", "sha256", "size_bytes"),
    "drive_artifacts": (
        "artifact_id", "parent_folder_id", "drive_file_id", "sha256", "size_bytes",
    ),
    "google_existing_files": ("job_id", "file_id", "recovery_active"),
}
_REQUIRED_UNIQUES = (
    ("budget_policies", ("scope", "scope_id", "revision"), "policy_revision"),
    ("stored_artifacts", ("object_key",), "stored_object"),
    ("cloud_artifacts", ("artifact_id", "target_id"), "cloud_copy"),
    ("drive_artifacts", ("artifact_id", "parent_folder_id"), "drive_copy"),
    ("drive_artifacts", ("parent_folder_id", "drive_file_id"), "drive_file"),
    ("google_existing_files", ("file_id",), "google_file"),
)
_PENDING_REMOTE_GATES = (
    "full_production_schema_remote_ddl_and_constraints",
    "three_scope_budget_reservation_remote_concurrency",
    "worker_lease_claim_and_provider_intent_fencing",
    "cross_runner_remote_single_writer_behavior",
    "network_commit_ack_loss_readonly_reconciliation",
    "source_snapshot_quiescence_and_cutover_rollback",
    "cloud_drive_artifact_receipt_recovery",
)


class RemoteGapDenied(ValueError):
    """The source is not allowed to be created, updated or replaced."""


def _quote(name: str) -> str:
    # Values here originate from fixed _REQUIRED_* constants or catalog
    # names returned by SQLite; no user SQL is ever accepted.
    return '"' + name.replace('"', '""') + '"'


def _has_unique(conn: sqlite3.Connection, table: str, columns: tuple[str, ...]) -> bool:
    for idx in conn.execute(f"PRAGMA index_list({_quote(table)})"):
        if not idx[2] or idx[4]:
            continue
        actual = tuple(
            row[2] for row in conn.execute(
                f"PRAGMA index_info({_quote(idx[1])})"
            )
        )
        if actual == columns:
            return True
    return False


def _extra_protection_scan(source: Path) -> dict:
    """One read-only snapshot of metadata; never inspect business row values."""
    conn = sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        entries = {
            (row[0], row[1]): (row[2], row[3])
            for row in conn.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
            )
        }
        tables = {name for kind, name in entries if kind == "table"}
        blockers: list[str] = []
        for table in _REQUIRED_EXTRA_TABLES:
            if table not in tables:
                blockers.append("missing_asset_table_" + table)
        for index in _REQUIRED_EXTRA_INDEXES:
            if ("index", index) not in entries:
                blockers.append("missing_asset_index_" + index)
        for table, columns in _REQUIRED_COLUMNS.items():
            if table not in tables:
                blockers.append("missing_required_table_" + table)
                continue
            seen = {
                row[1] for row in conn.execute(
                    f"PRAGMA table_info({_quote(table)})"
                )
            }
            if not set(columns).issubset(seen):
                blockers.append("missing_required_columns_" + table)
        for table, cols, label in _REQUIRED_UNIQUES:
            if table in tables and not _has_unique(conn, table, cols):
                blockers.append("missing_unique_" + label)
        for table, column, parent in _REQUIRED_EXTRA_FKS:
            if table not in tables:
                continue
            observed = {
                (row[3], row[2]) for row in conn.execute(
                    f"PRAGMA foreign_key_list({_quote(table)})"
                )
            }
            if (column, parent) not in observed:
                blockers.append("missing_asset_fk_" + table + "_" + column)
        for name, (table, action) in _REQUIRED_EXTRA_TRIGGERS.items():
            row = entries.get(("trigger", name))
            if row is None:
                blockers.append("missing_asset_immutable_trigger_" + name)
                continue
            owner, sql = row
            normalized = re.sub(r"\s+", " ", sql.lower())
            if (
                owner != table
                or f"before {action} on {table}" not in normalized
                or "raise(abort," not in normalized.replace(" ", "")
                or "append-only" not in normalized
                or " when " in normalized
            ):
                blockers.append("invalid_asset_immutable_trigger_" + name)
        return {
            "total_local_tables": len(tables),
            "total_local_named_indexes": sum(
                kind == "index" for kind, _ in entries
            ),
            "total_local_triggers": sum(
                kind == "trigger" for kind, _ in entries
            ),
            "checked_asset_tables": len(_REQUIRED_EXTRA_TABLES),
            "checked_asset_indexes": len(_REQUIRED_EXTRA_INDEXES),
            "checked_asset_audit_triggers": len(_REQUIRED_EXTRA_TRIGGERS),
            "checked_additional_fk_edges": len(_REQUIRED_EXTRA_FKS),
            "checked_uniques": len(_REQUIRED_UNIQUES),
            "checked_column_groups": len(_REQUIRED_COLUMNS),
            "asset_schema_blockers": sorted(set(blockers)),
        }
    finally:
        conn.rollback()
        conn.close()


def assess_pr31_cutover_gaps(
    source: Path, *, offline_review_only: bool = False,
) -> dict:
    """Combine local safety checks with the already verified v3 scope.

    The two existing inspectors and extra schema scan use separate read-only
    snapshots. They are NOT a consistent global snapshot if writers run; a
    production cutover requires its own quiescence and snapshot protocol.
    """
    if offline_review_only is not True:
        raise RemoteGapDenied("Explicit offline read-only review required")
    if "://" in str(source) or str(source) == ":memory:":
        raise RemoteGapDenied("Existing local SQLite file only")
    path = Path(source).expanduser().absolute()
    if path.is_symlink() or not path.is_file() or path.parent.is_symlink():
        raise RemoteGapDenied("Existing non-symlink local source required")
    inventory = inspect_local_sqlite(path)
    critical = inspect_critical_local_schema(path, offline_review_only=True)
    extra = _extra_protection_scan(path)
    blockers = sorted(set(
        inventory["blockers"] + critical["blockers"] + extra["asset_schema_blockers"]
    ))
    local_structure_ok = bool(
        inventory["schema_compatible_with_current_ledger"]
        and critical["local_schema_safety_checks_passed"]
        and not extra["asset_schema_blockers"]
    )
    local_operations_quiet = bool(inventory["offline_snapshot_checks_passed"])
    return {
        "mode": "pr31_production_vs_v3_offline_readonly_gap_assessment",
        "source_opened_read_only": True,
        "source_modified_by_this_assessment": False,
        "reference_real_v3_actions_run_id": _REMOTE_V3_PROOF,
        "remote_v3_synthetic_serial_multitable_verified": True,
        "remote_v3_synthetic_fk_partial_unique_audit_verified": True,
        "remote_v3_only_test_objects": 10,
        "full_production_tables_run_remotely_in_v3": 0,
        "local_inventory_schema_fingerprint_sha256":
            inventory["schema_fingerprint_sha256"],
        "local_critical_schema_fingerprint_sha256":
            critical["schema_fingerprint_sha256"],
        "local_schema_metrics": {
            key: value for key, value in extra.items()
            if key not in ("asset_schema_blockers",)
        },
        "local_schema_safety_checks_passed": local_structure_ok,
        "local_quiescence_checks_passed": local_operations_quiet,
        "local_operational_risk_counts": inventory["risk_counts"],
        "source_global_cross_scan_snapshot_verified": False,
        "blockers": blockers,
        "pending_remote_gates": list(_PENDING_REMOTE_GATES),
        "full_production_schema_import_verified": False,
        "remote_budget_fencing_verified": False,
        "remote_multiworker_concurrency_verified": False,
        "remote_network_commit_recovery_verified": False,
        "cloud_artifact_migration_verified": False,
        "production_backend_switched": False,
        "live_cutover_permitted": False,
        "requires_new_live_write_authorization": True,
        "turso_connections": 0,
        "paid_provider_calls": 0,
    }


def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline only: assess PR-31 gaps, never perform cutover"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--confirmation", required=True)
    args = parser.parse_args(argv)
    try:
        if args.confirmation != "PR31_LOCAL_GAP_REVIEW_ONLY":
            raise RemoteGapDenied("Explicit read-only confirmation required")
        receipt = assess_pr31_cutover_gaps(
            args.source, offline_review_only=True,
        )
    except Exception:
        print("PR-31 gap assessment failed (details redacted)", file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
