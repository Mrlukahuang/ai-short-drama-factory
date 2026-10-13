"""PR-31c1: evidence-only local SQLite pre-cutover review, never a cutover.

Compares an existing source, local snapshot, and recovered copy. Every result
explicitly denies remote cutover because no Writer freeze, provider billing
reconciliation, remote import, or remote transaction proof is performed here.
Nothing is created, uploaded, deleted, or changed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from drama_factory.storage.migration_readiness import inspect_local_sqlite
from drama_factory.storage.snapshot_rehearsal import _logical_digest


class OfflineCutoverDenied(ValueError):
    pass


def _existing_regular_path(value: Path) -> Path:
    path = Path(value).expanduser().absolute()
    if path.is_symlink() or not path.is_file():
        raise OfflineCutoverDenied("An existing non-symlink SQLite file is required")
    return path


def _valid_inventory(path: Path) -> dict:
    info = inspect_local_sqlite(path)
    if not (
        info["schema_compatible_with_current_ledger"]
        and info["integrity_ok"]
        and info["foreign_key_violation_count"] == 0
    ):
        raise OfflineCutoverDenied("Schema or source integrity is not valid")
    return info


def inspect_cutover_evidence(
    source: Path, backup: Path, recovered: Path, *,
    operator_approved: bool = False, offline_review_only: bool = False,
) -> dict:
    """Compare existing local files and report blockers without exposing data.

    Two source comparisons detect changes before/during this inspection but
    CANNOT prove writers are fenced afterward. That requires a separate,
    durable fleet-wide write gate and its own signed operator attestation.
    """
    if operator_approved is not True or offline_review_only is not True:
        raise OfflineCutoverDenied("Explicit offline-only review approval required")
    paths = tuple(_existing_regular_path(p) for p in (source, backup, recovered))
    if len(set(paths)) != 3:
        raise OfflineCutoverDenied("Source, backup and recovered paths must be distinct")
    src, snap, restored = paths

    source_before = _valid_inventory(src)
    backup_info = _valid_inventory(snap)
    restore_info = _valid_inventory(restored)
    src_before_digest = _logical_digest(src)
    backup_digest = _logical_digest(snap)
    restore_digest = _logical_digest(restored)
    source_after = _valid_inventory(src)
    src_after_digest = _logical_digest(src)

    blockers = set()
    if backup_digest != restore_digest:
        blockers.add("snapshot_restore_mismatch")
    if src_before_digest != backup_digest:
        blockers.add("source_snapshot_mismatch")
    if src_before_digest != src_after_digest or (
        source_before["risk_counts"] != source_after["risk_counts"]
    ):
        blockers.add("source_changed_during_review")
    if source_before["schema_fingerprint_sha256"] != source_after["schema_fingerprint_sha256"]:
        blockers.add("source_schema_changed_during_review")
    # Both inventories must be clean; a restored DB with held budget or
    # unresolved provider state is NOT suitable for unattended cutover.
    if not source_before["offline_snapshot_checks_passed"]:
        blockers.add("unsettled_source_work")
    if not source_after["offline_snapshot_checks_passed"]:
        blockers.add("unsettled_source_work")
    if not backup_info["offline_snapshot_checks_passed"]:
        blockers.add("unsettled_backup_work")
    if not restore_info["offline_snapshot_checks_passed"]:
        blockers.add("unsettled_restored_work")
    source_risks = source_after["risk_counts"]
    if source_risks is None:
        raise OfflineCutoverDenied("Source risk inventory incomplete")

    receipt = {
        "mode": "offline_cutover_evidence_review_only",
        "local_snapshot_and_restore_match": backup_digest == restore_digest,
        "source_matches_snapshot_during_review": (
            src_before_digest == backup_digest == src_after_digest
        ),
        "source_risk_counts": source_risks,
        "schema_sha256": backup_digest["schema_sha256"],
        "snapshot_logical_sha256": backup_digest["logical_sha256"],
        "table_count": backup_digest["table_count"],
        "row_count_total": backup_digest["row_count_total"],
        "offline_evidence_checks_passed": not blockers,
        "blockers": sorted(blockers),
        # Every condition below is intentionally hard-disabled. This is not
        # a fake user signoff or an implicit permission to run real migration.
        "fleet_writers_fenced": False,
        "provider_intents_reconciled_externally": False,
        "remote_transactions_verified": False,
        "remote_concurrency_verified": False,
        "remote_schema_and_import_verified": False,
        "rollback_on_real_workers_rehearsed": False,
        "live_cutover_authorized": False,
        "live_cutover_permitted": False,
        "source_modified": False,
        "destination_files_modified": False,
        "turso_connections": 0,
        "paid_provider_calls": 0,
    }
    # The evidence checksum proves only the internal consistency of this
    # report, NOT provenance, freshness, a signed freeze or tamper resistance.
    receipt["report_sha256"] = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return receipt
