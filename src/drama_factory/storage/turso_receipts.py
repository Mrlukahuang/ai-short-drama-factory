"""Opt-in Turso mirror for VERIFIED Google Drive video metadata only.

This is deliberately not a replacement for the transactional SQLite production
database. It writes a separate immutable receipt table in a dedicated Turso DB.
It never sends raw videos, OAuth credentials, model prompts, or local file paths.
No network or remote writes occur until the caller explicitly authorizes one.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from drama_factory.db import Database
from drama_factory.storage.artifacts import verify_stored_artifact


class TursoReceiptError(ValueError):
    pass


# Remote database must be dedicated to THIS factory, not a shared Turso DB
# belonging to the user's unrelated apps.
_DB_HOST = re.compile(r"ai-short-drama-factory-[a-z0-9-]+\.turso\.io")
_SHA = re.compile(r"[0-9a-f]{64}")
_RECEIPT_COLUMNS = (
    "drive_copy_id", "artifact_id", "series_id", "production_id",
    "episode_id", "shot_job_id", "kind", "object_key", "sha256",
    "size_bytes", "drive_file_id", "parent_folder_id", "remote_folder_id",
)
_TABLE = "drama_drive_receipts_v1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS drama_drive_receipts_v1 (
 drive_copy_id TEXT PRIMARY KEY,
 artifact_id TEXT NOT NULL,
 series_id TEXT NOT NULL,
 production_id TEXT NOT NULL,
 episode_id TEXT NOT NULL,
 shot_job_id TEXT,
 kind TEXT NOT NULL CHECK(kind IN ('shot_video','episode_preview')),
 object_key TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes>=1000),
 drive_file_id TEXT NOT NULL,
 parent_folder_id TEXT NOT NULL,
 remote_folder_id TEXT NOT NULL,
 UNIQUE(parent_folder_id,drive_file_id)
);
"""


@dataclass(frozen=True)
class TursoMetadataTarget:
    url: str
    engine: str

    def __post_init__(self):
        if self.engine not in {"libsql", "turso"}:
            raise TursoReceiptError("Choose libsql or turso engine explicitly")
        parsed = urlsplit(self.url)
        schemes = {"libsql", "https"} if self.engine == "libsql" else {"https"}
        if (
            parsed.scheme not in schemes
            or not parsed.hostname
            or not _DB_HOST.fullmatch(parsed.hostname)
            or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment
            or parsed.username or parsed.password
            or parsed.port is not None
        ):
            raise TursoReceiptError(
                "Use a dedicated ai-short-drama-factory-<org>.turso.io URL "
                "without embedded credentials, paths or query parameters"
            )


def _open_remote(target: TursoMetadataTarget, token: str):
    if target.engine == "libsql":
        try:
            import libsql
        except ImportError as exc:
            raise TursoReceiptError("Install the turso-libsql extra") from exc
        return libsql.connect(database=target.url, auth_token=token)
    try:
        import turso_serverless
    except ImportError as exc:
        raise TursoReceiptError("Install the turso-serverless extra") from exc
    return turso_serverless.connect(target.url, auth_token=token)


def _source_receipt(db: Database, copy_id: str, local_store_root: Path) -> tuple:
    record = db.one(
        """SELECT d.id AS drive_copy_id, d.artifact_id, a.series_id,
                  a.production_id, a.episode_id, a.shot_job_id, a.kind,
                  d.object_key, d.sha256, d.size_bytes,
                  d.drive_file_id, d.parent_folder_id, d.remote_folder_id,
                  a.object_key AS local_key, a.sha256 AS local_sha,
                  a.size_bytes AS local_size
           FROM drive_artifacts d
           JOIN stored_artifacts a ON a.id=d.artifact_id
           WHERE d.id=?""", (copy_id,),
    )
    if record is None:
        raise TursoReceiptError("Verified Drive receipt not found")
    events = db.many(
        "SELECT action FROM drive_artifact_events WHERE drive_copy_id=?",
        (copy_id,),
    )
    actions = {e["action"] for e in events}
    if not {
        "uploaded_verified_by_download",
        "downloaded_verified_local_copy",
    }.issubset(actions):
        raise TursoReceiptError("Drive upload AND recovery must both be verified")
    if (
        record["sha256"] != record["local_sha"]
        or record["size_bytes"] != record["local_size"]
        or record["object_key"] != record["local_key"]
        or not _SHA.fullmatch(record["sha256"])
    ):
        raise TursoReceiptError("Drive and local artifact identifiers disagree")
    checked = verify_stored_artifact(db, record["artifact_id"], local_store_root)
    if (
        checked["sha256"] != record["sha256"]
        or checked["size_bytes"] != record["size_bytes"]
        or checked["series_id"] != record["series_id"]
        or checked["production_id"] != record["production_id"]
    ):
        raise TursoReceiptError("Recovered local video bytes failed verification")
    return tuple(record[name] for name in _RECEIPT_COLUMNS)


def mirror_verified_drive_receipt(
    db: Database, drive_copy_id: str, local_store_root: Path,
    target: TursoMetadataTarget, *, operator_approved: bool = False,
    remote=None,
) -> dict:
    """Write one immutable metadata receipt to a dedicated Turso instance.

    An existing receipt is accepted ONLY if every column still matches;
    duplicate or conflicting cloud IDs never overwrite a previously recorded
    result. All remote access is opt-in. The source SQLite remains authoritative
    for the current local Worker and its budget/approval state machine.
    """
    if (
        operator_approved is not True
        or os.getenv("DRAMA_ENABLE_TURSO_METADATA_WRITE") != "YES"
        or os.getenv("DRAMA_TURSO_WRITE_CONFIRM") != "MIRROR_VERIFIED_DRIVE_METADATA"
    ):
        raise TursoReceiptError("Turso metadata transfer is disabled")
    if not isinstance(target, TursoMetadataTarget):
        raise TursoReceiptError("Explicit validated Turso target required")
    value = _source_receipt(db, drive_copy_id, local_store_root)
    close_remote = False
    if remote is None:
        token = os.getenv("TURSO_AUTH_TOKEN")
        if not token:
            raise TursoReceiptError("TURSO_AUTH_TOKEN is missing")
        remote = _open_remote(target, token)
        close_remote = True
    try:
        remote.execute(_SCHEMA)
        columns = ", ".join(_RECEIPT_COLUMNS)
        placeholders = ", ".join(["?"] * len(_RECEIPT_COLUMNS))
        existing = remote.execute(
            f"SELECT {columns} FROM {_TABLE} WHERE drive_copy_id=?",
            (drive_copy_id,),
        ).fetchone()
        cached = existing is not None
        if existing is not None:
            if tuple(existing) != value:
                raise TursoReceiptError("Turso immutable metadata receipt conflict")
        else:
            # Never REPLACE or UPDATE; remote PK/UNIQUE constraints reject races
            # and attempts to bind the same Drive file to another source.
            remote.execute(
                f"INSERT INTO {_TABLE} ({columns}) VALUES ({placeholders})",
                value,
            )
        remote.commit()
        verified = remote.execute(
            f"SELECT {columns} FROM {_TABLE} WHERE drive_copy_id=?",
            (drive_copy_id,),
        ).fetchone()
        if verified is None or tuple(verified) != value:
            raise TursoReceiptError("Turso remote readback mismatch")
        return {
            "mirrored": True, "cached": cached,
            "table": _TABLE, "engine": target.engine,
            "drive_copy_id": drive_copy_id,
            "series_id": value[2], "production_id": value[3],
            "sha256": value[8], "size_bytes": value[9],
            "google_drive_file_id_redacted": True,
            "new_ai_model_generation_calls": 0,
        }
    except Exception:
        # The remote library may have already committed a DDL/INSERT even if
        # readback fails. Retrying will only accept exactly matching bytes.
        try:
            remote.rollback()
        except Exception:
            pass
        raise
    finally:
        if close_remote:
            remote.close()
