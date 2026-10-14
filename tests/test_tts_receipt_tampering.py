"""PR-10h: final ledger write MUST independently decode local WAV payload."""
from __future__ import annotations

import base64
import hashlib

import pytest

from drama_factory.jobs.tts_intents import (
    TtsLedgerDenied, prepare_tts_task, reserve_tts_task_budget,
    commit_tts_submission_intent, acknowledge_tts_provider_interaction,
    record_offline_verified_tts_wav,
)
from drama_factory.providers.gemini_tts_contract import (
    GeminiTtsPreparation, InspectedGeminiSpeech,
    inspect_gemini_tts_unary_response,
)
from test_gemini_tts_contract import _approved_spec, _fake_gemini_unary_wav


def _acknowledged(client):
    db, spec, mapping, actors = _approved_spec(client)
    control = GeminiTtsPreparation(
        max_acknowledged_spend_usd="0.04",
        consent_reviewed_by_operator=True,
    )
    task = prepare_tts_task(db, spec, control)
    # Reuse same budget policy plumbing as the real approved voice tests.
    from drama_factory.jobs.budgets import configure_policy
    column = db.one("SELECT column_id FROM projects WHERE id=?", (spec.series_id,))["column_id"]
    for scope, scope_id in (("column", column), ("series", spec.series_id),
                            ("provider", "google")):
        configure_policy(db, scope, scope_id, daily_limit_usd="0.10", max_active_jobs=3)
    reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.03")
    commit_tts_submission_intent(db, task["id"])
    acknowledge_tts_provider_interaction(db, task["id"], "existing-mock-interaction")
    return db, spec, control, task, mapping, actors


@pytest.mark.parametrize("corruption", ["not_a_wav", "wrong_sample_rate",
                                        "wrong_duration", "fake_result_duration"])
def test_malicious_dataclass_cannot_bypass_actual_pcm_decoding(client, corruption):
    db, spec, control, task, _, _ = _acknowledged(client)
    if corruption == "not_a_wav":
        payload = b"fake-but-hashed-by-attacker"
        stated = 0.75
    elif corruption == "wrong_sample_rate":
        payload = base64.b64decode(_fake_gemini_unary_wav(0.75, 8000))
        stated = 0.75
    elif corruption == "wrong_duration":
        payload = base64.b64decode(_fake_gemini_unary_wav(2.0, 24000))
        stated = 2.0
    else:
        payload = base64.b64decode(_fake_gemini_unary_wav(0.75, 24000))
        stated = 0.66
    # Dataclasses may be constructed by arbitrary callers: SHA256 matching
    # doesn't prove the PCM sample rate, actual frames or approved slot.
    forged = InspectedGeminiSpeech(
        wav_bytes=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
        duration_seconds=stated,
    )
    with pytest.raises(TtsLedgerDenied, match="WAV"):
        record_offline_verified_tts_wav(db, task["id"], forged)
    row = db.one("SELECT status,output_sha256 FROM tts_tasks WHERE id=?", (task["id"],))
    assert row["status"] == "acknowledged"
    assert row["output_sha256"] is None
    assert db.one("SELECT COUNT(*) AS n FROM tts_task_events WHERE task_id=? AND action='format_verified_not_speech_reviewed'",
                  (task["id"],))["n"] == 0


def test_second_voice_cue_cannot_reuse_another_cues_provider_id(client):
    db, first, control, task, mapping, actors = _acknowledged(client)
    # Independent reviewed speaker; its own voice version and exact text.
    second = first.model_copy(update={
        "cue_index": 1, "speaker_actor_id": actors[1],
        "voice_asset_id": mapping[actors[1]],
        "dialogue_text": f"{actors[1]}: Welcome",
    })
    task2 = prepare_tts_task(db, second, control)
    reserve_tts_task_budget(db, task2["id"], estimated_charge_usd="0.03")
    commit_tts_submission_intent(db, task2["id"])
    with pytest.raises(TtsLedgerDenied, match="already bound"):
        acknowledge_tts_provider_interaction(db, task2["id"],
                                             "existing-mock-interaction")
    row = db.one("SELECT status,interaction_id FROM tts_tasks WHERE id=?", (task2["id"],))
    assert row["status"] == "submission_intent" and row["interaction_id"] is None
    assert db.one("SELECT COUNT(*) AS n FROM tts_task_events WHERE task_id=? AND action='interaction_id_recorded'",
                  (task2["id"],))["n"] == 0
    assert acknowledge_tts_provider_interaction(db, task2["id"], "fresh-second-id")["status"] == "acknowledged"


def test_successful_validated_wav_still_records_only_hash(client):
    db, spec, control, task, _, _ = _acknowledged(client)
    report = inspect_gemini_tts_unary_response(_fake_gemini_unary_wav(0.75), 1)
    result = record_offline_verified_tts_wav(db, task["id"], report)
    assert result["status"] == "verified"
    assert result["wav_receipt_recorded"] is True
    assert result["publish_approved"] is False
    assert result["vendor_billing_verified"] is False
    assert result["submitted_to_provider_by_this_module"] is False
    assert "Hello" not in str(result)
