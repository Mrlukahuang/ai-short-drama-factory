"""PR-10i: actual local durable one-attempt TTS orchestration under Fake SDK."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from drama_factory.jobs.budgets import configure_policy
from drama_factory.jobs.tts_intents import (
    list_tts_task_events, prepare_tts_task, reserve_tts_task_budget,
    commit_tts_submission_intent, quarantine_tts_unknown_ack,
)
from drama_factory.jobs.tts_fake_dispatch import (
    OfflineFakeGeminiTransport, OfflineTtsDispatchDenied,
    execute_offline_fake_tts_once,
)
from drama_factory.providers.gemini_tts_contract import GeminiTtsPreparation
from test_gemini_tts_contract import _approved_spec


def _ready(client):
    db, spec, voices, actors = _approved_spec(client)
    control = GeminiTtsPreparation(
        consent_reviewed_by_operator=True,
        max_acknowledged_spend_usd="0.04",
    )
    task = prepare_tts_task(db, spec, control)
    col = db.one("SELECT column_id FROM projects WHERE id=?", (spec.series_id,))["column_id"]
    for name, value in (
        ("column", col), ("series", spec.series_id), ("provider", "google"),
    ):
        configure_policy(
            db, name, value, daily_limit_usd="0.12",
            max_active_jobs=4,
        )
    reserve_tts_task_budget(db, task["id"], estimated_charge_usd="0.03")
    return db, spec, control, task["id"], voices, actors


def _state(db, task_id):
    task = db.one("SELECT * FROM tts_tasks WHERE id=?", (task_id,))
    hold = db.one("SELECT * FROM tts_budget_reservations WHERE task_id=?", (task_id,))
    events = list_tts_task_events(db, task_id)
    return task, hold, events


def test_exact_fake_one_request_produces_durable_unique_ack_validated_pcm(client):
    db, spec, control, task, _, _ = _ready(client)
    fake = OfflineFakeGeminiTransport()
    done = execute_offline_fake_tts_once(db, task, spec, control, fake)
    assert fake.calls == 1
    assert done["task_status"] == "verified"
    assert done["provider_interaction_recorded"] is True
    assert done["wav_receipt_recorded"] is True
    assert done["actual_paid_provider_calls"] == 0
    assert done["publish_approved"] is False
    assert done["vendor_hard_spend_cap_verified"] is False
    assert done["automated_retry_allowed"] is False
    assert "Hello" not in str(done)
    assert "Hello" not in repr(fake)
    row, hold, events = _state(db, task)
    assert row["status"] == "verified" and row["interaction_id"]
    assert row["output_sha256"] == done["wav_sha256"]
    assert hold["status"] == "held"  # No invented real vendor invoice
    assert [x["action"] for x in events] == [
        "prepared_offline", "budget_held", "paid_intent_committed",
        "interaction_id_recorded", "format_verified_not_speech_reviewed",
    ]
    with pytest.raises(OfflineTtsDispatchDenied):
        execute_offline_fake_tts_once(
            db, task, spec, control, OfflineFakeGeminiTransport(),
        )
    assert db.one("SELECT COUNT(*) AS n FROM tts_task_events WHERE task_id=? AND action='paid_intent_committed'",
                  (task,))["n"] == 1


@pytest.mark.parametrize("mode", ["ack_lost", "bad_interaction_id"])
def test_ambiguous_outcome_quarantines_holds_and_never_retries(client, mode):
    db, spec, control, task, _, _ = _ready(client)
    fake = OfflineFakeGeminiTransport(fail_mode=mode)
    with pytest.raises(OfflineTtsDispatchDenied, match="no retry") as exc:
        execute_offline_fake_tts_once(db, task, spec, control, fake)
    assert fake.calls == 1
    assert "Hello" not in str(exc.value)
    assert "private dialogue" not in str(exc.value)
    row, hold, events = _state(db, task)
    assert row["status"] == "quarantined"
    assert row["interaction_id"] is None
    assert hold["status"] == "held"
    assert [x["action"] for x in events][-2:] == [
        "paid_intent_committed", "unknown_ack_quarantined",
    ]
    with pytest.raises(OfflineTtsDispatchDenied):
        execute_offline_fake_tts_once(
            db, task, spec, control, OfflineFakeGeminiTransport(),
        )


def test_bad_wav_after_valid_ack_keeps_interaction_and_hold(client):
    db, spec, control, task, _, _ = _ready(client)
    fake = OfflineFakeGeminiTransport(fail_mode="invalid_wav")
    with pytest.raises(OfflineTtsDispatchDenied, match="WAV invalid"):
        execute_offline_fake_tts_once(db, task, spec, control, fake)
    assert fake.calls == 1
    row, hold, events = _state(db, task)
    assert row["status"] == "acknowledged"
    assert row["interaction_id"] == "synthetic-fake-interaction"
    assert row["output_sha256"] is None
    assert hold["status"] == "held"
    assert [x["action"] for x in events][-2:] == [
        "paid_intent_committed", "interaction_id_recorded",
    ]
    with pytest.raises(OfflineTtsDispatchDenied):
        execute_offline_fake_tts_once(db, task, spec, control, OfflineFakeGeminiTransport())


def test_wrong_voice_or_new_model_fails_before_consuming_intent(client):
    db, spec, control, task, mapping, actors = _ready(client)
    bad_control = control.model_copy(update={"prebuilt_voice": "Puck"})
    bad_spec = spec.model_copy(update={"voice_asset_id": mapping[actors[1]]})
    for wrong_spec, wrong_control in (
        (spec, bad_control), (bad_spec, control),
    ):
        fake = OfflineFakeGeminiTransport()
        with pytest.raises((OfflineTtsDispatchDenied, ValueError)):
            execute_offline_fake_tts_once(
                db, task, wrong_spec, wrong_control, fake,
            )
        assert fake.calls == 0
        row, hold, events = _state(db, task)
        assert row["status"] == "prepared" and hold["status"] == "held"
        assert len(events) == 2


def test_no_hold_no_dispatch_and_only_exact_fake_transport(client):
    db, spec, control, task, _, _ = _ready(client)
    db.exec("DELETE FROM tts_budget_reservations WHERE task_id=?", (task,))
    fake = OfflineFakeGeminiTransport()
    with pytest.raises(OfflineTtsDispatchDenied, match="hold"):
        execute_offline_fake_tts_once(db, task, spec, control, fake)
    assert fake.calls == 0
    with pytest.raises(OfflineTtsDispatchDenied, match="exact offline Fake"):
        execute_offline_fake_tts_once(db, task, spec, control, object())
    class Impersonator(OfflineFakeGeminiTransport):
        pass
    with pytest.raises(OfflineTtsDispatchDenied):
        execute_offline_fake_tts_once(db, task, spec, control, Impersonator())
    assert db.one("SELECT status FROM tts_tasks WHERE id=?", (task,))["status"] == "prepared"


def test_threads_race_only_one_durable_intent_and_fake_submission(client):
    db, spec, control, task, _, _ = _ready(client)
    clients = [OfflineFakeGeminiTransport(), OfflineFakeGeminiTransport()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(execute_offline_fake_tts_once, db, task, spec, control, f)
            for f in clients
        ]
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except OfflineTtsDispatchDenied:
                results.append({"blocked": True})
    assert sum(x.calls for x in clients) == 1
    assert sum(x.get("task_status") == "verified" for x in results) == 1
    assert sum(x.get("blocked", False) for x in results) == 1
    row, hold, events = _state(db, task)
    assert row["status"] == "verified"
    assert hold["status"] == "held"
    assert len([e for e in events if e["action"] == "paid_intent_committed"]) == 1


def test_existing_provider_id_another_cue_is_quarantined_and_not_overwritten(client):
    db, spec, control, task, mapping, actors = _ready(client)
    first = execute_offline_fake_tts_once(
        db, task, spec, control, OfflineFakeGeminiTransport(
            simulated_interaction_id="synthetic-shared-id",
        ),
    )
    assert first["task_status"] == "verified"
    second = spec.model_copy(update={
        "cue_index": 1, "speaker_actor_id": actors[1],
        "voice_asset_id": mapping[actors[1]],
        "dialogue_text": f"{actors[1]}: Welcome",
    })
    second_task = prepare_tts_task(db, second, control)
    reserve_tts_task_budget(db, second_task["id"], estimated_charge_usd="0.03")
    fake = OfflineFakeGeminiTransport(
        simulated_interaction_id="synthetic-shared-id",
    )
    with pytest.raises(OfflineTtsDispatchDenied, match="no retry"):
        execute_offline_fake_tts_once(
            db, second_task["id"], second, control, fake,
        )
    assert fake.calls == 1
    row, hold, events = _state(db, second_task["id"])
    assert row["status"] == "quarantined"
    assert row["interaction_id"] is None
    assert hold["status"] == "held"
    assert db.one("SELECT COUNT(*) AS n FROM tts_tasks WHERE interaction_id=?",
                  ("synthetic-shared-id",))["n"] == 1
