"""PR-31c0: offline SQLite backup -> restore -> logical checksum rehearsal.

Never creates or connects a Turso database; no source-file migrations.
The restore is a separate local test file, not production cutover.
Do not run on a real production source without a distinct operator approval.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

from drama_factory.storage.migration_readiness import inspect_local_sqlite


class SnapshotRehearsalDenied(ValueError):
    pass


def _source_path(source: Path) -> Path:
    path = Path(source).expanduser().absolute()
    if path.is_symlink() or not path.is_file() or "://" in str(source):
        raise SnapshotRehearsalDenied("An existing regular local SQLite source is required")
    return path


def _new_destination(destination: Path, sources: tuple[Path, ...]) -> Path:
    dest = Path(destination).expanduser().absolute()
    if not dest.parent.is_dir() or dest.parent.is_symlink():
        raise SnapshotRehearsalDenied("An existing non-symlink destination directory is required")
    if dest in sources or dest.is_symlink() or dest.exists():
        raise SnapshotRehearsalDenied("Refusing to overwrite a source or existing destination")
    return dest


def _create_private_empty_file(path: Path) -> None:
    # Files are owned by the caller; never replace/overwrite a prior snapshot.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    os.close(fd)


def _open_readonly(path: Path):
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _encode_value(value):
    if value is None:
        return ["null"]
    if isinstance(value, bytes):
        return ["blob_sha256", len(value), hashlib.sha256(value).hexdigest()]
    if isinstance(value, str):
        return ["text", value]
    if isinstance(value, int):
        return ["integer", str(value)]
    if isinstance(value, float):
        return ["real_hex", value.hex()]
    raise SnapshotRehearsalDenied("Unsupported source SQLite cell type")


def _logical_digest(path: Path) -> dict:
    """Deterministic whole-database logical digest, never returning source data."""
    conn = _open_readonly(path)
    try:
        # Hold a single read transaction throughout schema and row hashing.
        # Without BEGIN, commits by a concurrent writer between table reads
        # could produce a checksum that never existed in a real snapshot.
        conn.execute("BEGIN")
        if conn.execute("PRAGMA quick_check(10)").fetchone()[0] != "ok":
            raise SnapshotRehearsalDenied("SQLite integrity verification failed")
        if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise SnapshotRehearsalDenied("Source foreign key verification failed")
        entries = conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        ).fetchall()
        schema_sha = hashlib.sha256(
            json.dumps(entries, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
        table_names = [entry[1] for entry in entries if entry[0] == "table"]
        full = hashlib.sha256()
        full.update(schema_sha.encode())
        count_total = 0
        for name in sorted(table_names):
            # Names come from the database catalogue; quote as SQLite identifiers.
            escaped = name.replace('"', '""')
            row_digests = []
            for row in conn.execute(f'SELECT * FROM "{escaped}"'):
                encoded = json.dumps(
                    [_encode_value(v) for v in row],
                    ensure_ascii=True, separators=(",", ":"),
                ).encode()
                row_digests.append(hashlib.sha256(encoded).digest())
            count_total += len(row_digests)
            full.update(name.encode())
            full.update(len(row_digests).to_bytes(8, "big"))
            for row_digest in sorted(row_digests):
                full.update(row_digest)
        return {
            "table_count": len(table_names),
            "row_count_total": count_total,
            "schema_sha256": schema_sha,
            "logical_sha256": full.hexdigest(),
        }
    finally:
        conn.rollback()  # End the read snapshot; never mutate source rows.
        conn.close()


def _copy_consistent(source: Path, destination: Path) -> None:
    _create_private_empty_file(destination)
    try:
        origin = _open_readonly(source)
        try:
            target = sqlite3.connect(destination, timeout=10)
            try:
                origin.backup(target, pages=128)
                target.commit()
            finally:
                target.close()
        finally:
            origin.close()
    except BaseException:
        # Only remove our own newly-created, incomplete output on failure.
        destination.unlink(missing_ok=True)
        raise


def rehearse_local_snapshot(
    source: Path,
    backup: Path,
    restored: Path,
    *,
    operator_approved: bool = False,
    offline_rehearsal_only: bool = False,
) -> dict:
    """Create exactly two new local files and prove snapshot == restore.

    No live cutover switch exists. The source is opened read-only. The
    backup API itself takes a consistent source snapshot, including WAL.
    """
    if operator_approved is not True or offline_rehearsal_only is not True:
        raise SnapshotRehearsalDenied("Explicit offline snapshot rehearsal approval required")
    original = _source_path(source)
    if Path(backup).expanduser().absolute() == Path(restored).expanduser().absolute():
        raise SnapshotRehearsalDenied("Backup and restored file must differ")
    backup_path = _new_destination(backup, (original,))
    restored_path = _new_destination(restored, (original, backup_path))
    before = inspect_local_sqlite(original)
    if not (
        before["integrity_ok"]
        and before["foreign_key_violation_count"] == 0
        and before["schema_compatible_with_current_ledger"]
    ):
        raise SnapshotRehearsalDenied("Source must pass schema and integrity checks")
    _copy_consistent(original, backup_path)
    snapshot = inspect_local_sqlite(backup_path)
    if not (
        snapshot["integrity_ok"]
        and snapshot["foreign_key_violation_count"] == 0
        and snapshot["schema_compatible_with_current_ledger"]
    ):
        raise SnapshotRehearsalDenied("Snapshot failed schema or integrity checks")
    backup_digest = _logical_digest(backup_path)
    _copy_consistent(backup_path, restored_path)
    recovery_digest = _logical_digest(restored_path)
    if backup_digest != recovery_digest:
        raise SnapshotRehearsalDenied("Restored SQLite logical checksum mismatch")
    return {
        "mode": "offline_sqlite_snapshot_restore_rehearsal",
        "created_new_backup": True,
        "created_new_restore": True,
        "original_opened_read_only": True,
        "live_turso_connections": 0,
        "source_data_uploaded": False,
        "backup_and_restore_logically_equal": True,
        "table_count": backup_digest["table_count"],
        "row_count_total": backup_digest["row_count_total"],
        "schema_sha256": backup_digest["schema_sha256"],
        "logical_sha256": backup_digest["logical_sha256"],
        "unsettled_source_risk_counts": snapshot["risk_counts"],
        "remote_transaction_verified": False,
        "remote_concurrency_verified": False,
        "production_backend_switched": False,
        "live_cutover_permitted": False,
        "new_ai_model_generation_calls": 0,
    }
