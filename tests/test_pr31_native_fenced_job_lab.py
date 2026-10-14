"""PR-31b2o3: actual libsql==0.1.11 on marked disposable local test files."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

from drama_factory.jobs.budgets import configure_policy, reserve_job_budget
from drama_factory.jobs.shots import prepare_shot_jobs, record_submission_intent, restore_failed_job
from drama_factory.storage.libsql_sdk_local_ledger import _NativeConnection
from drama_factory.storage.pr31_native_fenced_job_lab import (
    NativeFenceLabDenied, fenced_claim_local_job,
    fenced_fail_unsubmitted_local_job, init_local_native_fence_lab,
    set_local_writer_gate,
)
from test_libsql_sdk_local_ledger_adapter import _backend, _production

libsql = pytest.importorskip("libsql")
NOW = datetime.now(timezone.utc)


def _ready_lab(client):
    series, run = _production(client)
    backend = _backend(client)
    jobs = prepare_shot_jobs(backend, run)
    assert len(jobs) == 2
    init_local_native_fence_lab(backend, isolated_test_only=True)
    return backend, series, run


def _count(backend, table, *, action):
    # Fixed query-only helper; never interpolate untrusted table names.
    assert table in ("shot_job_events", "pr31_native_job_fence_events")
    return backend.one(
        f"SELECT COUNT(*) AS n FROM {table} WHERE action=?", (action,)
    )["n"]


def test_fixture_isolation_and_explicit_opt_in(client):
    backend, _, _ = _ready_lab(client)
    assert _count(backend, "pr31_native_job_fence_events", action="pause") == 0
    with pytest.raises(NativeFenceLabDenied, match="offline"):
        init_local_native_fence_lab(backend)
    with pytest.raises(NativeFenceLabDenied, match="fixture"):
        init_local_native_fence_lab(object(), isolated_test_only=True)
    assert backend.safety_metadata()["live_cutover_permitted"] is False


def test_six_concurrent_native_claims_cannot_share_a_job_or_epoch(client):
    backend, _, run = _ready_lab(client)
    gate = Barrier(6)

    def claim(i):
        gate.wait(timeout=20)
        try:
            return fenced_claim_local_job(
                backend, f"fenced-worker-{i}", production_id=run, now=NOW
            )
        except NativeFenceLabDenied as exc:
            # The real native libSQL SDK occasionally refuses simultaneous
            # BEGIN IMMEDIATE *before* entering any transaction. This is a
            # safely declined claim, not a lost paid COMMIT acknowledgement.
            assert "pretransaction" in str(exc)
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        claimed = [x for x in pool.map(claim, range(6)) if x is not None]
    assert len(claimed) <= 2
    assert len({t.job_id for t in claimed}) == len(claimed)
    # Once the initial race is over, issue distinct NEW unpaid claim
    # attempts to account for any legitimately declined pre-BEGIN workers.
    # This is NOT resubmission of an external/paid generation request.
    for i in range(2):
        remaining = fenced_claim_local_job(
            backend, f"fenced-fresh-unpaid-worker-{i}",
            production_id=run, now=NOW,
        )
        if remaining is not None:
            claimed.append(remaining)
    assert len(claimed) == 2
    assert len({t.job_id for t in claimed}) == len(claimed)
    assert all(t.attempt == 1 and t.epoch == 1 for t in claimed)
    assert _count(backend, "shot_job_events", action="claimed") == 2
    assert _count(backend, "pr31_native_job_fence_events", action="fenced_claim") == 2
    assert all(
        backend.one("SELECT status,attempts FROM shot_jobs WHERE id=?", (t.job_id,))
        == {"status": "leased", "attempts": 1} for t in claimed
    )


def test_reused_worker_name_cannot_commit_stale_attempt_after_manual_retry(client):
    backend, _, run = _ready_lab(client)
    old = fenced_claim_local_job(backend, "same-worker", production_id=run, now=NOW)
    assert old and old.attempt == 1
    # Occupy the other pending job before retrying, so only the first is ready.
    other = fenced_claim_local_job(backend, "different-worker", production_id=run, now=NOW)
    assert other and other.job_id != old.job_id
    fenced_fail_unsubmitted_local_job(backend, old, now=NOW)
    assert restore_failed_job(backend, old.job_id, operator_reviewed=True)["status"] == "pending"
    current = fenced_claim_local_job(backend, "same-worker", production_id=run, now=NOW)
    assert current and current.job_id == old.job_id
    assert current.attempt == 2 and current.worker_id == old.worker_id
    with pytest.raises(NativeFenceLabDenied, match="stale"):
        fenced_fail_unsubmitted_local_job(backend, old, now=NOW)
    assert backend.one(
        "SELECT status,attempts FROM shot_jobs WHERE id=?", (old.job_id,)
    ) == {"status": "leased", "attempts": 2}
    assert fenced_fail_unsubmitted_local_job(backend, current, now=NOW)["state"] == "failed"


def test_paused_gate_invalidates_all_old_tokens_even_after_resume(client):
    backend, _, run = _ready_lab(client)
    old = fenced_claim_local_job(backend, "offline-worker", production_id=run, now=NOW)
    assert old
    paused = set_local_writer_gate(backend, pause=True)
    assert paused["epoch"] == 2 and paused["state"] == "paused"
    with pytest.raises(NativeFenceLabDenied, match="epoch"):
        fenced_fail_unsubmitted_local_job(backend, old, now=NOW)
    with pytest.raises(NativeFenceLabDenied, match="paused"):
        fenced_claim_local_job(backend, "new-worker", production_id=run, now=NOW)
    with pytest.raises(NativeFenceLabDenied, match="review"):
        set_local_writer_gate(backend, pause=False)
    resumed = set_local_writer_gate(backend, pause=False, operator_reviewed=True)
    assert resumed["epoch"] == 3
    with pytest.raises(NativeFenceLabDenied, match="epoch"):
        fenced_fail_unsubmitted_local_job(backend, old, now=NOW)
    fresh = fenced_claim_local_job(backend, "new-worker", production_id=run, now=NOW)
    assert fresh and fresh.epoch == 3
    assert _count(backend, "pr31_native_job_fence_events", action="pause") == 1
    assert _count(backend, "pr31_native_job_fence_events", action="resume") == 1


def test_expiry_and_paid_intent_never_allow_local_fenced_failure(client):
    backend, series, run = _ready_lab(client)
    first = fenced_claim_local_job(backend, "owner-1", production_id=run, now=NOW)
    assert first
    with pytest.raises(NativeFenceLabDenied, match="stale"):
        fenced_fail_unsubmitted_local_job(
            backend, first, now=NOW + timedelta(seconds=91)
        )
    second = fenced_claim_local_job(backend, "owner-2", production_id=run, now=NOW)
    assert second
    column_id = backend.one(
        "SELECT column_id FROM projects WHERE id=?", (series,)
    )["column_id"]
    for scope, key in (("column", column_id), ("series", series), ("provider", "google")):
        configure_policy(backend, scope, key, daily_limit_usd="2.00", max_active_jobs=2)
    # Use current day for both reservation and intent; fixed NOW is only for lease fixture.
    reservation = reserve_job_budget(backend, second.job_id, estimated_charge_usd="0.40", now=NOW)
    assert reservation["status"] == "held"
    record_submission_intent(backend, second.job_id, "owner-2", now=NOW)
    with pytest.raises(NativeFenceLabDenied, match="safely unsubmitted"):
        fenced_fail_unsubmitted_local_job(backend, second, now=NOW)
    assert backend.one(
        "SELECT status,generation_intent_recorded FROM shot_jobs WHERE id=?",
        (second.job_id,)
    ) == {"status": "submission_intent", "generation_intent_recorded": 1}


def test_audit_failure_rolls_back_real_job_update_and_gate_event(client, monkeypatch):
    import drama_factory.storage.pr31_native_fenced_job_lab as impl

    backend, _, run = _ready_lab(client)
    token = fenced_claim_local_job(backend, "safe-worker", production_id=run, now=NOW)
    before_shot = _count(backend, "shot_job_events", action="failed")
    with monkeypatch.context() as patch:
        patch.setattr(impl, "_gate_event", lambda *args: (_ for _ in ()).throw(
            RuntimeError("local synthetic gate audit unavailable")
        ))
        with pytest.raises(RuntimeError, match="gate audit"):
            fenced_fail_unsubmitted_local_job(backend, token, now=NOW)
    assert backend.one("SELECT status FROM shot_jobs WHERE id=?", (token.job_id,))["status"] == "leased"
    assert _count(backend, "shot_job_events", action="failed") == before_shot
    assert _count(backend, "pr31_native_job_fence_events", action="fenced_unsubmitted_failure") == 0
    fenced_fail_unsubmitted_local_job(backend, token, now=NOW)


def test_real_commit_followed_by_lost_ack_is_never_replayed(client, monkeypatch):
    backend, _, run = _ready_lab(client)
    token = fenced_claim_local_job(backend, "ack-worker", production_id=run, now=NOW)
    real_commit = _NativeConnection.commit
    commits = []

    def commit_but_drop_ack(conn):
        real_commit(conn)
        commits.append(True)
        raise ConnectionError("durable commit; synthetic response lost")

    with monkeypatch.context() as patch:
        patch.setattr(_NativeConnection, "commit", commit_but_drop_ack)
        with pytest.raises(ConnectionError, match="response lost"):
            fenced_fail_unsubmitted_local_job(backend, token, now=NOW)
    assert len(commits) == 1
    assert backend.one("SELECT status FROM shot_jobs WHERE id=?", (token.job_id,))["status"] == "failed"
    assert _count(backend, "shot_job_events", action="failed") == 1
    assert _count(backend, "pr31_native_job_fence_events", action="fenced_unsubmitted_failure") == 1
    with pytest.raises(NativeFenceLabDenied):
        fenced_fail_unsubmitted_local_job(backend, token, now=NOW)
    assert _count(backend, "shot_job_events", action="failed") == 1


def test_pause_racing_write_serializes_without_post_pause_success(client):
    backend, _, run = _ready_lab(client)
    token = fenced_claim_local_job(backend, "race-worker", production_id=run, now=NOW)
    gate = Barrier(2)

    def attempt_write():
        gate.wait(timeout=20)
        try:
            fenced_fail_unsubmitted_local_job(backend, token, now=NOW)
            return "committed"
        except NativeFenceLabDenied:
            return "denied"

    def pause():
        gate.wait(timeout=20)
        return set_local_writer_gate(backend, pause=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(attempt_write)
        pauser = pool.submit(pause)
        result = writer.result(timeout=30)
        paused = pauser.result(timeout=30)
    assert paused["epoch"] == 2
    assert result in ("committed", "denied")
    assert backend.one("SELECT status FROM shot_jobs WHERE id=?", (token.job_id,))["status"] == (
        "failed" if result == "committed" else "leased"
    )
    for _ in range(3):
        with pytest.raises(NativeFenceLabDenied, match="epoch"):
            fenced_fail_unsubmitted_local_job(backend, token, now=NOW)


def test_declined_prebegin_native_busy_has_no_audit_or_claim_and_no_internal_retry(
    client, monkeypatch,
):
    backend, _, run = _ready_lab(client)
    real_execute = _NativeConnection.execute
    seen = []

    def reject_only_begin(conn, sql, params=()):
        if sql == "BEGIN IMMEDIATE":
            seen.append(sql)
            raise ValueError("database is locked")
        return real_execute(conn, sql, params)

    with monkeypatch.context() as patch:
        patch.setattr(_NativeConnection, "execute", reject_only_begin)
        with pytest.raises(NativeFenceLabDenied, match="pretransaction"):
            fenced_claim_local_job(
                backend, "declined-worker", production_id=run, now=NOW,
            )
    assert seen == ["BEGIN IMMEDIATE"]  # no internal retry after rejection
    assert _count(backend, "shot_job_events", action="claimed") == 0
    assert _count(backend, "pr31_native_job_fence_events", action="fenced_claim") == 0
    assert backend.one(
        "SELECT COUNT(*) AS n FROM shot_jobs WHERE status='pending'"
    )["n"] == 2
    # Separate, later unpaid attempt is valid only because no paid intent
    # and no transaction ever started in the rejected call.
    token = fenced_claim_local_job(
        backend, "later-unpaid-worker", production_id=run, now=NOW,
    )
    assert token is not None and token.attempt == 1
    assert _count(backend, "shot_job_events", action="claimed") == 1
