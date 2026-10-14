"""PR-31c3c: exhaustive pure ordering spec + real native SDK differential.

No remote URL/Secret or paid Provider. A and B are synthetic Worker roles
within the SAME marked local SQLite test fixture; never remote Runners.
"""
from __future__ import annotations

from itertools import permutations
from datetime import datetime, timezone

import pytest

from drama_factory.storage.pr31_v5_offline_schedule_oracle import (
    OPS, OfflineScheduleDenied, predict_offline_schedule,
)


def test_exhaustive_720_symbolic_permutations_cannot_double_hold_or_pay():
    for order in permutations(OPS):
        result = predict_offline_schedule(order)
        assert len(result["accepted"]) == 6
        assert 0 <= result["intents"] <= 1
        assert 0 <= result["tasks"] <= result["intents"]
        assert result["held_budget_reservations"] == result["intents"]
        assert result["epoch"] in (2, 3)
        assert result["remote_multi_runner_verified"] is False
        assert result["remote_txlab_write_calls"] == 0
        assert result["paid_provider_calls"] == 0
        assert result["may_resume_production"] is False
        assert result["live_cutover_permitted"] is False
        # A real pause is present in every schedule. Even if an old worker
        # managed an intent earlier, it may not register a new one later.
        pause_at = order.index("pause")
        resume_at = order.index("resume")
        if pause_at < resume_at:
            assert result["gate"] == "running"
            assert result["epoch"] == 3
        else:
            assert result["gate"] == "paused"
            assert result["epoch"] == 2


@pytest.mark.parametrize("bad", [
    (), ["pause"], ("pause", "pause"), ("bogus",), ("intent_a",) * 7,
])
def test_oracle_rejects_unknown_duplicate_or_unbounded_inputs(bad):
    with pytest.raises(OfflineScheduleDenied):
        predict_offline_schedule(bad)


def test_late_task_without_prior_intent_and_released_epoch_stay_denied():
    result = predict_offline_schedule((
        "task_a", "pause", "resume", "intent_a", "task_b",
    ))
    assert result["accepted"] == (False, True, True, False, False)
    assert result["intents"] == result["tasks"] == 0


# Native libSQL SDK is mandatory in its dedicated CI; import lazily so the
# normal two Python-version offline matrix keeps running without libsql.
libsql = pytest.importorskip("libsql")
from drama_factory.storage.pr31_native_fenced_job_lab import (
    NativeFenceLabDenied, fenced_claim_local_job, set_local_writer_gate,
)
from drama_factory.storage.pr31_native_fenced_intent_lab import (
    fenced_hold_and_record_intent_local,
)
from drama_factory.storage.pr31_native_synthetic_task_lab import (
    fenced_bind_synthetic_provider_task_local,
)
from test_pr31_native_fenced_job_lab import _ready_lab
from test_pr31_native_fenced_intent_lab import _set_policies


def _count(db, table, action):
    assert table in (
        "shot_job_events",
        "budget_reservation_events",
        "pr31_native_job_fence_events",
    )
    return db.one(
        f"SELECT COUNT(*) AS n FROM {table} WHERE action=?",
        (action,),
    )["n"]


def _test_one_real_schedule(client, operations):
    db, series, run = _ready_lab(client)
    now = datetime.now(timezone.utc)
    _set_policies(db, series, provider_limit="0.60")
    tokens = {
        role: fenced_claim_local_job(
            db, "offline-runner-" + role, production_id=run, now=now,
        )
        for role in ("a", "b")
    }
    assert all(tokens.values())
    assert tokens["a"].epoch == tokens["b"].epoch == 1
    expected = predict_offline_schedule(tuple(operations))

    for i, op in enumerate(operations):
        try:
            if op == "pause":
                set_local_writer_gate(db, pause=True)
            elif op == "resume":
                set_local_writer_gate(db, pause=False, operator_reviewed=True)
            elif op in ("intent_a", "intent_b"):
                fenced_hold_and_record_intent_local(
                    db, tokens[op[-1]], estimated_charge_usd="0.40", now=now,
                )
            elif op in ("task_a", "task_b"):
                fenced_bind_synthetic_provider_task_local(
                    db, tokens[op[-1]],
                    "SYNTHETIC_SCHEDULE_TASK_" + op[-1].upper() + "_0001",
                    now=now,
                )
            else:
                raise AssertionError("Unexpected schedule step")
            accepted = True
        except NativeFenceLabDenied:
            accepted = False
        assert accepted == expected["accepted"][i], (operations, i, op)

        prefix = predict_offline_schedule(tuple(operations[:i+1]))
        gate = db.one(
            "SELECT epoch,state FROM pr31_native_job_fence_gate WHERE id=1"
        )
        assert gate == {"epoch": prefix["epoch"], "state": prefix["gate"]}
        assert db.one(
            "SELECT COUNT(*) AS n FROM job_budget_reservations WHERE status='held'"
        )["n"] == prefix["held_budget_reservations"]
        assert _count(db, "budget_reservation_events", "held") == prefix["intents"]
        assert _count(db, "shot_job_events", "generation_intent_recorded") == prefix["intents"]
        assert _count(db, "shot_job_events", "provider_task_recorded") == prefix["tasks"]
        assert _count(db, "pr31_native_job_fence_events", "fenced_hold_and_intent") == prefix["intents"]
        assert _count(db, "pr31_native_job_fence_events", "fenced_synthetic_task_bound") == prefix["tasks"]
        assert _count(db, "pr31_native_job_fence_events", "pause") == prefix["pause_events"]
        assert _count(db, "pr31_native_job_fence_events", "resume") == prefix["resume_events"]
        assert db.one(
            "SELECT COUNT(*) AS n FROM shot_jobs WHERE status='submission_intent'"
        )["n"] == prefix["intents"] - prefix["tasks"]
        assert db.one(
            "SELECT COUNT(*) AS n FROM shot_jobs WHERE status='submitted'"
        )["n"] == prefix["tasks"]
        assert db.one(
            "SELECT COUNT(*) AS n FROM job_budget_reservations"
        )["n"] <= 1

    assert expected["remote_multi_runner_verified"] is False
    assert expected["paid_provider_calls"] == 0
    assert db.safety_metadata()["remote_concurrency_verified"] is False


@pytest.mark.parametrize(
    "operations",
    list(permutations(("intent_a", "intent_b", "task_a", "pause"))),
)
def test_each_of_24_orderings_matches_real_native_sdk_ledger(client, operations):
    _test_one_real_schedule(client, operations)


@pytest.mark.parametrize("operations", [
    ("pause", "resume", "intent_a", "intent_b", "task_a", "task_b"),
    ("intent_a", "task_a", "pause", "resume", "intent_b", "task_b"),
    ("intent_b", "task_b", "pause", "resume", "intent_a", "task_a"),
    ("resume", "intent_a", "task_a", "pause", "intent_b", "task_b"),
    ("task_b", "intent_b", "task_a", "intent_a", "pause", "resume"),
    ("intent_b", "intent_a", "pause", "task_b", "resume", "task_a"),
])
def test_adversarial_resume_and_task_orders_match_sdk(client, operations):
    _test_one_real_schedule(client, operations)
