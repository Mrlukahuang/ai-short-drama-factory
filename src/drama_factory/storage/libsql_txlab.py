"""PR-31b2a: opt-in transactions on a SEPARATE, disposable Turso libSQL lab.

Never connect to the established ai-short-drama-factory production metadata DB.
The lab has a different strictly validated database name and separate GitHub
Secrets. No production SQLite rows or provider requests are transferred.

Offline CI injects independent sqlite3 test connections. Real cloud execution
is blocked by manual workflow confirmation and new lab-scoped credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
from uuid import uuid4


_HOST = re.compile(
    r"ai-short-drama-factory-txlab-[a-z0-9]+(?:-[a-z0-9]+)*"
    r"(?:\.[a-z0-9]+(?:-[a-z0-9]+)*)?\.turso\.io"
)
_CONFIRM = "RUN_ISOLATED_LIBSQL_TRANSACTION_CANARY"
_TABLE = "pr31_txlab_transaction_probe_v1"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS pr31_txlab_transaction_probe_v1 (
 probe_id TEXT PRIMARY KEY,
 counter INTEGER NOT NULL CHECK(counter>=0),
 marker TEXT NOT NULL UNIQUE
)
"""


class TxLabDenied(ValueError):
    pass


_STAGES = frozenset({
    "open_master", "create_schema", "insert_probe", "rollback_begin",
    "rollback_update", "rollback_check", "worker_connect", "worker_begin",
    "worker_read", "worker_update", "worker_commit", "worker_result",
    "final_read", "unique_begin", "unique_insert", "unique_commit",
    "unique_verify",
})
_CATEGORIES = frozenset({"busy", "timeout", "connection", "constraint", "unknown"})


def _safe_error_category(exc: BaseException) -> str:
    """Classify only into fixed labels: never expose a raw SDK message."""
    message = str(exc).lower()
    if any(word in message for word in ("sqlite_busy", "database is locked", "database busy", "busy snapshot")):
        return "busy"
    if any(word in message for word in ("timed out", "timeout", "deadline exceeded")):
        return "timeout"
    if any(word in message for word in ("connection refused", "connection closed", "connection reset", "network error", "transport error", "broken pipe")):
        return "connection"
    if isinstance(exc, sqlite3.IntegrityError) or "unique constraint failed" in message:
        return "constraint"
    return "unknown"


class TxLabStageError(TxLabDenied):
    """Safe fixed-label error after a possibly committed TxLab mutation."""

    def __init__(self, stage: str, category: str):
        self.stage = stage if stage in _STAGES else "worker_result"
        self.category = category if category in _CATEGORIES else "unknown"
        super().__init__(
            f"stage={self.stage} category={self.category}; "
            "commit state may be partial (details redacted)"
        )


def validate_lab_url(url: str) -> str:
    """Reject existing short-drama DB URL, credentials, paths and HTTP schemes."""
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "libsql"
            or not parsed.hostname or not _HOST.fullmatch(parsed.hostname)
            or parsed.path not in ("", "/") or parsed.username or parsed.password
            or parsed.port is not None or parsed.query or parsed.fragment
        ):
            raise TxLabDenied("Only isolated ai-short-drama-factory-txlab libSQL is allowed")
    except (ValueError, TypeError) as exc:
        raise TxLabDenied("Invalid isolated lab URL") from exc
    return url


def _close_quietly(conn):
    try:
        conn.close()
    except Exception:
        pass


def _rollback_quietly(conn):
    try:
        conn.rollback()
    except Exception:
        pass


def _open_lab_connection(url: str, token: str):
    # Only evaluated after strict live gates; offline CI never imports libsql.
    import libsql
    return libsql.connect(database=url, auth_token=token)


def run_transaction_contract(conn_factory, *, mode: str) -> dict:
    """One bounded row in a dedicated test table, two competing connections.

    Rollback is tested before concurrency. If an operation fails after an
    earlier commit, don't retry automatically; inspect lab state manually.
    """
    if mode not in ("offline_fake", "isolated_live"):
        raise TxLabDenied("Invalid transaction test mode")
    probe = "txlab_" + uuid4().hex
    tag = "isolated_" + uuid4().hex
    stage = "open_master"
    master = None
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

        # An explicit write followed by rollback must not persist.
        stage = "rollback_begin"
        master.execute("BEGIN IMMEDIATE")
        try:
            stage = "rollback_update"
            master.execute(
                f"UPDATE {_TABLE} SET counter=counter+5 WHERE probe_id=?",
                (probe,),
            )
        finally:
            master.rollback()
        stage = "rollback_check"
        after_rollback = master.execute(
            f"SELECT counter FROM {_TABLE} WHERE probe_id=?", (probe,)
        ).fetchone()
        if after_rollback is None or int(after_rollback[0]) != 0:
            raise TxLabDenied("Transaction rollback persisted unintended changes")

        def increment():
            # Each simulated/remote Worker owns a separate connection. This
            # tests server-side serialization, not Python's threading lock.
            # Never retry a remote write with an ambiguous commit result.
            worker_stage = "worker_connect"
            conn = None
            try:
                conn = conn_factory()
                worker_stage = "worker_begin"
                conn.execute("BEGIN IMMEDIATE")
                worker_stage = "worker_read"
                before = conn.execute(
                    f"SELECT counter FROM {_TABLE} WHERE probe_id=?", (probe,)
                ).fetchone()
                if before is None:
                    raise TxLabDenied("Lab row disappeared")
                worker_stage = "worker_update"
                conn.execute(
                    f"UPDATE {_TABLE} SET counter=? WHERE probe_id=?",
                    (int(before[0]) + 1, probe),
                )
                worker_stage = "worker_commit"
                conn.commit()
            except BaseException as exc:
                _rollback_quietly(conn)
                raise TxLabStageError(worker_stage, _safe_error_category(exc)) from None
            finally:
                _close_quietly(conn)

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(increment)
            fut_b = pool.submit(increment)
            # Always await both, even if the first fails, to avoid leaving
            # a background live write when the CLI considers itself done.
            failures = []
            for fut in (fut_a, fut_b):
                try:
                    fut.result(timeout=30)
                except BaseException as exc:
                    failures.append(exc)
            if failures:
                # Prefer an actual worker's sanitized stage over generic
                # timeout. Both futures have been joined by the context.
                for exc in failures:
                    if isinstance(exc, TxLabStageError):
                        raise exc
                raise TxLabStageError("worker_result", _safe_error_category(failures[0]))

        stage = "final_read"
        final = master.execute(
            f"SELECT counter,marker FROM {_TABLE} WHERE probe_id=?", (probe,)
        ).fetchone()
        if final is None or int(final[0]) != 2 or final[1] != tag:
            raise TxLabDenied("Concurrent transactions lost update or changed marker")

        # SQLite primary key enforcement must reject a duplicate attempt.
        constraint_rejected = False
        try:
            stage = "unique_begin"
            master.execute("BEGIN IMMEDIATE")
            stage = "unique_insert"
            master.execute(
                f"INSERT INTO {_TABLE}(probe_id,counter,marker) VALUES (?,?,?)",
                (probe, 99, "duplicate_" + uuid4().hex),
            )
            stage = "unique_commit"
            master.commit()
        except Exception as exc:
            # A dropped connection, timeout or SDK failure is NOT evidence
            # of a real primary-key constraint. Reject unrelated errors.
            message = str(exc).lower()
            constraint_rejected = (
                isinstance(exc, sqlite3.IntegrityError)
                or "unique constraint failed" in message
                or "primary key" in message
            )
            _rollback_quietly(master)
            if not constraint_rejected:
                raise TxLabStageError(stage, _safe_error_category(exc)) from None
        if not constraint_rejected:
            raise TxLabDenied("Primary key uniqueness was not enforced")
        stage = "unique_verify"
        stable = master.execute(
            f"SELECT counter FROM {_TABLE} WHERE probe_id=?", (probe,)
        ).fetchone()
        if stable is None or int(stable[0]) != 2:
            raise TxLabDenied("Uniqueness conflict altered committed lab counter")
        return {
            "mode": mode,
            "engine": "libsql" if mode == "isolated_live" else "sqlite_fake",
            "isolated_txlab_name_validated": mode == "isolated_live",
            "dedicated_test_row_inserted": True,
            "explicit_rollback_verified": True,
            "two_independent_connection_increments": True,
            "no_lost_update": True,
            "primary_key_duplicate_rejected": True,
            "table": _TABLE,
            "probe_ids_redacted": True,
            "production_database_touched": False,
            "production_backend_switched": False,
            "production_schema_migrated": False,
            "live_cutover_permitted": False,
            "new_ai_model_generation_calls": 0,
        }
    except TxLabStageError:
        raise
    except BaseException as exc:
        # From the first connection onward, DB writes may have committed.
        raise TxLabStageError(stage, _safe_error_category(exc)) from None
    finally:
        _close_quietly(master)


def run_live_txlab(*, url: str, token: str, operator_approved: bool = False) -> dict:
    if (
        operator_approved is not True
        or os.getenv("DRAMA_TXLAB_CONFIRM") != _CONFIRM
        or os.getenv("DRAMA_ENABLE_TXLAB_WRITE") != "YES"
    ):
        raise TxLabDenied("Separate manual isolated libSQL test approval required")
    validate_lab_url(url)
    if not token:
        raise TxLabDenied("Dedicated isolated test token required")
    return run_transaction_contract(
        lambda: _open_lab_connection(url, token), mode="isolated_live",
    )


def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Manual isolated libSQL transaction test only")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        print("A separately authorized live lab is required (details redacted)",
              file=sys.stderr)
        return 1
    try:
        result = run_live_txlab(
            url=os.environ.get("DRAMA_TXLAB_DATABASE_URL", ""),
            token=os.environ.get("DRAMA_TXLAB_AUTH_TOKEN", ""),
            operator_approved=True,
        )
    except TxLabStageError as exc:
        print(
            f"Isolated lab transaction failed stage={exc.stage} "
            f"category={exc.category} (details redacted). "
            "Do not rerun without reviewing whether a test row committed.",
            file=sys.stderr,
        )
        return 1
    except Exception:
        print(
            "Isolated lab transaction check failed (details redacted). "
            "Do not rerun without reviewing whether a test row committed.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
