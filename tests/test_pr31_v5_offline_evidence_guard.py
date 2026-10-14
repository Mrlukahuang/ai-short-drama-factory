"""PR-31c3d: proposed future v5 evidence MUST NOT grant remote rights."""
from __future__ import annotations

from copy import deepcopy

import pytest

from drama_factory.storage.pr31_v5_offline_evidence_guard import (
    V5EvidenceDenied, inspect_proposed_v5_evidence,
)


def _example():
    nonce = "d" * 64
    return {
        "experiment": "pr31_v5_isolated_synthetic_only",
        "namespace": "pr31_v5_",
        "actors": [
            {
                "role": "a", "github_run_id": 77, "github_job_id": 1001,
                "run_attempt": 1, "nonce_sha256": nonce,
                "backend": "isolated_turso_remote", "outcome": "accepted",
            },
            {
                "role": "b", "github_run_id": 77, "github_job_id": 1002,
                "run_attempt": 1, "nonce_sha256": nonce,
                "backend": "isolated_turso_remote", "outcome": "denied",
            },
        ],
        "observer": {
            "github_run_id": 77, "github_job_id": 1003, "run_attempt": 1,
            "nonce_sha256": nonce, "backend": "isolated_turso_remote",
            "read_only_connection": True, "gate_state": "paused",
            "gate_epoch": 2, "held_rows": 1, "intent_audits": 1,
            "gate_audits": 1, "stale_token_writes": 0,
            "duplicate_task_bindings": 0, "foreign_keys_ok": True,
            "unknown_commit": False, "provider_api_calls": 0,
        },
    }


def test_formally_consistent_synthetic_receipt_still_does_not_prove_two_runners():
    example = _example()
    original = deepcopy(example)
    receipt = inspect_proposed_v5_evidence(example)
    assert example == original  # never mutates supplied evidence
    assert receipt["proposed_receipt_shape_consistent"] is True
    assert receipt["operator_must_check_github_job_provenance"] is True
    assert receipt["operator_must_check_independent_remote_sql"] is True
    assert receipt["remote_multi_runner_verified"] is False
    assert receipt["remote_fencing_verified"] is False
    assert receipt["may_authorize_another_remote_test"] is False
    assert receipt["may_resume_production"] is False
    assert receipt["live_cutover_permitted"] is False
    assert receipt["provider_api_calls"] == 0
    assert receipt["remote_txlab_write_calls"] == 0
    assert "d" * 64 not in str(receipt)
    assert "1001" not in str(receipt)


@pytest.mark.parametrize("path,value", [
    (("experiment",), "other"),
    (("namespace",), "shot_jobs"),
    (("actors", 0, "role"), "b"),
    (("actors", 0, "role"), ["a"]),
    (("actors", 0, "outcome"), "unknown"),
    (("actors", 0, "outcome"), {"status": "accepted"}),
    (("actors", 1, "outcome"), "accepted"),
    (("actors", 0, "run_attempt"), 2),
    (("actors", 0, "run_attempt"), True),
    (("actors", 1, "github_run_id"), 78),
    (("actors", 1, "github_job_id"), 1001),
    (("actors", 1, "github_job_id"), True),
    (("actors", 0, "backend"), "native_local_sdk_only"),
    (("actors", 0, "nonce_sha256"), "bad"),
    (("actors", 0, "nonce_sha256"), "a" * 64),
    (("observer", "nonce_sha256"), "1" * 64),
    (("observer", "github_job_id"), 1002),
    (("observer", "github_run_id"), 89),
    (("observer", "run_attempt"), 2),
    (("observer", "backend"), "fake"),
    (("observer", "read_only_connection"), False),
    (("observer", "read_only_connection"), 1),
    (("observer", "gate_state"), "running"),
    (("observer", "gate_epoch"), 1),
    (("observer", "gate_epoch"), True),
    (("observer", "held_rows"), 2),
    (("observer", "held_rows"), True),
    (("observer", "intent_audits"), 0),
    (("observer", "gate_audits"), 0),
    (("observer", "stale_token_writes"), 1),
    (("observer", "duplicate_task_bindings"), 1),
    (("observer", "foreign_keys_ok"), False),
    (("observer", "foreign_keys_ok"), 1),
    (("observer", "unknown_commit"), True),
    (("observer", "provider_api_calls"), 1),
])
def test_mismatched_job_provenance_unknown_commit_or_missing_sql_audit_is_denied(path, value):
    example = _example()
    node = example
    for segment in path[:-1]:
        node = node[segment]
    node[path[-1]] = value
    with pytest.raises(V5EvidenceDenied):
        inspect_proposed_v5_evidence(example)


@pytest.mark.parametrize("placement", [
    "bundle_extra", "actor_extra", "observer_extra", "actor_missing",
    "observer_missing", "single_runner", "three_runners", "not_dictionary",
])
def test_extra_payloads_secret_like_fields_or_missing_sources_are_denied(placement):
    candidate = _example()
    if placement == "bundle_extra":
        candidate["PRIVATE_REAL_PROVIDER_TOKEN"] = "must never appear"
    elif placement == "actor_extra":
        candidate["actors"][0]["raw_task_id"] = "PRIVATE_REAL_TASK"
    elif placement == "observer_extra":
        candidate["observer"]["database_url"] = "libsql://SECRET"
    elif placement == "actor_missing":
        del candidate["actors"][1]["backend"]
    elif placement == "observer_missing":
        del candidate["observer"]["foreign_keys_ok"]
    elif placement == "single_runner":
        candidate["actors"] = [candidate["actors"][0]]
    elif placement == "three_runners":
        candidate["actors"].append(deepcopy(candidate["actors"][0]))
    elif placement == "not_dictionary":
        candidate = ["PRIVATE_SECRET"]
    with pytest.raises(V5EvidenceDenied) as e:
        inspect_proposed_v5_evidence(candidate)
    assert "PRIVATE" not in str(e.value)
    assert "SECRET" not in str(e.value)
    assert "libsql://" not in str(e.value)
