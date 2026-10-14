"""PR-31b2o2: pure per-claim fencing precheck; NOT a production gate."""
from datetime import datetime, timedelta, timezone

import pytest

from drama_factory.storage.pr31_claim_fencing_contract import (
    FenceContractDenied, assess_claim_fence,
)


NOW = datetime(2026, 10, 14, 2, tzinfo=timezone.utc)


def _claim(**overrides):
    args = dict(
        candidate_worker="shared-name",
        acquired_attempt=2,
        acquired_epoch=4,
        stored_worker="shared-name",
        stored_attempt=2,
        stored_lease_expires_at=(NOW + timedelta(minutes=2)).isoformat(),
        stored_status="leased",
        stored_generation_intent=False,
        durable_epoch=4,
        durable_gate_state="running",
        now=NOW,
    )
    args.update(overrides)
    return assess_claim_fence(**args)


def test_valid_claim_is_only_a_precheck_not_write_authority():
    report = _claim()
    assert report["decision"] == "candidate_requires_atomic_cas"
    assert report["candidate_requires_atomic_cas"] is True
    assert report["authorizes_db_mutation"] is False
    assert report["authorizes_paid_provider_call"] is False
    assert report["cross_runner_enforced"] is False


@pytest.mark.parametrize("changes,expected", [
    ({"acquired_attempt": 1}, "stale_claim_token"),
    # Same Worker name after a second claim must not revive old claim.
    ({"stored_attempt": 3}, "stale_claim_token"),
    ({"stored_worker": "new-owner"}, "stale_claim_token"),
    ({"durable_epoch": 5}, "stale_writer_epoch"),
    ({"durable_gate_state": "paused"}, "writer_gate_not_running"),
    ({"stored_lease_expires_at": NOW.isoformat()}, "expired_lease"),
    ({"stored_lease_expires_at": (NOW - timedelta(seconds=1)).isoformat()}, "expired_lease"),
    ({"stored_lease_expires_at": "not-a-timestamp"}, "invalid_lease"),
    ({"stored_lease_expires_at": None}, "missing_lease"),
    ({"stored_status": "submission_intent"}, "unsafe_job_state"),
    ({"stored_generation_intent": True}, "unsafe_job_state"),
])
def test_stale_or_unsafe_claim_fails_closed(changes, expected):
    report = _claim(**changes)
    assert report["decision"] == expected
    assert report["candidate_requires_atomic_cas"] is False
    assert not report["authorizes_db_mutation"]
    assert not report["authorizes_paid_provider_call"]


@pytest.mark.parametrize("changes", [
    {"acquired_attempt": True},
    {"acquired_epoch": 0},
    {"durable_epoch": -1},
    {"stored_attempt": 2.0},
    {"now": NOW.replace(tzinfo=None)},
])
def test_invalid_token_or_clock_denied(changes):
    with pytest.raises(FenceContractDenied):
        _claim(**changes)
