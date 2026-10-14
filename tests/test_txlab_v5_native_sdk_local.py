"""v5 same isolated test SQL on PINNED libsql==0.1.11 local file.

This is not Turso remote; the real GitHub workflow remains hard-locked
until explicitly activated via separately reviewed merge. No credentials.
"""
from __future__ import annotations

import pytest
from concurrent.futures import ThreadPoolExecutor

from drama_factory.storage.txlab_v5_isolated_dual_runner import (
    stage_setup, stage_actor, stage_seal, stage_observe, V5Denied,
)

libsql = pytest.importorskip("libsql")


def _backend(path):
    def factory():
        return libsql.connect(database=str(path), timeout=15.0)
    return factory


def test_pinned_sdk_performs_one_real_local_multi_connection_competition(tmp_path):
    factory = _backend(tmp_path / "v5-pinned-sdk-local-only.sqlite")
    assert stage_setup(factory, run_id=702)["schema_objects"] == 6
    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(stage_actor, factory, run_id=702, job_id=5001, role="a", wait_seconds=15)
        f2 = pool.submit(stage_actor, factory, run_id=702, job_id=5002, role="b", wait_seconds=15)
        a, b = f1.result(timeout=45), f2.result(timeout=45)
    assert sorted([a["outcome"], b["outcome"]]) == ["accepted", "denied"]
    assert stage_seal(factory)["stale_token_writes"] == 0
    observed = stage_observe(factory, run_id=702, job_id=5003, actor_a=a, actor_b=b)
    assert observed["independent_remote_readback_consistent"] is True
    assert observed["remote_multi_runner_verified"] is False
    assert observed["network_commit_ack_loss_verified"] is False
    with pytest.raises(V5Denied):
        stage_setup(factory, run_id=702)


def test_native_sdk_observer_uses_fixed_select_sql_without_query_only_setting(tmp_path):
    path = tmp_path / "v5-native-observer-sql-only.sqlite"
    factory = _backend(path)
    assert stage_setup(factory, run_id=705)["schema_objects"] == 6
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(stage_actor, factory, run_id=705, job_id=5101, role="a", wait_seconds=15)
        b = pool.submit(stage_actor, factory, run_id=705, job_id=5102, role="b", wait_seconds=15)
        receipts = (a.result(timeout=45), b.result(timeout=45))
    assert sorted(x["outcome"] for x in receipts) == ["accepted", "denied"]
    stage_seal(factory)

    class RemoteRestrictedConnection:
        def __init__(self, real):
            self.real = real
        def execute(self, sql, params=()):
            if not (
                sql == "BEGIN"
                or sql == "PRAGMA foreign_key_check"
                or sql.lstrip().upper().startswith("SELECT ")
            ):
                raise ValueError("unsupported query_only remote PRAGMA")
            return self.real.execute(sql, params)
        def rollback(self):
            return self.real.rollback()
        def close(self):
            return self.real.close()

    result = stage_observe(
        lambda: RemoteRestrictedConnection(factory()), run_id=705,
        job_id=5103, actor_a=receipts[0], actor_b=receipts[1],
    )
    assert result["read_only_sql_path"] is True
    assert result["database_level_read_only_token_verified"] is False
    assert result["remote_multi_runner_verified"] is False
    assert result["paid_provider_calls"] == 0
