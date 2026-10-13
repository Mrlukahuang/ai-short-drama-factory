"""SELECT-only TxLab diagnostics after an ambiguous manual transaction failure.

NEVER retry the transaction canary here, perform DDL/DML, inspect main drama
database, or output row identifiers, tokens or the database URL. The new
disposable TxLab may already contain a partially written test row.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from drama_factory.storage.libsql_txlab import (
    _TABLE, _close_quietly, _open_lab_connection, validate_lab_url,
)

_CONFIRM = "CHECK_ISOLATED_TXLAB_READ_ONLY"
_STAGES = frozenset(("target_validation", "connect", "select_ping", "select_schema", "select_counter_summary"))


class ReadOnlyTxLabFailure(ValueError):
    """Only fixed stage labels, never raw third-party errors."""

    def __init__(self, stage: str):
        super().__init__(stage if stage in _STAGES else "target_validation")
        self.stage = stage if stage in _STAGES else "target_validation"


def inspect_txlab_readonly(
    url: str,
    token: str,
    *,
    operator_approved: bool = False,
    connection_factory=None,
) -> dict:
    if (
        operator_approved is not True
        or os.getenv("DRAMA_TXLAB_READONLY_CONFIRM") != _CONFIRM
    ):
        raise ReadOnlyTxLabFailure("target_validation")
    try:
        validate_lab_url(url)
    except Exception:
        raise ReadOnlyTxLabFailure("target_validation") from None
    if not token:
        raise ReadOnlyTxLabFailure("target_validation")

    # Connection-factory injection is test-only, never read from user input.
    factory = connection_factory or _open_lab_connection
    try:
        conn = factory(url, token)
    except Exception:
        raise ReadOnlyTxLabFailure("connect") from None
    try:
        try:
            row = conn.execute("SELECT 1").fetchone()
            if row is None or int(row[0]) != 1:
                raise ValueError("ping mismatch")
        except Exception:
            raise ReadOnlyTxLabFailure("select_ping") from None
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                (_TABLE,),
            ).fetchone()
            if row is None or int(row[0]) not in (0, 1):
                raise ValueError("unexpected catalog response")
            exists = bool(int(row[0]))
        except Exception:
            raise ReadOnlyTxLabFailure("select_schema") from None

        counts = None
        if exists:
            try:
                # Fixed, code-owned SQL; no table or column names from user input.
                # Only aggregates, never SELECT any IDs or marker values.
                row = conn.execute(
                    f"SELECT COUNT(*), "
                    f"COALESCE(SUM(CASE WHEN counter=0 THEN 1 ELSE 0 END),0), "
                    f"COALESCE(SUM(CASE WHEN counter=1 THEN 1 ELSE 0 END),0), "
                    f"COALESCE(SUM(CASE WHEN counter=2 THEN 1 ELSE 0 END),0), "
                    f"COALESCE(SUM(CASE WHEN counter NOT IN (0,1,2) THEN 1 ELSE 0 END),0) "
                    f"FROM {_TABLE}"
                ).fetchone()
                if row is None or len(row) != 5:
                    raise ValueError("invalid aggregate result")
                values = [int(item) for item in row]
                if any(x < 0 for x in values) or values[0] != sum(values[1:]):
                    raise ValueError("inconsistent aggregate result")
                counts = {
                    "total_probe_rows": values[0],
                    "counter_zero_rows": values[1],
                    "counter_one_rows": values[2],
                    "counter_two_rows": values[3],
                    "counter_other_rows": values[4],
                }
            except Exception:
                raise ReadOnlyTxLabFailure("select_counter_summary") from None
        return {
            "mode": "isolated_txlab_select_only_diagnostics",
            "engine": "libsql",
            "strict_txlab_url_validated": True,
            "connection_ping_succeeded": True,
            "test_table_exists": exists,
            "aggregate_test_row_counts": counts,
            "read_only_operations": True,
            "database_modified_by_this_check": False,
            "previous_canary_commit_state_fully_known": False,
            "production_database_touched": False,
            "production_backend_switched": False,
            "new_ai_model_generation_calls": 0,
        }
    finally:
        _close_quietly(conn)


def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only diagnostics for a dedicated failed TxLab run"
    )
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        print("Isolated read-only TxLab diagnostics require manual live invocation",
              file=sys.stderr)
        return 1
    try:
        result = inspect_txlab_readonly(
            url=os.environ.get("DRAMA_TXLAB_DATABASE_URL", ""),
            token=os.environ.get("DRAMA_TXLAB_AUTH_TOKEN", ""),
            operator_approved=True,
        )
    except ReadOnlyTxLabFailure as exc:
        print(
            f"TxLab read-only diagnostic stopped at stage={exc.stage} "
            "(details redacted; no DDL/DML performed)",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print("TxLab read-only diagnostic failed (details redacted; no DDL/DML performed)",
              file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
