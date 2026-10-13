"""PR-31b2d: pure offline decision boundary for an observed BEGIN lock failure.

No remote calls and NO automatic retry. Production never imports this module.
A future remote Worker may only implement the decision after confirming the
server rejected BEGIN before a transaction was started or charged.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryDecision:
    may_retry_pre_begin: bool
    review_required: bool
    reason: str
    maximum_additional_attempts: int


def assess_txlab_retry(
    *,
    stage: str,
    error_category: str,
    begin_definitively_rejected: bool,
    write_sql_executed: bool,
    prior_retry_attempts: int,
) -> RetryDecision:
    """Return a bounded policy *proposal*, never actually call a provider/DB.

    An exception at BEGIN is not by itself enough to establish that the remote
    side never accepted the transaction: the caller must independently know
    that the server definitively rejected it with SQLITE_BUSY.
    """
    if type(prior_retry_attempts) is not int or prior_retry_attempts < 0:
        return RetryDecision(False, True, "invalid_attempt_counter", 0)
    if stage != "worker_begin":
        return RetryDecision(False, True, "transaction_or_commit_uncertain", 0)
    if error_category != "busy":
        return RetryDecision(False, True, "not_confirmed_lock_busy", 0)
    if begin_definitively_rejected is not True or write_sql_executed is not False:
        return RetryDecision(False, True, "begin_outcome_not_proven_safe", 0)
    if prior_retry_attempts >= 1:
        return RetryDecision(False, True, "bounded_retry_limit_reached", 0)
    return RetryDecision(True, False, "only_known_rejected_begin_can_retry", 1)
