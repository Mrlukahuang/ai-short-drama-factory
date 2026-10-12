"""One explicitly approved synthetic MP4 -> Drive -> Turso metadata canary.

No production database migration, paid AI provider, public endpoint or background
worker. Offline mode uses FakeDrive and an in-memory SQLite SQL adapter.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

from drama_factory.storage.turso_receipts import (
    TursoMetadataTarget, TursoReceiptError, _open_remote,
    mirror_verified_drive_receipt,
)

_CONFIRM = "UPLOAD_AND_MIRROR_ONE_VERIFIED_MP4"
_MIRROR_CONFIRM = "MIRROR_VERIFIED_DRIVE_METADATA"
_FAKE_TARGET = TursoMetadataTarget(
    url="libsql://ai-short-drama-factory-fake.turso.io", engine="libsql",
)


@contextmanager
def _fake_turso_gates():
    """Offline-only test gates; never construct a remote client."""
    names = ("DRAMA_ENABLE_TURSO_METADATA_WRITE", "DRAMA_TURSO_WRITE_CONFIRM")
    old = {name: os.environ.get(name) for name in names}
    try:
        os.environ[names[0]] = "YES"
        os.environ[names[1]] = _MIRROR_CONFIRM
        yield
    finally:
        for name, value in old.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _check_live_preconditions(parent_folder_id: str, target: TursoMetadataTarget | None):
    from drama_factory.storage.drive_objects import _file_id

    if os.getenv("DRAMA_TURSO_CANARY_CONFIRM") != _CONFIRM:
        raise TursoReceiptError("One-file Turso canary manual confirmation required")
    if os.getenv("DRAMA_DRIVE_SMOKE_CONFIRM") != "UPLOAD_ONE_PRIVATE_TEST_MP4":
        raise TursoReceiptError("Drive upload manual confirmation required")
    if any(os.getenv(name) != "YES" for name in (
        "DRAMA_ENABLE_DRIVE_UPLOAD", "DRAMA_ENABLE_DRIVE_READ",
        "DRAMA_ENABLE_TURSO_METADATA_WRITE",
    )):
        raise TursoReceiptError("All Drive/Turso manual operation gates are required")
    if os.getenv("DRAMA_TURSO_WRITE_CONFIRM") != _MIRROR_CONFIRM:
        raise TursoReceiptError("Turso write approval missing")
    if not isinstance(target, TursoMetadataTarget) or target.engine != "libsql":
        raise TursoReceiptError("Only the dedicated libSQL database is approved for this canary")
    if parent_folder_id == "fakeDriveRoot0001" or not parent_folder_id:
        raise TursoReceiptError("A real app-created private Drive parent folder is required")
    _file_id(parent_folder_id)
    if not os.getenv("TURSO_AUTH_TOKEN") or not os.getenv("DRAMA_DRIVE_USER_OAUTH_JSON"):
        raise TursoReceiptError("Dedicated Turso and Drive credentials are required")


def run_turso_canary(
    output: Path, *, live: bool = False, parent_folder_id: str = "fakeDriveRoot0001",
    target: TursoMetadataTarget | None = None, drive_client=None, remote=None,
) -> dict:
    """Verify exactly one synthetic preview MP4 in Drive before mirroring a receipt.

    No write happens before the two Drive audit events and recovered-media hash
    and stream verification. Do not retry blindly: a failed remote write may
    have committed and the temporary SQLite ledger is not durable.
    """
    from drama_factory.storage.drive_canary import run_drive_canary

    close_remote = False
    if live:
        # Avoid allowing callers to mislabel injected Fake clients as real cloud.
        if drive_client is not None or remote is not None:
            raise TursoReceiptError("Live canary does not accept injected clients")
        _check_live_preconditions(parent_folder_id, target)
        # Check connectivity BEFORE creating any Drive object.
        remote = _open_remote(target, os.environ["TURSO_AUTH_TOKEN"])
        close_remote = True
    else:
        if target is not None and target != _FAKE_TARGET:
            raise TursoReceiptError("Offline canary only accepts the fixed Fake target")
        target = _FAKE_TARGET
        if remote is not None:
            raise TursoReceiptError("Offline canary creates its own in-memory SQL adapter")
        remote = sqlite3.connect(":memory:")
        close_remote = True

    mirrored = {}
    try:
        ping = remote.execute("SELECT 1").fetchone()
        if ping is None or int(ping[0]) != 1:
            raise TursoReceiptError("Dedicated Turso pre-upload SELECT ping failed")

        def on_verified(db, copy_id, recovered_root):
            nonlocal mirrored
            mirrored = mirror_verified_drive_receipt(
                db, copy_id, recovered_root, target,
                operator_approved=True, remote=remote,
            )

        if live:
            drive = run_drive_canary(
                output, parent_folder_id=parent_folder_id,
                live=True, on_verified=on_verified,
            )
        else:
            with _fake_turso_gates():
                drive = run_drive_canary(
                    output, parent_folder_id=parent_folder_id,
                    live=False, client=drive_client, on_verified=on_verified,
                )
        if not (
            drive["verified"] is True and drive["uploaded_mp4_count"] == 1
            and drive["sha256_before"] == drive["sha256_after"]
            and mirrored.get("mirrored") is True
            and mirrored.get("cached") is False
        ):
            raise TursoReceiptError("Single Drive MP4 and fresh Turso INSERT not confirmed")
        result = {
            "mode": "live" if live else "fake",
            "engine": target.engine,
            "dedicated_name_validated": True,
            "drive_round_trip_verified": True,
            "uploaded_mp4_count": 1,
            "sha256_match": True,
            "size_bytes": drive["size_bytes"],
            "turso_table": mirrored["table"],
            "turso_metadata_inserted": True,
            "turso_full_row_readback_verified": True,
            "database_modified": True,
            "remote_ids_redacted": True,
            "new_ai_model_generation_calls": 0,
            "production_sqlite_migrated": False,
        }
        root = Path(output).resolve()
        (root / "turso-canary-verification.json").write_text(
            json.dumps(result, sort_keys=True, indent=2), encoding="utf-8",
        )
        return result
    finally:
        if close_remote:
            remote.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="One manual verified Drive -> Turso receipt")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("artifacts/turso-write-canary"))
    args = parser.parse_args(argv)
    if args.live:
        raw = os.getenv("TURSO_DATABASE_URL")
        if not raw:
            raise TursoReceiptError("Dedicated Turso URL is missing")
        target = TursoMetadataTarget(url=raw, engine="libsql")
        parent = os.getenv("DRAMA_DRIVE_PARENT_FOLDER_ID", "")
        return run_turso_canary(args.out, live=True, parent_folder_id=parent, target=target)
    return run_turso_canary(args.out)


def run_cli(argv=None) -> int:
    """Sanitize all third-party SDK errors before they reach Actions logs."""
    try:
        result = main(argv)
    except Exception:
        print(
            "Single Drive-to-Turso canary failed (error details redacted). "
            "Inspect offline CI and confirm the approved database, Drive OAuth and "
            "explicit manual gates; do not blindly rerun after a partial write.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
