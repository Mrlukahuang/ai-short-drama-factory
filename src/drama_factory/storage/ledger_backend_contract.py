"""PR-31b1: an *offline-only* transactional ledger backend seam.

Production still constructs drama_factory.db.Database directly. This module
cannot connect to Turso or run the Worker against a remote database. It proves
only that the existing job/budget functions can be exercised through a
separately constructed backend satisfying the explicit connection contract.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, ContextManager, Protocol, runtime_checkable


@runtime_checkable
class TransactionConnection(Protocol):
    """SQLite-shaped transaction handle; no implicit BEGIN semantics."""
    def execute(self, sql: str, params: tuple = ()) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


@runtime_checkable
class LedgerBackend(Protocol):
    """The subset of Database consumed by present job/budget algorithms."""

    def connection(self) -> ContextManager[TransactionConnection]: ...
    def one(self, sql: str, params: tuple = ()) -> dict | None: ...
    def many(self, sql: str, params: tuple = ()) -> list[dict]: ...
    def exec(self, sql: str, params: tuple = ()) -> None: ...


class OfflineAdapterDenied(ValueError):
    pass


class OfflineSqliteLedger:
    """Isolated secondary adapter over an *existing* local SQLite test file.

    This class NEVER calls Database(), initializes schema, or accepts a URL.
    A future remote backend must be a new implementation with a separate
    explicit authorization and transaction validation phase, NOT an alias
    of this local sqlite3 adapter.
    """

    def __init__(self, source: Path, *, offline_test_only: bool = False):
        if offline_test_only is not True:
            raise OfflineAdapterDenied("Explicit offline adapter approval required")
        raw = str(source)
        if "://" in raw or raw == ":memory:":
            raise OfflineAdapterDenied("Offline adapter only accepts existing local SQLite files")
        path = Path(source)
        if not path.is_file():
            raise OfflineAdapterDenied("Existing, initialized local SQLite file required")
        self._path = path.absolute()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self._path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        with self.connection() as db:
            row = db.execute(sql, params).fetchone()
            return dict(row) if row else None

    def many(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute(sql, params).fetchall()]

    def exec(self, sql: str, params: tuple = ()) -> None:
        with self.connection() as db:
            db.execute(sql, params)


def require_ledger_contract(backend: LedgerBackend) -> LedgerBackend:
    """Fail-closed structural check; DOES NOT certify remote SQL semantics."""
    if not isinstance(backend, LedgerBackend):
        raise OfflineAdapterDenied("Ledger connection/one/many/exec contract missing")
    return backend


def export_offline_contract_metadata() -> dict:
    """A static machine-readable checklist; never claims Turso certification."""
    return {
        "contract": "pr31b1-ledger-transaction-v1",
        "validated_backend": "local_sqlite_only",
        "required_primitives": [
            "independent_connections",
            "explicit_begin_immediate",
            "commit_or_rollback",
            "foreign_keys_enforced",
            "row_mapping",
            "unique_idempotency_and_provider_ids",
            "event_write_atomic_with_state",
            "budget_hold_atomic_with_policy_read",
        ],
        "remote_sql_transaction_verified": False,
        "remote_concurrency_verified": False,
        "production_backend_switched": False,
        "live_migration_authorized": False,
        "turso_connections": 0,
        "paid_model_calls": 0,
    }
