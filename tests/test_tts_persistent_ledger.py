"""PR-10g: persistent, local-only per-cue TTS cost and ACK-loss fencing."""
from __future__ import annotations

import concurrent.futures
import hashlib
import sqlite3
from decimal import Decimal

import pytest

from drama_factory.jobs.budgets import (
    BudgetDenied, configure_policy, reserve_job_budget,
)
from drama_factory.jobs.shots import claim_next_job, prepare_shot_jobs
from drama_factory.jobs.tts_intents import (
    TtsLedgerDenied, acknowledge_tts_provider_interaction,
    commit_tts_submission_intent, list_tts_task_events,
    prepare_tts_task, quarantine_tts_unknown_ack,
    record_offline_verified_tts_wav, record_tts_vendor_charge,
    reserve_tts_task_budget,
)
from drama_factory.providers.gemini_tts_contract import (
    GeminiTtsPreparation, inspect_gemini_tts_unary_response,
)
from test_gemini_tts_contract import _approved_spec, _fake_gemini_unary_wav


def _policies(db, series, *, limit="0.05", concurrency=1):
    column = db.one("SELECT column_id FROM projects WHERE id=?", (series,))["column_id"]
    for kind, key in (
        ("column", column), ("series", series), ("provider", "google"),
    ):
        configure_policy(db, kind, key, daily_limit_usd=limit,
                         max_active_jobs=concurrency)


def _prepared(client, *, limit="0.05", concurrency=1):
    db, spec, _, _ = _approved_spec(client, timed=True)
    control = GeminiTtsPreparation(
        consent_reviewed_by_operator=True,
        max_acknowledged_spend_usd="0.04",
    )
    task = prepare_tts_task(db, spec, control)
    _policies(db, spec.series_id, limit=limit, concurrency=concurrency)
    return db, spec, control, task


def test_immutable_reviewed_task_redacted_without_private_dialogue(client):
    db, spec, control, task = _prepared(client)
    assert task["status"] == "prepared"
    assert task["submitted_to_provider_by_this_module"] is False
    assert task["automated_retry_allowed"] is False
    assert task["publish_approved"] is False
    assert task["request_sha256"] == prepare_tts_task(db, spec, control)["request_sha256"]
    assert "Hello" not in str(task)
    assert "Hello" not in str(db.many("SELECT * FROM tts_tasks"))
    changed = control.model_copy(update={"prebuilt_voice": "Puck"})
    with pytest.raises(TtsLedgerDenied, match="immutable"):
        prepare_tts_task(db, spec, changed)
    assert len(db.many("SELECT id FROM tts_tasks")) == 1


def test_no_current_budget_or_scope_policy_blocks_intent(client):
    db, spec, control, task = _prepared(client)
    with pytest.raises(TtsLedgerDenied, match="Current held"):
        commit_tts_submission_intent(db, task["id"])
    held = reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.03")
    assert held["status"] == "held"
    assert held["real_provider_hard_cap"] is False
    assert held["reserved_usd"] == "0.03"
    assert reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.03") == held
    with pytest.raises(TtsLedgerDenied, match="immutable"):
        reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.02")
    committed = commit_tts_submission_intent(db, task["id"])
    assert committed["status"] == "submission_intent"
    assert committed["automated_retry_allowed"] is False
    for action in (
        lambda: commit_tts_submission_intent(db, task["id"]),
        lambda: reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.03"),
    ):
        with pytest.raises(TtsLedgerDenied):
            action()
    assert not any("Hello" in str(x) for x in list_tts_task_events(db, task["id"]))


def test_unknown_provider_ack_quarantines_and_keeps_held_money(client):
    db, _, _, task = _prepared(client)
    reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.03")
    commit_tts_submission_intent(db, task["id"])
    value = quarantine_tts_unknown_ack(db, task["id"])
    assert value["status"] == "quarantined"
    assert value["provider_interaction_recorded"] is False
    with pytest.raises(TtsLedgerDenied):
        acknowledge_tts_provider_interaction(db, task["id"], "interaction-one")
    with pytest.raises(TtsLedgerDenied):
        quarantine_tts_unknown_ack(db, task["id"])
    held = db.one("SELECT * FROM tts_budget_reservations WHERE task_id=?", (task["id"],))
    assert held["status"] == "held"
    charge = record_tts_vendor_charge(
        db, task["id"], amount_usd="0.04",
        evidence_reference="invoice-offline-manually-entered", reviewer="qa-auditor",
    )
    assert charge["status"] == "reconciled"
    assert charge["retry_allowed"] is False
    assert charge["vendor_invoice_independently_verified"] is False
    assert db.one("SELECT status FROM tts_tasks WHERE id=?", (task["id"],))["status"] == "quarantined"
    with pytest.raises(TtsLedgerDenied):
        record_tts_vendor_charge(db, task["id"], amount_usd="0.03",
                                 evidence_reference="another-evidence",reviewer="user")


def test_acknowledge_single_provider_interaction_and_verify_fake_wav_format(client):
    db, _, _, task = _prepared(client)
    reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.03")
    commit_tts_submission_intent(db, task["id"])
    assert acknowledge_tts_provider_interaction(
        db, task["id"], "fake-interaction-one",
    )["status"] == "acknowledged"
    with pytest.raises(TtsLedgerDenied):
        acknowledge_tts_provider_interaction(db, task["id"], "fake-interaction-one")
    inspected = inspect_gemini_tts_unary_response(_fake_gemini_unary_wav(), 1)
    result = record_offline_verified_tts_wav(db, task["id"], inspected)
    assert result["status"] == "verified"
    assert result["wav_receipt_recorded"] is True
    assert result["publish_approved"] is False
    assert result["submitted_to_provider_by_this_module"] is False
    with pytest.raises(TtsLedgerDenied):
        record_offline_verified_tts_wav(db, task["id"], inspected)
    assert db.one("SELECT output_sha256 FROM tts_tasks WHERE id=?", (task["id"],))["output_sha256"] == inspected.sha256
    assert len(list_tts_task_events(db, task["id"])) == 5


def test_shared_provider_budget_cannot_be_used_twice_by_tts_and_video(client):
    db, spec, _, task = _prepared(client, limit="0.05", concurrency=5)
    reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.04")
    # Existing video budget path must now notice the TTS hold under the SAME
    # project, default Column and google Provider policies.
    jobs = prepare_shot_jobs(
        db, spec.production_id, provider="google",
        max_acknowledged_spend_usd="0.05",
    )
    video = claim_next_job(db, "video-worker", production_id=spec.production_id)
    assert video is not None and video["id"] in {x["id"] for x in jobs}
    with pytest.raises(BudgetDenied, match="daily budget"):
        reserve_job_budget(db, video["id"], estimated_charge_usd="0.02")
    assert reserve_job_budget(db, video["id"], estimated_charge_usd="0.01")["reserved_usd"] == "0.01"


def test_tts_budget_checks_existing_video_hold(client):
    db, spec, _, task = _prepared(client, limit="0.05", concurrency=5)
    prepare_shot_jobs(db, spec.production_id, provider="google",
                      max_acknowledged_spend_usd="0.05")
    video = claim_next_job(db, "video-worker", production_id=spec.production_id)
    reserve_job_budget(db, video["id"], estimated_charge_usd="0.04")
    with pytest.raises(BudgetDenied):
        reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.02")
    assert reserve_tts_task_budget(
        db, task["id"], estimated_charge_usd="0.01",
    )["reserved_usd"] == "0.01"


def test_two_threads_cannot_double_reserve_or_double_commit(client):
    db, spec, control, task = _prepared(client, limit="0.05", concurrency=1)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(reserve_tts_task_budget, db, task["id"],
                               estimated_charge_usd="0.03") for _ in range(2)]
        results = [f.result() for f in futures]
    assert results[0]["id"] == results[1]["id"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(commit_tts_submission_intent, db, task["id"]) for _ in range(2)]
        outcomes=[]
        for f in futures:
            try:
                outcomes.append(f.result()["status"])
            except TtsLedgerDenied:
                outcomes.append("blocked")
    assert sorted(outcomes) == ["blocked", "submission_intent"]
    assert db.one("SELECT COUNT(*) AS n FROM tts_task_events WHERE task_id=? AND action='paid_intent_committed'",
                  (task["id"],))["n"] == 1


def test_tts_event_log_is_database_immutable(client):
    db, _, _, task = _prepared(client)
    event = db.one("SELECT id FROM tts_task_events WHERE task_id=?", (task["id"],))["id"]
    with pytest.raises(sqlite3.DatabaseError):
        db.exec("UPDATE tts_task_events SET action='forged' WHERE id=?", (event,))
    with pytest.raises(sqlite3.DatabaseError):
        db.exec("DELETE FROM tts_task_events WHERE id=?", (event,))
    assert db.one("SELECT COUNT(*) AS n FROM tts_task_events WHERE task_id=?", (task["id"],))["n"] == 1
