"""TxLab v5 exactly same stage SQL under offline isolated sqlite3 fixture.

No Turso URL, Secrets, production ledger or provider calls. These tests
enforce one-shot prefix guard, parallel claims and independent observer.
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from drama_factory.storage.txlab_v5_isolated_dual_runner import (
    _OBJECTS, V5Denied, V5StageError,
    stage_setup, stage_actor, stage_seal, stage_observe, run_stage, cli,
)


def _factory(path: Path):
    def connect():
        conn = sqlite3.connect(path, timeout=15, isolation_level="DEFERRED")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    return connect


def _parallel(factory):
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(stage_actor, factory, run_id=77, job_id=1001, role="a", wait_seconds=6)
        b = pool.submit(stage_actor, factory, run_id=77, job_id=1002, role="b", wait_seconds=6)
        return a.result(timeout=25), b.result(timeout=25)


def test_two_independent_connections_one_remote_shaped_budget_barrier_and_readback(tmp_path):
    path = tmp_path / "v5-contract-offline-only.sqlite"
    factory = _factory(path)
    setup = stage_setup(factory, run_id=77)
    assert setup["schema_objects"] == len(_OBJECTS) == 6
    assert setup["paid_provider_calls"] == 0
    a, b = _parallel(factory)
    assert sorted((a["outcome"], b["outcome"])) == ["accepted", "denied"]
    assert {a["github_job_id"], b["github_job_id"]} == {1001, 1002}
    seal = stage_seal(factory)
    assert seal["stale_token_writes"] == 0
    assert seal["gate_paused"] is True
    observed = stage_observe(factory, run_id=77, job_id=1003, actor_a=a, actor_b=b)
    assert observed["independent_remote_readback_consistent"] is True
    assert observed["one_accepted_one_denied"] is True
    assert observed["remote_multi_runner_verified"] is False
    assert observed["network_commit_ack_loss_verified"] is False
    assert observed["paid_provider_calls"] == 0
    assert observed["live_cutover_permitted"] is False
    with sqlite3.connect(path) as db:
        schema = {r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE name LIKE 'pr31_v5_%'"
        )}
        assert schema == _OBJECTS
        assert db.execute("SELECT COUNT(*) FROM pr31_v5_holds").fetchone() == (1,)
        assert db.execute("SELECT state,epoch FROM pr31_v5_gate").fetchone() == ("paused", 2)
        assert db.execute("SELECT COUNT(*) FROM pr31_v5_events").fetchone() == (3,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    # A second stage cannot silently replay a test into an old namespace.
    with pytest.raises(V5Denied):
        stage_setup(factory, run_id=77)


def test_gate_does_not_allow_out_of_order_seal_or_lost_actor(tmp_path):
    factory = _factory(tmp_path / "v5-no-out-of-order.sqlite")
    stage_setup(factory, run_id=7)
    with pytest.raises(V5Denied):
        stage_seal(factory)
    with pytest.raises(V5StageError):
        stage_actor(factory, run_id=7, job_id=100, role="a", wait_seconds=.15)
    with sqlite3.connect(tmp_path / "v5-no-out-of-order.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM pr31_v5_holds").fetchone() == (0,)


def test_fake_or_mismatched_observer_receipt_fails_closed(tmp_path):
    factory = _factory(tmp_path / "v5-readonly-proof.sqlite")
    stage_setup(factory, run_id=77)
    a, b = _parallel(factory)
    stage_seal(factory)
    fake = dict(a, github_job_id=b["github_job_id"])
    with pytest.raises(V5EvidenceDenied):
        stage_observe(factory, run_id=77, job_id=1003, actor_a=fake, actor_b=b)
    assert stage_observe(factory, run_id=77, job_id=1003,
                         actor_a=a, actor_b=b)["remote_multi_runner_verified"] is False


def test_cli_fail_closed_no_credentials_or_cost_gate(monkeypatch, capsys):
    for var in (
        "DRAMA_TXLAB_V5_CONFIRM", "DRAMA_ENABLE_TXLAB_V5_WRITE",
        "DRAMA_TXLAB_V5_MAX_USD", "DRAMA_TXLAB_DATABASE_URL",
        "DRAMA_TXLAB_AUTH_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)
    assert cli(["--stage", "setup"]) == 1
    assert "denied" in capsys.readouterr().err.lower()


def test_live_schema_is_namespaced_and_has_no_old_or_prod_table_mutations():
    from drama_factory.storage.txlab_v5_isolated_dual_runner import _DDL
    sql = "\n".join(_DDL).lower()
    assert len(_DDL) == 6
    for obj in _OBJECTS:
        assert obj in sql
    for forbidden in ("create if not exists", "drop table", "alter table",
                      "pr31_v4_", "create table shot_jobs", "create table job_budget",
                      "call provider", "production_database_url"):
        assert forbidden not in sql


from drama_factory.storage.pr31_v5_offline_evidence_guard import V5EvidenceDenied
