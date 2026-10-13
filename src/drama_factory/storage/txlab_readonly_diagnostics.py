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
from drama_factory.storage.txlab_v2 import _TABLE as _TABLE_V2
from drama_factory.storage.txlab_multitable_v3_live import _NAMES as _V3_NAMES

_CONFIRM = "CHECK_ISOLATED_TXLAB_READ_ONLY"
_STAGES = frozenset((
    "target_validation", "connect", "select_ping", "select_schema",
    "select_counter_summary", "select_v2_schema", "select_v2_counter_summary",
    "select_v3_schema", "select_v3_reservation", "select_v3_job",
    "select_v3_budget_event",
))


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
        # The first real v2 run failed at worker_read/busy after earlier
        # commits may have succeeded. Inspect its DIFFERENT table without
        # reading probe IDs/markers or changing any existing v1 records.
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
                (_TABLE_V2,),
            ).fetchone()
            if row is None or int(row[0]) not in (0, 1):
                raise ValueError("unexpected v2 catalogue response")
            v2_exists = bool(int(row[0]))
        except Exception:
            raise ReadOnlyTxLabFailure("select_v2_schema") from None
        v2_counts = None
        if v2_exists:
            try:
                row = conn.execute(
                    f"SELECT COUNT(*), "
                    f"COALESCE(SUM(CASE WHEN counter=0 THEN 1 ELSE 0 END),0), "
                    f"COALESCE(SUM(CASE WHEN counter=1 THEN 1 ELSE 0 END),0), "
                    f"COALESCE(SUM(CASE WHEN counter=2 THEN 1 ELSE 0 END),0), "
                    f"COALESCE(SUM(CASE WHEN counter=3 THEN 1 ELSE 0 END),0), "
                    f"COALESCE(SUM(CASE WHEN counter=4 THEN 1 ELSE 0 END),0), "
                    f"COALESCE(SUM(CASE WHEN counter NOT IN (0,1,2,3,4) THEN 1 ELSE 0 END),0) "
                    f"FROM {_TABLE_V2}"
                ).fetchone()
                if row is None or len(row) != 7:
                    raise ValueError("invalid v2 aggregate result")
                values = [int(value) for value in row]
                if any(x < 0 for x in values) or values[0] != sum(values[1:]):
                    raise ValueError("inconsistent v2 aggregate result")
                v2_counts = {
                    "total_probe_rows": values[0],
                    "counter_zero_rows": values[1],
                    "counter_one_rows": values[2],
                    "counter_two_rows": values[3],
                    "counter_three_rows": values[4],
                    "counter_four_rows": values[5],
                    "counter_other_rows": values[6],
                }
            except Exception:
                raise ReadOnlyTxLabFailure("select_v2_counter_summary") from None
        # PR-31b2l2: proactively inspect v3 after a future DDL/COMMIT
        # ambiguity, WITHOUT trying to repair or replay any write. Counting
        # ALL prefixed catalog objects detects a partially installed schema.
        try:
            objects = conn.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE 'pr31_v3_%'"
            ).fetchall()
            names = {row[0] for row in objects}
            if len(names) != len(objects):
                raise ValueError("duplicate v3 catalogue names")
            v3_complete = names == _V3_NAMES
            v3_count = len(names)
        except Exception:
            raise ReadOnlyTxLabFailure("select_v3_schema") from None

        v3_reservation = None
        if "pr31_v3_reservation" in names:
            try:
                row = conn.execute(
                    "SELECT COUNT(*), "
                    "COALESCE(SUM(CASE WHEN status='held' THEN 1 ELSE 0 END),0), "
                    "COALESCE(SUM(CASE WHEN status='reconciled' THEN 1 ELSE 0 END),0), "
                    "COALESCE(SUM(CASE WHEN actual_cents=45 THEN 1 ELSE 0 END),0), "
                    "COALESCE(SUM(CASE WHEN actual_cents IS NULL THEN 1 ELSE 0 END),0) "
                    "FROM pr31_v3_reservation"
                ).fetchone()
                if row is None or len(row) != 5:
                    raise ValueError("bad synthetic reservation aggregates")
                values = [int(value) for value in row]
                if any(value < 0 for value in values):
                    raise ValueError("negative aggregate")
                v3_reservation = {
                    "total": values[0],
                    "held": values[1],
                    "reconciled": values[2],
                    "charge_45_cents": values[3],
                    "charge_null": values[4],
                }
            except Exception:
                raise ReadOnlyTxLabFailure("select_v3_reservation") from None

        v3_job = None
        if "pr31_v3_job" in names:
            try:
                row = conn.execute(
                    "SELECT COUNT(*), "
                    "COALESCE(SUM(CASE WHEN actual_charge_cents=45 THEN 1 ELSE 0 END),0), "
                    "COALESCE(SUM(CASE WHEN actual_charge_cents IS NULL THEN 1 ELSE 0 END),0), "
                    "COALESCE(SUM(CASE WHEN generation_intent_recorded=1 THEN 1 ELSE 0 END),0) "
                    "FROM pr31_v3_job"
                ).fetchone()
                if row is None or len(row) != 4:
                    raise ValueError("bad synthetic job aggregates")
                values = [int(value) for value in row]
                if any(value < 0 for value in values):
                    raise ValueError("negative aggregate")
                v3_job = {
                    "total": values[0],
                    "charge_45_cents": values[1],
                    "charge_null": values[2],
                    "intent_recorded": values[3],
                }
            except Exception:
                raise ReadOnlyTxLabFailure("select_v3_job") from None

        v3_audit = None
        if "pr31_v3_budget_event" in names:
            try:
                row = conn.execute(
                    "SELECT COUNT(*), "
                    "COALESCE(SUM(CASE WHEN action='held' THEN 1 ELSE 0 END),0), "
                    "COALESCE(SUM(CASE WHEN action='reconciled' THEN 1 ELSE 0 END),0) "
                    "FROM pr31_v3_budget_event"
                ).fetchone()
                if row is None or len(row) != 3:
                    raise ValueError("bad synthetic audit aggregates")
                values = [int(value) for value in row]
                if any(value < 0 for value in values):
                    raise ValueError("negative aggregate")
                v3_audit = {
                    "total": values[0],
                    "held": values[1],
                    "reconciled": values[2],
                }
            except Exception:
                raise ReadOnlyTxLabFailure("select_v3_budget_event") from None

        return {
            "mode": "isolated_txlab_select_only_diagnostics",
            "engine": "libsql",
            "strict_txlab_url_validated": True,
            "connection_ping_succeeded": True,
            "test_table_exists": exists,
            "aggregate_test_row_counts": counts,
            "v2_test_table_exists": v2_exists,
            "v2_aggregate_test_row_counts": v2_counts,
            "v3_schema_objects_present": v3_count,
            "v3_schema_names_complete": v3_complete,
            "v3_reservation_aggregate": v3_reservation,
            "v3_job_aggregate": v3_job,
            "v3_budget_event_aggregate": v3_audit,
            "v3_remote_transaction_semantics_verified": False,
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
