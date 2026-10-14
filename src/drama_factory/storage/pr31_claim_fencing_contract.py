"""PR-31b2o2: pure, deny-by-default cross-Runner fencing candidate contract.

No database connection, no changes to the live Worker, no Provider calls.
PR-31c2 already tests a *separate* local persistent epoch simulator. This
contract defines the per-claim tuple that a future shared durable backend must
check ATOMICALLY in each mutation (never just at Worker start).
"""
from __future__ import annotations

from datetime import datetime, timezone


class FenceContractDenied(ValueError):
    pass


def assess_claim_fence(
    *,
    candidate_worker: str,
    acquired_attempt: int,
    acquired_epoch: int,
    stored_worker: str | None,
    stored_attempt: int,
    stored_lease_expires_at: str | None,
    stored_status: str,
    stored_generation_intent: bool,
    durable_epoch: int,
    durable_gate_state: str,
    now: datetime,
) -> dict:
    """Only 'candidate_requires_atomic_cas' is a passing *precheck*.

    The result NEVER authorizes a write, lease renewal or paid API request.
    A future SQL mutation must combine the tuple comparison, lease deadline,
    running gate epoch and audit append in ONE committed transaction.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise FenceContractDenied("Timezone-aware time required")
    for n in (acquired_attempt, acquired_epoch, stored_attempt, durable_epoch):
        if type(n) is not int or n < 1:
            raise FenceContractDenied("Positive integer attempt/epoch required")

    reason = "candidate_requires_atomic_cas"
    if durable_gate_state != "running":
        reason = "writer_gate_not_running"
    elif acquired_epoch != durable_epoch:
        reason = "stale_writer_epoch"
    elif (
        not isinstance(candidate_worker, str) or not candidate_worker
        or candidate_worker != stored_worker or acquired_attempt != stored_attempt
    ):
        reason = "stale_claim_token"
    elif stored_status != "leased" or stored_generation_intent is not False:
        reason = "unsafe_job_state"
    elif not stored_lease_expires_at:
        reason = "missing_lease"
    else:
        try:
            expiry = datetime.fromisoformat(stored_lease_expires_at)
            if expiry.tzinfo is None or expiry.utcoffset() is None:
                raise ValueError("naive lease")
            if expiry.astimezone(timezone.utc) <= now.astimezone(timezone.utc):
                reason = "expired_lease"
        except (TypeError, ValueError, OverflowError):
            reason = "invalid_lease"

    return {
        "decision": reason,
        "candidate_requires_atomic_cas": reason == "candidate_requires_atomic_cas",
        "authorizes_db_mutation": False,
        "authorizes_paid_provider_call": False,
        "cross_runner_enforced": False,
        "production_worker_modified": False,
    }
