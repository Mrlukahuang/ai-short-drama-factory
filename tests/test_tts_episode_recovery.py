"""Episode TTS recovery: all cues, one snapshot, no secret or dispatch."""
from __future__ import annotations

import sqlite3
import pytest

from drama_factory.models import EpisodeDraft
from drama_factory.jobs.tts_episode_recovery import inspect_episode_tts_recovery
from drama_factory.jobs.tts_recovery_readonly import TtsRecoveryDenied
from drama_factory.jobs.tts_intents import (
    prepare_tts_task, reserve_tts_task_budget, commit_tts_submission_intent,
    quarantine_tts_unknown_ack, acknowledge_tts_provider_interaction,
)
from drama_factory.jobs.tts_fake_dispatch import (
    execute_offline_fake_tts_once, OfflineFakeGeminiTransport,
)
from drama_factory.providers.dialogue_audio import DialogueGenerationSpec
from drama_factory.providers.gemini_tts_contract import GeminiTtsPreparation
from test_offline_cast_timeline import create_reviewed_cast
from test_tts_persistent_ledger import _policies


def _episode(client):
    run, mapping, actors = create_reviewed_cast(client, explicit_timing=True)
    db = client.app.state.db
    row = db.one(
        """SELECT e.body_json,e.project_id FROM productions p
           JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""", (run,),
    )
    draft = EpisodeDraft.model_validate_json(row["body_json"])
    control = GeminiTtsPreparation(
        consent_reviewed_by_operator=True,
        max_acknowledged_spend_usd="0.04",
    )
    tasks = []
    for shot in draft.shots:
        for index, cue in enumerate(shot.dialogue_cues):
            spec = DialogueGenerationSpec(
                series_id=row["project_id"], production_id=run,
                shot_id=shot.shot_id, cue_index=index,
                speaker_actor_id=cue.speaker_actor_id,
                voice_asset_id=mapping[cue.speaker_actor_id],
                dialogue_text=f"{cue.speaker_actor_id}: {cue.text}",
                duration_seconds=cue.end_second - cue.start_second,
                operator_confirmed_voice_rights=True,
            )
            tasks.append((prepare_tts_task(db, spec, control)["id"], spec))
    _policies(db, row["project_id"], limit="1.00", concurrency=5)
    return db, run, tasks, control


def test_all_prepared_cues_are_visible_and_readonly(client):
    db, run, tasks, _ = _episode(client)
    before = [(db.one("SELECT * FROM tts_tasks WHERE id=?", (t,)),
               db.one("SELECT * FROM tts_budget_reservations WHERE task_id=?", (t,)))
              for t, _ in tasks]
    result = inspect_episode_tts_recovery(db, run)
    assert result["total_cues_checked"] == 2
    assert result["task_status_counts"] == {"prepared": 2}
    assert result["reservation_status_counts"] == {"missing": 2}
    assert result["all_approved_cues_have_tasks"] is True
    assert result["all_audio_format_receipts_present"] is False
    assert result["automatic_generation_or_retry_allowed"] is False
    assert result["publish_approved"] is False
    assert result["paid_provider_calls"] == result["external_database_writes"] == 0
    assert "Hello" not in str(result) and "Welcome" not in str(result)
    assert "task_id" not in str(result) and "interaction_id" not in str(result)
    assert before == [(db.one("SELECT * FROM tts_tasks WHERE id=?", (t,)),
                       db.one("SELECT * FROM tts_budget_reservations WHERE task_id=?", (t,)))
                      for t, _ in tasks]


def test_mixed_unknown_ack_and_verified_show_accurate_operator_triage(client):
    db, run, tasks, control = _episode(client)
    for task, _ in tasks:
        reserve_tts_task_budget(db, task, estimated_charge_usd="0.02")
    first, second = tasks
    execute_offline_fake_tts_once(
        db, first[0], first[1], control, OfflineFakeGeminiTransport(),
    )
    commit_tts_submission_intent(db, second[0])
    quarantine_tts_unknown_ack(db, second[0])
    result = inspect_episode_tts_recovery(db, run)
    assert result["task_status_counts"] == {"quarantined": 1, "verified": 1}
    assert result["reservation_status_counts"] == {"held": 2}
    assert result["any_unknown_ack_or_unresolved_submission"] is True
    assert result["all_audio_format_receipts_present"] is False
    assert result["operator_review_required"] is True
    assert result["automatic_generation_or_retry_allowed"] is False
    assert result["invoice_vendor_verified"] is False
    assert result["paid_provider_calls"] == 0


def test_any_missing_task_fails_entire_episode_closed(client):
    db, run, tasks, _ = _episode(client)
    db.exec("UPDATE tts_tasks SET shot_id='not-an-approved-shot' WHERE id=?", (tasks[1][0],))
    with pytest.raises(TtsRecoveryDenied, match="unknown|incomplete"):
        inspect_episode_tts_recovery(db, run)


def test_corrupted_one_task_audit_blocks_all_other_valid_tasks(client):
    db, run, tasks, _ = _episode(client)
    db.exec("UPDATE tts_tasks SET status='verified' WHERE id=?", (tasks[1][0],))
    with pytest.raises(TtsRecoveryDenied, match="audit|state"):
        inspect_episode_tts_recovery(db, run)


def test_invalid_run_id_rejected_and_no_external_io(client):
    db, run, _, _ = _episode(client)
    for val in ("", run + "private", "../secrets", 7, None):
        with pytest.raises(TtsRecoveryDenied):
            inspect_episode_tts_recovery(db, val)
