"""Offline single-statement conditional mutation contract; no Turso writes."""
from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from drama_factory.db import Database
from drama_factory.storage.txlab_atomic_candidate import (
    OfflineAtomicCounter, OfflineAtomicDenied, create_offline_atomic_fixture,
)
from drama_factory.storage.txlab_retry_policy import assess_txlab_retry


def new_counter(tmp_path, max_count):
    source = create_offline_atomic_fixture(
        tmp_path / "single-statement-test-only.sqlite",
        max_count=max_count, isolated_test_only=True,
    )
    return OfflineAtomicCounter(source, isolated_test_only=True)


def test_true_parallel_single_sql_claim_never_exceeds_capacity(tmp_path):
    counter = new_counter(tmp_path, 5)
    gate = Barrier(16)

    def work(_):
        gate.wait(timeout=20)
        return counter.claim_once()

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(work, range(16)))

    successful = sorted(value for value in results if value is not None)
    assert successful == [1, 2, 3, 4, 5]
    assert results.count(None) == 11
    assert counter.claim_once() is None
    receipt = counter.status()
    assert receipt["counter"] == receipt["capacity"] == 5
    assert receipt["remote_concurrency_verified"] is False
    assert receipt["multi_scope_budget_transaction_verified"] is False
    assert receipt["production_backend_switched"] is False
    assert receipt["live_cutover_permitted"] is False
    assert receipt["turso_connections"] == 0
    assert receipt["paid_provider_calls"] == 0


def test_claim_preserves_capacity_across_new_independent_fixture_objects(tmp_path):
    counter = new_counter(tmp_path, 3)
    reopened = OfflineAtomicCounter(counter.path, isolated_test_only=True)
    assert counter.claim_once() == 1
    assert reopened.claim_once() == 2
    assert counter.claim_once() == 3
    assert reopened.claim_once() is None
    assert reopened.status()["counter"] == 3


def test_offline_fixture_must_be_new_and_operator_approved(tmp_path):
    missing = tmp_path / "never_created.sqlite"
    with pytest.raises(OfflineAtomicDenied, match="authorization"):
        create_offline_atomic_fixture(missing, max_count=3)
    assert not missing.exists()
    with pytest.raises(OfflineAtomicDenied, match="capacity"):
        create_offline_atomic_fixture(missing, max_count=0, isolated_test_only=True)
    with pytest.raises(OfflineAtomicDenied, match="capacity"):
        create_offline_atomic_fixture(missing, max_count=True, isolated_test_only=True)
    assert not missing.exists()

    production = tmp_path / "existing_source.sqlite"
    Database(production)
    previous = production.read_bytes()
    with pytest.raises(OfflineAtomicDenied, match="existing file"):
        create_offline_atomic_fixture(
            production, max_count=3, isolated_test_only=True,
        )
    with pytest.raises(OfflineAtomicDenied, match="Not an isolated"):
        OfflineAtomicCounter(production, isolated_test_only=True)
    assert production.read_bytes() == previous

    alias = tmp_path / "symlink.sqlite"
    alias.symlink_to(production)
    with pytest.raises(OfflineAtomicDenied, match="Regular"):
        create_offline_atomic_fixture(
            alias, max_count=3, isolated_test_only=True,
        )
    with pytest.raises(OfflineAtomicDenied, match="Regular"):
        OfflineAtomicCounter(alias, isolated_test_only=True)
    assert production.read_bytes() == previous
    with pytest.raises(OfflineAtomicDenied, match="local"):
        create_offline_atomic_fixture(
            "libsql://some-remote.turso.io", max_count=3,
            isolated_test_only=True,
        )


def test_no_fallback_to_unsafe_read_update_or_automatic_retry(tmp_path, monkeypatch):
    import drama_factory.storage.txlab_atomic_candidate as implementation

    counter = new_counter(tmp_path, 2)
    calls = []
    original_connect = implementation.sqlite3.connect

    class SimulatedSQLBusy:
        def __init__(self, real):
            self.real = real

        def execute(self, sql, params=()):
            calls.append(sql)
            raise sqlite3.OperationalError(
                "SQLITE_BUSY: locked, SECRET_BEARER never printed"
            )

        def rollback(self):
            self.real.rollback()

        def close(self):
            self.real.close()

    def busy_connect(*args, **kwargs):
        return SimulatedSQLBusy(original_connect(*args, **kwargs))

    monkeypatch.setattr(implementation.sqlite3, "connect", busy_connect)
    with pytest.raises(sqlite3.OperationalError, match="SQLITE_BUSY"):
        counter.claim_once()
    # This test explicitly proves a *single statement attempted* and no
    # write replay. Production exception sanitization is a different layer.
    assert len(calls) == 1
    assert "UPDATE offline_atomic_counter" in calls[0]
    assert "RETURNING counter" in calls[0]
    monkeypatch.setattr(implementation.sqlite3, "connect", original_connect)
    assert counter.status()["counter"] == 0


def test_worker_read_busy_is_never_classified_as_safe_prebegin_retry():
    decision = assess_txlab_retry(
        stage="worker_read",
        error_category="busy",
        begin_definitively_rejected=False,
        write_sql_executed=False,
        prior_retry_attempts=0,
    )
    assert decision.may_retry_pre_begin is False
    assert decision.review_required is True
    assert decision.maximum_additional_attempts == 0
    assert decision.reason == "transaction_or_commit_uncertain"


def test_fixture_does_not_import_paid_or_remote_clients(tmp_path, monkeypatch):
    import builtins

    original_import = builtins.__import__

    def forbid_cloud(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "googleapiclient", "google.genai")):
            raise AssertionError("Test fixture attempted a remote SDK import")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", forbid_cloud)
    counter = new_counter(tmp_path, 1)
    assert counter.claim_once() == 1
    assert counter.claim_once() is None
    receipt = counter.status()
    assert len(json.dumps(receipt)) > 0
    assert "bearer" not in json.dumps(receipt).lower()
