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


