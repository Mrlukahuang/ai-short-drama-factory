"""PR-31b2e: safer, second-generation isolated libSQL transaction experiment.

Offline CI uses disposable sqlite3 connections; the manual GitHub Actions
workflow is deliberately disabled until a NEW, specific cloud-write approval.
Old TxLab probes and the real short-drama metadata database are untouched.

This tests independently committed updates and reports lock contention as a
separate outcome, not as a lost committed update. It never retries any SQL.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from drama_factory.storage.libsql_txlab import (
    TxLabStageError, _close_quietly, _open_lab_connection,
    _rollback_quietly, _safe_error_category, validate_lab_url,
)

_TABLE = "pr31_txlab_v2_probe_v1"
_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS pr31_txlab_v2_probe_v1 ("
    "probe_id TEXT PRIMARY KEY, counter INTEGER NOT NULL CHECK(counter>=0), "
    "marker TEXT NOT NULL UNIQUE)"
)
_CONFIRM = "RUN_ISOLATED_TXLAB_V2_ONE_TIME"


def _stage_failure(stage: str, exc: BaseException) -> TxLabStageError:
    # The v1 sanitizer deliberately limits labels and never serializes
    # third-party exception messages, DB identifiers or token values.
    return TxLabStageError(stage, _safe_error_category(exc))


def _step(conn_factory, probe: str, *, gate=None, allow_busy: bool = False) -> str:
    conn = None
    stage = "worker_connect"
    try:
        conn = conn_factory()
        if gate is not None:
            gate.wait(timeout=12)
        stage = "worker_begin"
        try:
            conn.execute("BEGIN IMMEDIATE")
        except Exception as exc:
            # Only known SQLITE_BUSY at BEGIN is a *measured conflict*, not
            # a successful increment, retry instruction or lost-update proof.
            if allow_busy and _safe_error_category(exc) == "busy":
                _rollback_quietly(conn)
                return "busy_at_begin"
            raise
        stage = "worker_read"
        row = conn.execute(
            f"SELECT counter FROM {_TABLE} WHERE probe_id=?", (probe,)
        ).fetchone()
        if row is None:
            raise ValueError("missing synthetic probe")
        stage = "worker_update"
        conn.execute(
            f"UPDATE {_TABLE} SET counter=? WHERE probe_id=?",
            (int(row[0]) + 1, probe),
        )
        stage = "worker_commit"
        conn.commit()
        return "committed"
    except Exception as exc:
        _rollback_quietly(conn)
        raise _stage_failure(stage, exc) from None
    finally:
        if conn is not None:
            _close_quietly(conn)


def run_txlab_v2_contract(conn_factory, *, mode: str) -> dict:
    """One new synthetic row, rollback, two sequential and two racing writes.

    This routine cannot prove distributed transaction isolation or provide
    production authorization. All write-capable adapters are supplied by the
    caller; no SDK loaded by import.
    """
    if mode not in ("offline_fake", "isolated_live"):
        raise ValueError("Invalid TxLab v2 mode")
    probe = "txlabv2_" + uuid4().hex
    tag = "isolatedv2_" + uuid4().hex
    master = None
    stage = "open_master"
    try:
        master = conn_factory()
        stage = "create_schema"
        master.execute(_SCHEMA)
        stage = "insert_probe"
        master.execute(
            f"INSERT INTO {_TABLE}(probe_id,counter,marker) VALUES (?,?,?)",
            (probe, 0, tag),
        )
        master.commit()

        stage = "rollback_begin"
        master.execute("BEGIN IMMEDIATE")
        try:
            stage = "rollback_update"
            master.execute(
                f"UPDATE {_TABLE} SET counter=counter+7 WHERE probe_id=?",
                (probe,),
            )
        finally:
            master.rollback()
        stage = "rollback_check"
        rollback_row = master.execute(
            f"SELECT counter FROM {_TABLE} WHERE probe_id=?", (probe,)
        ).fetchone()
        if rollback_row is None or int(rollback_row[0]) != 0:
            raise ValueError("Rollback did not preserve zero counter")

        # Establish a simple independent-connection serial baseline.
        for _ in range(2):
            result = _step(conn_factory, probe)
            if result != "committed":
                raise ValueError("Serial worker failed to commit")
        stage = "serial_readback"
        serial_row = master.execute(
            f"SELECT counter FROM {_TABLE} WHERE probe_id=?", (probe,)
        ).fetchone()
        if serial_row is None or int(serial_row[0]) != 2:
            raise ValueError("Sequential committed increments not preserved")

        # Two independently established DB connections race. SQLITE_BUSY at
        # BEGIN is a measured/expected *rejection*, never silently counted as
        # a success. Commit errors fail the entire test (ambiguous side effect).
        gate = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (
                pool.submit(_step, conn_factory, probe, gate=gate, allow_busy=True),
                pool.submit(_step, conn_factory, probe, gate=gate, allow_busy=True),
            )
            results = []
            failures = []
            for fut in futures:
                try:
                    results.append(fut.result(timeout=30))
                except Exception as exc:
                    failures.append(exc)
            if failures:
                for exc in failures:
                    if isinstance(exc, TxLabStageError):
                        raise exc
                raise _stage_failure("worker_result", failures[0])
        committed = results.count("committed")
        rejected = results.count("busy_at_begin")
        if committed + rejected != 2:
            raise ValueError("Unexpected concurrent worker outcome")
        stage = "final_read"
        last = master.execute(
            f"SELECT counter,marker FROM {_TABLE} WHERE probe_id=?", (probe,)
        ).fetchone()
        if last is None or int(last[0]) != 2 + committed or last[1] != tag:
            raise ValueError("Committed concurrency outcome not reflected in DB")

        # Unique constraint check must distinguish constraint error from
        # network/timeout; a lost response is NOT evidence of a constraint.
        stage = "unique_begin"
        master.execute("BEGIN IMMEDIATE")
        stage = "unique_insert"
        try:
            master.execute(
                f"INSERT INTO {_TABLE}(probe_id,counter,marker) VALUES (?,?,?)",
                (probe, 99, "duplicatev2_" + uuid4().hex),
            )
        except Exception as exc:
            category = _safe_error_category(exc)
            _rollback_quietly(master)
            if category != "constraint":
                raise _stage_failure("unique_insert", exc) from None
        else:
            # Do not persist a disallowed duplicate, even if DB misbehaves.
            _rollback_quietly(master)
            raise ValueError("Duplicate primary key unexpectedly accepted")
        stage = "unique_verify"
        checked = master.execute(
            f"SELECT counter FROM {_TABLE} WHERE probe_id=?", (probe,)
        ).fetchone()
        if checked is None or int(checked[0]) != 2 + committed:
            raise ValueError("Uniqueness attempt altered committed value")

        return {
            "mode": mode,
            "engine": "libsql" if mode == "isolated_live" else "sqlite_fake",
            "only_separate_txlab": mode == "isolated_live",
            "table": _TABLE,
            "single_new_probe_row_committed": True,
            "explicit_rollback_verified": True,
            "sequential_independent_commits": 2,
            "parallel_workers_attempted": 2,
            "parallel_commits_observed": committed,
            "parallel_begin_busy_observed": rejected,
            "all_confirmed_commits_in_readback": True,
            "primary_key_duplicate_rejected": True,
            "remote_distributed_concurrency_certified": False,
            "any_automatic_write_retries": False,
            "probe_ids_redacted": True,
            "production_database_touched": False,
            "production_backend_switched": False,
            "live_cutover_permitted": False,
            "new_ai_model_generation_calls": 0,
        }
    except TxLabStageError:
        raise
    except Exception as exc:
        raise _stage_failure(stage, exc) from None
    finally:
        if master is not None:
            _close_quietly(master)


def run_live_txlab_v2(*, url: str, token: str, operator_approved: bool = False) -> dict:
    if (
        operator_approved is not True
        or os.getenv("DRAMA_TXLAB_V2_CONFIRM") != _CONFIRM
        or os.getenv("DRAMA_ENABLE_TXLAB_V2_WRITE") != "YES"
    ):
        raise ValueError("Separate one-use lab-v2 approval required")
    validate_lab_url(url)
    if not token:
        raise ValueError("New TxLab-v2 requires dedicated token")
    return run_txlab_v2_contract(
        lambda: _open_lab_connection(url, token), mode="isolated_live"
    )


def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="TxLab v2 isolated experiment, requires fresh authorization"
    )
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        print("TxLab v2 requires separately authorized manual invocation", file=sys.stderr)
        return 1
    try:
        output = run_live_txlab_v2(
            url=os.getenv("DRAMA_TXLAB_DATABASE_URL", ""),
            token=os.getenv("DRAMA_TXLAB_AUTH_TOKEN", ""),
            operator_approved=True,
        )
    except TxLabStageError as exc:
        print(
            f"TxLab v2 stopped at stage={exc.stage} category={exc.category}. "
            "Previous SQL may have committed; do not rerun (details redacted).",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print("TxLab v2 denied/failed (details redacted); do not rerun", file=sys.stderr)
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
