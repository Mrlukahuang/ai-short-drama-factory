"""Explicit read-only connectivity preflight for a dedicated short-drama Turso DB.

This performs no DDL, writes, user-content reads, model invocations or Drive API
calls. It must NEVER accept the shared Turso database belonging to other apps.
"""
from __future__ import annotations

import argparse
import json
import os
from contextlib import suppress

from drama_factory.storage.turso_receipts import (
    TursoMetadataTarget, TursoReceiptError, _open_remote,
)


def check_dedicated_turso(
    target: TursoMetadataTarget, *,
    operator_approved: bool = False, remote=None,
) -> dict:
    """SELECT-only check; output is safe to attach to private Actions run."""
    if (
        operator_approved is not True
        or os.getenv("DRAMA_TURSO_READ_CONFIRM") != "CHECK_DEDICATED_DRAMA_DB"
    ):
        raise TursoReceiptError("Explicit read-only Turso check confirmation required")
    if not isinstance(target, TursoMetadataTarget):
        raise TursoReceiptError("Explicit validated target required")
    created = False
    if remote is None:
        token = os.getenv("TURSO_AUTH_TOKEN")
        if not token:
            raise TursoReceiptError("Turso token missing")
        remote = _open_remote(target, token)
        created = True
    try:
        ping = remote.execute("SELECT 1").fetchone()
        if ping is None or int(ping[0]) != 1:
            raise TursoReceiptError("Turso read-only ping failed")
        # Exact-name match only; never enumerate or return user's other tables.
        existing = remote.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            ("drama_drive_receipts_v1",),
        ).fetchone()
        return {
            "reachable": True,
            "engine": target.engine,
            "dedicated_name_validated": True,
            "metadata_table_exists": existing is not None,
            "read_only": True,
            "database_modified": False,
            "google_drive_operations": 0,
            "new_ai_model_generation_calls": 0,
        }
    finally:
        if created:
            with suppress(Exception):
                remote.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only short-drama Turso check")
    parser.add_argument("--engine", required=True, choices=("libsql","turso"))
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        raise TursoReceiptError("Explicit --live required (there is no automatic Turso check)")
    raw = os.getenv("TURSO_DATABASE_URL")
    if not raw:
        raise TursoReceiptError("Dedicated database URL missing")
    target = TursoMetadataTarget(url=raw, engine=args.engine)
    result = check_dedicated_turso(target, operator_approved=True)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
