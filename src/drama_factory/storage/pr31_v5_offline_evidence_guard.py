"""PR-31c3d: OFFLINE-only validation of PROPOSED future v5 evidence.

This examines wholly synthetic dictionaries. It has no database connection,
GitHub API, secrets, remote runner, paid model, workflow dispatch or writes.
A syntactically consistent claim is never sufficient to CERTIFY a real
two-Runner experiment: operators must independently review server-side SQL,
Actions job provenance and any ambiguous commit/billing.
"""
from __future__ import annotations

import re


class V5EvidenceDenied(ValueError):
    """Fixed redacted refusal: never interpolate caller-supplied evidence."""


_ACTOR_FIELDS = frozenset({
    "role", "github_run_id", "github_job_id", "run_attempt",
    "nonce_sha256", "backend", "outcome",
})
_OBSERVER_FIELDS = frozenset({
    "github_run_id", "github_job_id", "run_attempt", "nonce_sha256",
    "backend", "read_only_connection", "gate_state", "gate_epoch",
    "held_rows", "intent_audits", "gate_audits", "stale_token_writes",
    "duplicate_task_bindings", "foreign_keys_ok", "unknown_commit",
    "provider_api_calls",
})
_BUNDLE_FIELDS = frozenset({"experiment", "namespace", "actors", "observer"})
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")


def _exact(obj: object, required: frozenset[str]) -> dict:
    if type(obj) is not dict or set(obj) != required:
        raise V5EvidenceDenied("Incomplete or unexpected evidence fields")
    return obj


def _positive_integer(v: object) -> bool:
    return type(v) is int and v > 0


def inspect_proposed_v5_evidence(bundle: dict) -> dict:
    """Check a future two-runner report's *shape*, not its authenticity.

    The return value NEVER authorizes remote SQL, vendor calls, migration,
    cutover, a rerun, a workflow dispatch, or automatic production resume.
    """
    item = _exact(bundle, _BUNDLE_FIELDS)
    if item["experiment"] != "pr31_v5_isolated_synthetic_only" or item["namespace"] != "pr31_v5_":
        raise V5EvidenceDenied("Unrecognized proposed v5 isolation scope")
    actors = item["actors"]
    if type(actors) is not list or len(actors) != 2:
        raise V5EvidenceDenied("Exactly two independent runner receipts required")
    first, second = [_exact(x, _ACTOR_FIELDS) for x in actors]
    observer = _exact(item["observer"], _OBSERVER_FIELDS)

    if {first["role"], second["role"]} != {"a", "b"}:
        raise V5EvidenceDenied("Missing distinct runner roles")

    receipts = (first, second, observer)
    if any(
        not _positive_integer(x["github_job_id"])
        or not _positive_integer(x["github_run_id"])
        or type(x["run_attempt"]) is not int
        or x["run_attempt"] != 1
        or x["backend"] != "isolated_turso_remote"
        or type(x["nonce_sha256"]) is not str
        or _DIGEST.fullmatch(x["nonce_sha256"]) is None
        for x in receipts
    ):
        raise V5EvidenceDenied("Unverified runner provenance or isolation label")
    if len({x["github_run_id"] for x in receipts}) != 1:
        raise V5EvidenceDenied("Evidence must refer to one original Actions run")
    if len({x["github_job_id"] for x in receipts}) != 3:
        raise V5EvidenceDenied("Runner evidence does not have distinct job sources")
    if len({x["nonce_sha256"] for x in receipts}) != 1:
        raise V5EvidenceDenied("Mismatched test batch")
    if sorted([first["outcome"], second["outcome"]]) != ["accepted", "denied"]:
        raise V5EvidenceDenied("Outcome ambiguous or duplicate acceptance")
    if (
        observer["read_only_connection"] is not True
        or observer["gate_state"] != "paused"
        or type(observer["gate_epoch"]) is not int
        or observer["gate_epoch"] < 2
    ):
        raise V5EvidenceDenied("Missing independent paused-gate observation")
    expected_counts = {
        "held_rows": 1,
        "intent_audits": 1,
        "gate_audits": 1,
        "stale_token_writes": 0,
        "duplicate_task_bindings": 0,
        "provider_api_calls": 0,
    }
    if any(
        type(observer[key]) is not int or observer[key] != expected
        for key, expected in expected_counts.items()
    ):
        raise V5EvidenceDenied("Synthetic ledger or audit evidence inconsistent")
    if observer["foreign_keys_ok"] is not True or observer["unknown_commit"] is not False:
        raise V5EvidenceDenied("Unresolved integrity or ambiguous commit")

    # A receipt can be spoofed or produced by a fake backend. Do not treat
    # ANY client-side self-attestation as server-side proof or as authorization.
    return {
        "proposed_receipt_shape_consistent": True,
        "operator_must_check_github_job_provenance": True,
        "operator_must_check_independent_remote_sql": True,
        "operator_must_reconcile_unknown_vendor_side_effects": True,
        "remote_multi_runner_verified": False,
        "remote_fencing_verified": False,
        "remote_txlab_write_calls": 0,
        "provider_api_calls": 0,
        "may_authorize_another_remote_test": False,
        "may_resume_production": False,
        "live_cutover_permitted": False,
    }
