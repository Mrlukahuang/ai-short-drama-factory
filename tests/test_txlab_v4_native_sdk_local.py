"""Execute the exact v4 single-use contract on libsql==0.1.11 LOCAL FILES.

The dedicated GitHub CI job explicitly selects this test; zero secrets/network.
"""
from __future__ import annotations

import pytest

from drama_factory.storage.txlab_v4_isolated_canary import (
    V4StageFailure, run_v4_contract,
)

libsql = pytest.importorskip("libsql")


def _factory(path):
    def factory():
        assert "://" not in str(path)
        return libsql.connect(database=str(path), timeout=15.0)
    return factory


def test_real_pinned_sdk_executes_identical_v4_candidate_on_temp_file(tmp_path):
    path = tmp_path / "strictly-local-v4-sdk.sqlite"
    result = run_v4_contract(_factory(path))
    assert result["schema_objects_verified"] == 22
    assert result["synthetic_claim_intent_task_atomic"] is True
    assert result["rollback_and_independent_readback_verified"] is True
    assert result["local_or_serial_epoch_pause_verified"] is True
    assert result["remote_multiworker_concurrency_verified"] is False
    assert result["full_production_schema_verified"] is False
    assert result["isolated_v4_lab_verified"] is False
    assert result["paid_provider_calls"] == 0
    assert result["live_cutover_permitted"] is False
    reader = libsql.connect(database=str(path), timeout=15.0)
    try:
        assert reader.execute(
            "SELECT status FROM pr31_v4_shot_jobs"
        ).fetchone()[0] == "submitted"
        assert reader.execute(
            "SELECT state,epoch FROM pr31_v4_gate WHERE id=1"
        ).fetchone() == ("paused", 2)
        assert reader.execute(
            "SELECT COUNT(*) FROM pr31_v4_shot_job_events"
        ).fetchone()[0] == 3
    finally:
        reader.close()


def test_real_sdk_v4_second_run_fails_closed_no_duplicate_receipt(tmp_path):
    path = tmp_path / "local-v4-no-replay.sqlite"
    factory = _factory(path)
    run_v4_contract(factory)
    with pytest.raises(V4StageFailure) as exc:
        run_v4_contract(factory)
    assert exc.value.stage == "preflight"
    reader = libsql.connect(database=str(path), timeout=15.0)
    try:
        assert reader.execute(
            "SELECT COUNT(*) FROM pr31_v4_budget_reservation_events"
        ).fetchone()[0] == 1
        assert reader.execute(
            "SELECT COUNT(*) FROM pr31_v4_gate_events"
        ).fetchone()[0] == 2
    finally:
        reader.close()
