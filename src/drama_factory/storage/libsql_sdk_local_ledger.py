"""PR-31b2o0: EXPERIMENTAL native libSQL SDK ledger facade, LOCAL ONLY.

Only disposable marked SQLite test files are accepted. NEVER accepts
libsql:// URLs, remote credentials, production database files or a live
worker cutover. Connection and query protocols match the existing SQL
business functions; this does NOT certify remote concurrency, retries,
lost commit acknowledgement or production migrations.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from drama_factory.storage.ledger_backend_contract import LedgerBackend


_MARKER_TABLE = "pr31_native_libsql_local_test_marker"
_MARKER_VALUE = "pr31b2o0-isolated-test-schema-only"


class LocalSdkDenied(ValueError):
    pass


class NamedSdkRow(Mapping):
    """Read-only sqlite3.Row-like key OR ordinal access; duplicate names deny."""

    def __init__(self, column_names: tuple[str, ...], values: tuple):
        if len(column_names) != len(values):
            raise LocalSdkDenied("Cursor description/row width mismatch")
        if len(column_names) != len(set(column_names)):
            # Duplicate names in a join can silently pick the WRONG billing
            # column. Forbid until an explicit alias is supplied in SQL.
            raise LocalSdkDenied("Ambiguous duplicate column names")
        self._names = column_names
        self._values = values
        self._lookup = dict(zip(column_names, values))

    def __getitem__(self, key: Any):
        if type(key) is int:
            return self._values[key]
        if type(key) is str:
            return self._lookup[key]
        raise KeyError("A column name or integer ordinal is required")

    def __iter__(self) -> Iterator[str]:
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._names)


class NamedSdkCursor:
    def __init__(self, native_cursor):
        self._cursor = native_cursor
        desc = native_cursor.description
        self._names = tuple(item[0] for item in desc) if desc else ()

    def _convert(self, row):
        if row is None:
            return None
        return NamedSdkRow(self._names, tuple(row))

    def fetchone(self):
        return self._convert(self._cursor.fetchone())

    def fetchall(self):
        return [self._convert(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid


class _NativeConnection:
    def __init__(self, native):
        self._native = native

    def execute(self, sql: str, params: tuple = ()):
        return NamedSdkCursor(self._native.execute(sql, params))

    def commit(self):
        self._native.commit()

    def rollback(self):
        self._native.rollback()

    def close(self):
        self._native.close()


def tag_disposable_sdk_fixture(file: Path, *, offline_test_only: bool = False):
    """Allow tests to mark a disposable DB. Not a production setup function."""
    if offline_test_only is not True:
        raise LocalSdkDenied("Explicit offline test gate required")
    path = _path(file)
    if not path.is_file():
        raise LocalSdkDenied("Existing disposable local SQLite file required")
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            f"CREATE TABLE {_MARKER_TABLE} ("
            "value TEXT PRIMARY KEY "
            "CHECK(value='pr31b2o0-isolated-test-schema-only'))"
        )
        conn.execute(
            f"INSERT INTO {_MARKER_TABLE}(value) VALUES (?)", (_MARKER_VALUE,)
        )
        conn.commit()
    finally:
        conn.close()


def _path(value: Path) -> Path:
    raw = str(value)
    if "://" in raw or raw == ":memory:":
        raise LocalSdkDenied("Only disposable local SQLite files accepted")
    file = Path(value).expanduser().absolute()
    if file.is_symlink() or file.parent.is_symlink():
        raise LocalSdkDenied("No symlink source permitted")
    return file


class LocalNativeLibsqlLedger:
    """Native SDK backend experiment with a test fixture marker whitelist."""

    def __init__(self, source: Path, *, offline_test_only: bool = False):
        if offline_test_only is not True:
            raise LocalSdkDenied("Explicit offline SDK experiment required")
        path = _path(source)
        if not path.is_file():
            raise LocalSdkDenied("Existing initialized test SQLite file required")
        # Verify dedicated synthetic fixture marker READ-ONLY before allowing
        # SDK writes. The ordinary production database does not contain it.
        conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            conn.execute("PRAGMA query_only=ON")
            try:
                row = conn.execute(
                    f"SELECT value FROM {_MARKER_TABLE}"
                ).fetchone()
            except sqlite3.Error:
                raise LocalSdkDenied("Unmarked source: no SDK writes permitted") from None
            if row != (_MARKER_VALUE,):
                raise LocalSdkDenied("Wrong SDK-only fixture marker")
        finally:
            conn.close()
        self.path = path

    @contextmanager
    def connection(self):
        # Lazy import: normal offline CI and production code never need to
        # import/install SDK or touch a database endpoint.
        import libsql

        native = libsql.connect(database=str(self.path), timeout=15.0)
        conn = _NativeConnection(native)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            state = conn.execute("PRAGMA foreign_keys").fetchone()
            if state is None or state[0] != 1:
                raise LocalSdkDenied("Native SDK foreign-key enforcement not enabled")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        finally:
            conn.close()

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row is not None else None

    def many(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def exec(self, sql: str, params: tuple = ()) -> None:
        with self.connection() as conn:
            conn.execute(sql, params)

    def safety_metadata(self) -> dict:
        return {
            "backend": "native_libsql_sdk_local_test_only",
            "row_mapping_verified": True,
            "requires_disposable_marker": True,
            "remote_txlab_connection_attempts": 0,
            "remote_sql_semantics_verified": False,
            "remote_concurrency_verified": False,
            "network_commit_recovery_verified": False,
            "production_backend_switched": False,
            "live_cutover_permitted": False,
            "paid_provider_calls": 0,
        }
