"""PR-31b2o5 synthetic provider task binding: real SDK local-only tests."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from drama_factory.storage.libsql_sdk_local_ledger import _NativeConnection
from drama_factory.storage.pr31_native_fenced_intent_lab import (
    fenced_hold_and_record_intent_local,
)
from drama_factory.storage.pr31_native_fenced_job_lab import (
    NativeFenceLabDenied, fenced_claim_local_job, set_local_writer_gate,
)
from drama_factory.storage.pr31_native_synthetic_task_lab import (
    fenced_bind_synthetic_provider_task_local,
)
from drama_factory.storage.pr31_offline_recovery import (
    inspect_offline_job_recovery,
)
from test_pr31_native_fenced_job_lab import _ready_lab
from test_pr31_native_fenced_intent_lab import _set_policies

libsql = pytest.importorskip("libsql")

TASK1 = "SYNTHETIC_FAKE_TASK_001"
TASK2 = "SYNTHETIC_FAKE_TASK_002"


def _staged(client):
    backend, series, run = _ready_lab(client)
    point = datetime.now(timezone.utc)
    _set_policies(backend, series, provider_limit="2.00")
    token = fenced_claim_local_job(
        backend, "synthetic-worker", production_id=run, now=point,
    )
    assert token
    receipt = fenced_hold_and_record_intent_local(
        backend, token, estimated_charge_usd="0.40", now=point,
    )
    assert receipt["status"] == "submission_intent"
    return backend, run, point, token


def _count(backend, action, table="shot_job_events"):
    assert table in ("shot_job_events", "pr31_native_job_fence_events")
    return backend.one(
        f"SELECT COUNT(*) AS n FROM {table} WHERE action=?", (action,),
    )["n"]


def test_synthetic_receipt_binds_only_after_intent_and_cannot_replay(client):
    backend, _, point, token = _staged(client)
    receipt = fenced_bind_synthetic_provider_task_local(
        backend, token, TASK1, now=point,
    )
    assert receipt["status"] == "submitted"
    assert receipt["synthetic_task_bound"] is True
    assert receipt["task_was_generated"] is False
    assert receipt["remote_provider_queried"] is False
    assert receipt["authorizes_paid_provider_call"] is False
    assert receipt["may_retry_submission"] is False
    assert receipt["paid_provider_calls"] == 0
    assert TASK1 not in str(receipt) and token.worker_id not in str(receipt)
    assert backend.one(
        "SELECT status,provider_task_id FROM shot_jobs WHERE id=?",
        (token.job_id,),
    ) == {"status": "submitted", "provider_task_id": TASK1}
    assert _count(backend, "provider_task_recorded") == 1
    assert _count(
        backend, "fenced_synthetic_task_bound",
        "pr31_native_job_fence_events",
    ) == 1
    recovery = inspect_offline_job_recovery(backend, token.job_id, now=point)
    assert {"existing_provider_task", "held_budget"} <= set(recovery["flags"])
    assert "intent_uncertain" not in recovery["flags"]
    assert recovery["may_resubmit_paid_provider"] is False
    assert TASK1 not in str(recovery)
    with pytest.raises(NativeFenceLabDenied, match="stale"):
        fenced_bind_synthetic_provider_task_local(
            backend, token, TASK1, now=point,
        )
    assert _count(backend, "provider_task_recorded") == 1


@pytest.mark.parametrize("candidate", [
    "",
    "REAL_PROVIDER_TASK_ID",
    "SYNTHETIC_short",
    "SYNTHETIC_bad/slash",
])
def test_only_synthetic_fixture_task_names_accepted(client, candidate):
    backend, _, point, token = _staged(client)
    with pytest.raises(NativeFenceLabDenied, match="synthetic"):
        fenced_bind_synthetic_provider_task_local(
            backend, token, candidate, now=point,
        )
    assert backend.one(
        "SELECT status,provider_task_id FROM shot_jobs WHERE id=?",
        (token.job_id,),
    ) == {"status": "submission_intent", "provider_task_id": None}


def test_same_provider_synthetic_task_id_cannot_bind_to_two_jobs(client):
    backend, run, point, first = _staged(client)
    second = fenced_claim_local_job(
        backend, "second-synthetic-worker", production_id=run, now=point,
    )
    assert second and second.job_id != first.job_id
    fenced_hold_and_record_intent_local(
        backend, second, estimated_charge_usd="0.40", now=point,
    )
    fenced_bind_synthetic_provider_task_local(
        backend, first, TASK1, now=point,
    )
    with pytest.raises(NativeFenceLabDenied, match="Duplicate"):
        fenced_bind_synthetic_provider_task_local(
            backend, second, TASK1, now=point,
        )
    assert backend.one(
        "SELECT status,provider_task_id FROM shot_jobs WHERE id=?",
        (second.job_id,),
    ) == {"status": "submission_intent", "provider_task_id": None}
    assert _count(backend, "provider_task_recorded") == 1
    fenced_bind_synthetic_provider_task_local(
        backend, second, TASK2, now=point,
    )
    assert _count(backend, "provider_task_recorded") == 2


@pytest.mark.parametrize("changes", [
    {"attempt": 2}, {"worker_id": "other-worker"},
    {"epoch": 7}, {"lease_expires_at": "2099-01-01T00:00:00+00:00"},
])
def test_stale_claim_tuple_cannot_record_provider_task(client, changes):
    backend, _, point, token = _staged(client)
    with pytest.raises(NativeFenceLabDenied):
        fenced_bind_synthetic_provider_task_local(
            backend, replace(token, **changes), TASK1, now=point,
        )
    assert _count(backend, "provider_task_recorded") == 0
    assert backend.one(
        "SELECT status FROM shot_jobs WHERE id=?", (token.job_id,),
    )["status"] == "submission_intent"


def test_expiry_and_pause_resume_invalidate_provider_receipt(client):
    backend, _, point, token = _staged(client)
    with pytest.raises(NativeFenceLabDenied):
        fenced_bind_synthetic_provider_task_local(
            backend, token, TASK1, now=point + timedelta(seconds=95),
        )
    assert set_local_writer_gate(backend, pause=True)["epoch"] == 2
    with pytest.raises(NativeFenceLabDenied, match="epoch"):
        fenced_bind_synthetic_provider_task_local(
            backend, token, TASK1, now=point,
        )
    assert set_local_writer_gate(
        backend, pause=False, operator_reviewed=True,
    )["epoch"] == 3
    with pytest.raises(NativeFenceLabDenied, match="epoch"):
        fenced_bind_synthetic_provider_task_local(
            backend, token, TASK1, now=point,
        )
    assert _count(backend, "provider_task_recorded") == 0


def test_no_held_reservation_no_synthetic_task_binding(client):
    backend, _, point, token = _staged(client)
    with backend.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE job_budget_reservations SET status='released' WHERE job_id=?",
            (token.job_id,),
        )
    with pytest.raises(NativeFenceLabDenied, match="held"):
        fenced_bind_synthetic_provider_task_local(
            backend, token, TASK1, now=point,
        )
    assert _count(backend, "provider_task_recorded") == 0


def test_shot_audit_failure_rolls_back_provider_task_status(client, monkeypatch):
    import drama_factory.storage.pr31_native_synthetic_task_lab as module

    backend, _, point, token = _staged(client)
    with monkeypatch.context() as patch:
        patch.setattr(module.shots, "_event", lambda *a: (_ for _ in ()).throw(
            RuntimeError("synthetic shot event insertion failure")
        ))
        with pytest.raises(RuntimeError, match="shot event"):
            fenced_bind_synthetic_provider_task_local(
                backend, token, TASK1, now=point,
            )
    assert backend.one(
        "SELECT status,provider_task_id FROM shot_jobs WHERE id=?",
        (token.job_id,),
    ) == {"status": "submission_intent", "provider_task_id": None}
    assert _count(backend, "provider_task_recorded") == 0
    assert _count(
        backend, "fenced_synthetic_task_bound",
        "pr31_native_job_fence_events",
    ) == 0


def test_last_gate_audit_failure_rolls_back_task_event_and_state(client, monkeypatch):
    import drama_factory.storage.pr31_native_synthetic_task_lab as module

    backend, _, point, token = _staged(client)
    with monkeypatch.context() as patch:
        patch.setattr(module, "_gate_event", lambda *a: (_ for _ in ()).throw(
            RuntimeError("synthetic gate event insertion failure")
        ))
        with pytest.raises(RuntimeError, match="gate event"):
            fenced_bind_synthetic_provider_task_local(
                backend, token, TASK1, now=point,
            )
    assert backend.one(
        "SELECT status,provider_task_id FROM shot_jobs WHERE id=?",
        (token.job_id,),
    ) == {"status": "submission_intent", "provider_task_id": None}
    assert _count(backend, "provider_task_recorded") == 0


def test_real_sdk_commit_ack_lost_synthetic_task_must_not_replay(client, monkeypatch):
    backend, _, point, token = _staged(client)
    commit = _NativeConnection.commit
    seen = []

    def durable_but_ack_lost(conn):
        commit(conn)
        seen.append(True)
        raise ConnectionError("synthetic commit ACK lost PRIVATE_TOKEN")

    with monkeypatch.context() as patch:
        patch.setattr(_NativeConnection, "commit", durable_but_ack_lost)
        with pytest.raises(ConnectionError, match="ACK lost"):
            fenced_bind_synthetic_provider_task_local(
                backend, token, TASK1, now=point,
            )
    assert seen == [True]
    assert backend.one(
        "SELECT status,provider_task_id FROM shot_jobs WHERE id=?",
        (token.job_id,),
    ) == {"status": "submitted", "provider_task_id": TASK1}
    assert _count(backend, "provider_task_recorded") == 1
    assert _count(
        backend, "fenced_synthetic_task_bound",
        "pr31_native_job_fence_events",
    ) == 1
    with pytest.raises(NativeFenceLabDenied):
        fenced_bind_synthetic_provider_task_local(
            backend, token, TASK1, now=point,
        )
    assert _count(backend, "provider_task_recorded") == 1
    assert "PRIVATE_TOKEN" not in str(
        inspect_offline_job_recovery(backend, token.job_id, now=point)
    )


def test_unmarked_source_is_never_accepted():
    with pytest.raises(NativeFenceLabDenied):
        fenced_bind_synthetic_provider_task_local(
            object(), object(), TASK1,
        )
