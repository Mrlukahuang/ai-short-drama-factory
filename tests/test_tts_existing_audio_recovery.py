"""PR-10k: recover ONLY existing fake ID audio, no new paid generation."""
from __future__ import annotations

import pytest

from drama_factory.jobs.tts_existing_audio_recovery import (
    OfflineExistingAudioDenied, OfflineFakeExistingAudioReader,
    recover_offline_existing_tts_wav,
)
from drama_factory.jobs.tts_intents import (
    acknowledge_tts_provider_interaction,
    commit_tts_submission_intent,
    quarantine_tts_unknown_ack,
    list_tts_task_events,
)
from test_tts_fake_dispatch import _ready


def _acknowledged(client):
    db, spec, control, task, _, _ = _ready(client)
    commit_tts_submission_intent(db, task)
    acknowledge_tts_provider_interaction(db, task, "original-interaction-one")
    return db, task


def _read_state(db, task):
    return (
        db.one("SELECT * FROM tts_tasks WHERE id=?", (task,)),
        db.one("SELECT * FROM tts_budget_reservations WHERE task_id=?", (task,)),
        list_tts_task_events(db, task),
    )


def test_existing_id_recover_valid_original_wav_never_submits_again(client):
    db, task = _acknowledged(client)
    reader = OfflineFakeExistingAudioReader("original-interaction-one")
    result = recover_offline_existing_tts_wav(db, task, reader)
    assert result["task_status"] == "verified"
    assert result["provider_interaction_recorded"] is True
    assert result["wav_receipt_recorded"] is True
    assert result["existing_interaction_reads"] == 1
    assert result["new_tts_generation_attempts"] == 0
    assert result["actual_paid_provider_calls"] == 0
    assert result["publish_approved"] is False
    assert result["vendor_invoice_independently_verified"] is False
    assert "original-interaction-one" not in str(result)
    assert "Hello" not in str(result)
    taskrow, reserve, events = _read_state(db, task)
    assert taskrow["status"] == "verified"
    assert taskrow["interaction_id"] == "original-interaction-one"
    assert taskrow["output_sha256"] == result["wav_sha256"]
    assert reserve["status"] == "held"
    assert [x["action"] for x in events][-1] == "format_verified_not_speech_reviewed"
    second = OfflineFakeExistingAudioReader("original-interaction-one")
    with pytest.raises(OfflineExistingAudioDenied):
        recover_offline_existing_tts_wav(db, task, second)
    assert second.read_calls == 0


@pytest.mark.parametrize("fault", ["timeout", "wrong_id", "corrupt_audio"])
def test_unknown_or_mismatched_original_result_preserves_ack_and_hold(client, fault):
    db, task = _acknowledged(client)
    original = _read_state(db, task)
    reader = OfflineFakeExistingAudioReader(
        "original-interaction-one", fault=fault,
    )
    with pytest.raises(OfflineExistingAudioDenied, match="no resubmission") as exc:
        recover_offline_existing_tts_wav(db, task, reader)
    assert reader.read_calls == 1
    assert "private" not in str(exc.value)
    assert "original-interaction-one" not in str(exc.value)
    assert _read_state(db, task) == original
    with pytest.raises(OfflineExistingAudioDenied):
        recover_offline_existing_tts_wav(db, task, reader)
    assert reader.read_calls == 1


def test_wrong_provider_id_blocks_before_any_existing_audio_read(client):
    db, task = _acknowledged(client)
    fake = OfflineFakeExistingAudioReader("someone-elses-interaction")
    with pytest.raises(OfflineExistingAudioDenied, match="acknowledged"):
        recover_offline_existing_tts_wav(db, task, fake)
    assert fake.read_calls == 0
    assert db.one("SELECT status FROM tts_tasks WHERE id=?", (task,))["status"] == "acknowledged"


def test_unsubmitted_and_quarantined_task_cannot_recover_fake_wav(client):
    db, spec, control, task, _, _ = _ready(client)
    fake = OfflineFakeExistingAudioReader("original-interaction-one")
    with pytest.raises(OfflineExistingAudioDenied):
        recover_offline_existing_tts_wav(db, task, fake)
    assert fake.read_calls == 0
    commit_tts_submission_intent(db, task)
    with pytest.raises(OfflineExistingAudioDenied):
        recover_offline_existing_tts_wav(db, task, fake)
    assert fake.read_calls == 0
    quarantine_tts_unknown_ack(db, task)
    with pytest.raises(OfflineExistingAudioDenied):
        recover_offline_existing_tts_wav(db, task, fake)
    assert fake.read_calls == 0
    assert db.one("SELECT status FROM tts_tasks WHERE id=?", (task,))["status"] == "quarantined"


def test_arbitrary_sdk_or_fake_reader_subclasses_cannot_be_injected(client):
    db, task = _acknowledged(client)
    class FakePretender(OfflineFakeExistingAudioReader):
        pass
    for bogus in (object(), FakePretender("original-interaction-one")):
        with pytest.raises(OfflineExistingAudioDenied, match="exact local Fake"):
            recover_offline_existing_tts_wav(db, task, bogus)
    assert db.one("SELECT status FROM tts_tasks WHERE id=?", (task,))["status"] == "acknowledged"
