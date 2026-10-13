"""PR-31c2 test-only epoch fencing; zero production/cloud side effects."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from drama_factory.db import Database
from drama_factory.storage.offline_fencing import (
    OfflineFence, OfflineFenceDenied, create_offline_fence,
)


def fixture(tmp_path):
    return create_offline_fence(
        tmp_path / "isolated-fence.sqlite", isolated_test_only=True,
    )


def test_fixture_creation_refuses_existing_sources_and_symlinks(tmp_path):
    live_like = tmp_path / "existing-production.sqlite"
    Database(live_like)
    before = live_like.read_bytes()
    with pytest.raises(OfflineFenceDenied, match="Existing file"):
        create_offline_fence(live_like, isolated_test_only=True)
    with pytest.raises(OfflineFenceDenied, match="Not an isolated"):
        OfflineFence(live_like, isolated_test_only=True)
    assert live_like.read_bytes() == before

    alias = tmp_path / "symlink.sqlite"
    alias.symlink_to(live_like)
    with pytest.raises(OfflineFenceDenied, match="Symlink"):
        create_offline_fence(alias, isolated_test_only=True)
    with pytest.raises(OfflineFenceDenied, match="Symlink"):
        OfflineFence(alias, isolated_test_only=True)
    assert live_like.read_bytes() == before

    new_path = tmp_path / "never-created.sqlite"
    with pytest.raises(OfflineFenceDenied, match="approval"):
        create_offline_fence(new_path)
    assert not new_path.exists()
    with pytest.raises(OfflineFenceDenied, match="local"):
        create_offline_fence("libsql://dangerous.turso.io", isolated_test_only=True)


def test_fake_worker_writes_stop_after_pause_and_old_token_cannot_resume(tmp_path):
    gate = fixture(tmp_path)
    initial = gate.snapshot()
    assert initial["epoch"] == 1
    assert initial["state"] == "running"
    for _ in range(3):
        gate.simulate_worker_write(initial["epoch"])
    pause = gate.pause_for_test()
    assert pause == {"epoch": 2, "state": "paused"}
    assert gate.snapshot()["simulated_worker_writes"] == 3
    for epoch in (initial["epoch"], pause["epoch"]):
        with pytest.raises(OfflineFenceDenied, match="Stale epoch"):
            gate.simulate_worker_write(epoch)
    assert gate.snapshot()["simulated_worker_writes"] == 3
    with pytest.raises(OfflineFenceDenied, match="Already paused"):
        gate.pause_for_test()
    with pytest.raises(OfflineFenceDenied, match="review"):
        gate.resume_for_test()
    resumed = gate.resume_for_test(operator_reviewed=True)
    assert resumed == {"epoch": 3, "state": "running"}
    for old in (1, 2):
        with pytest.raises(OfflineFenceDenied, match="Stale epoch"):
            gate.simulate_worker_write(old)
    assert gate.simulate_worker_write(3) == 4
    assert gate.snapshot()["simulated_worker_writes"] == 4
    snap = gate.snapshot()
    assert snap["fleet_writers_fenced"] is False
    assert snap["production_backend_switched"] is False
    assert snap["live_cutover_permitted"] is False
    assert snap["turso_connections"] == 0
    assert snap["paid_provider_calls"] == 0


def test_threads_racing_pause_cannot_write_after_commit(tmp_path):
    gate = fixture(tmp_path)
    sync = Barrier(13)

    def writer(_):
        sync.wait(timeout=20)
        try:
            gate.simulate_worker_write(1)
            return "written"
        except OfflineFenceDenied:
            return "rejected"

    def pause():
        sync.wait(timeout=20)
        return gate.pause_for_test()

    with ThreadPoolExecutor(max_workers=13) as pool:
        jobs = [pool.submit(writer, i) for i in range(12)]
        stopper = pool.submit(pause)
        outcomes = [task.result(timeout=30) for task in jobs]
        stopped = stopper.result(timeout=30)

    assert stopped["epoch"] == 2
    assert all(result in ("written", "rejected") for result in outcomes)
    count = outcomes.count("written")
    assert gate.snapshot()["simulated_worker_writes"] == count
    assert gate.snapshot()["state"] == "paused"
    # A pause always serializes after prior writes, and stale workers may not
    # increment after it commits, even if they entered their thread earlier.
    for _ in range(10):
        with pytest.raises(OfflineFenceDenied, match="Stale epoch"):
            gate.simulate_worker_write(1)
    assert gate.snapshot()["simulated_worker_writes"] == count
    with sqlite3.connect(gate.path) as con:
        assert con.execute(
            "SELECT COUNT(*) FROM offline_fence_events WHERE action='fake_write'"
        ).fetchone()[0] == count
        assert con.execute(
            "SELECT COUNT(*) FROM offline_fence_events WHERE action='pause'"
        ).fetchone()[0] == 1


def test_fake_write_rolls_back_if_audit_event_fails(tmp_path, monkeypatch):
    import drama_factory.storage.offline_fencing as impl

    gate = fixture(tmp_path)

    def fail_event(conn, action, epoch):
        if action == "fake_write":
            raise RuntimeError("simulated local event failure")
        return impl._old_event(conn, action, epoch)

    with monkeypatch.context() as patch:
        original_event = impl._event
        patch.setattr(impl, "_old_event", original_event, raising=False)
        patch.setattr(impl, "_event", fail_event)
        with pytest.raises(RuntimeError, match="simulated"):
            gate.simulate_worker_write(1)

    assert gate.snapshot()["simulated_worker_writes"] == 0
    with sqlite3.connect(gate.path) as con:
        assert con.execute("SELECT COUNT(*) FROM offline_fence_events").fetchone()[0] == 0


def test_pause_rolls_back_if_audit_event_fails(tmp_path, monkeypatch):
    import drama_factory.storage.offline_fencing as impl

    gate = fixture(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(impl, "_event",
                      lambda *args, **kwargs: (_ for _ in ()).throw(
                          RuntimeError("simulated pause audit failure")
                      ))
        with pytest.raises(RuntimeError, match="simulated"):
            gate.pause_for_test()
    assert gate.snapshot()["epoch"] == 1
    assert gate.snapshot()["state"] == "running"
    assert gate.simulate_worker_write(1) == 1


def test_no_cloud_clients_or_paid_providers_are_imported(tmp_path, monkeypatch):
    import builtins

    original = builtins.__import__
    def forbid(name, *args, **kwargs):
        if name.startswith(("libsql", "turso_serverless", "google_genai", "googleapiclient")):
            raise AssertionError("Unexpected remote import")
        return original(name, *args, **kwargs)
    gate = fixture(tmp_path)
    monkeypatch.setattr(builtins, "__import__", forbid)
    assert gate.simulate_worker_write(1) == 1
    assert gate.pause_for_test()["state"] == "paused"
    assert gate.snapshot()["paid_provider_calls"] == 0
