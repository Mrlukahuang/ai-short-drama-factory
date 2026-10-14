"""PR-10n: strictly offline Interactions GET original-ID recovery contract."""
from __future__ import annotations

import pytest

from drama_factory.jobs.tts_google_readback_contract import (
    OfflineFakeGoogleInteractionsGetter, OriginalTtsReadbackDenied,
    inspect_offline_original_google_tts_get,
)
from drama_factory.jobs.tts_existing_audio_recovery import (
    OfflineFakeExistingAudioReader, recover_offline_existing_tts_wav,
)
from drama_factory.jobs.tts_intents import (
    acknowledge_tts_provider_interaction, commit_tts_submission_intent,
    quarantine_tts_unknown_ack,
)
from test_tts_existing_audio_recovery import _acknowledged, _read_state
from drama_factory.jobs.tts_google_origin_scope import (
    TtsGoogleOriginDenied, bind_offline_tts_google_origin,
)
from test_tts_fake_dispatch import _ready

PROJECT = "a" * 64
PRINCIPAL = "b" * 64


def _acknowledged_origin(client):
    db, _, _, task, _, _ = _ready(client)
    bind_offline_tts_google_origin(
        db, task, project_ref_sha256=PROJECT, principal_ref_sha256=PRINCIPAL,
    )
    commit_tts_submission_intent(db, task)
    acknowledge_tts_provider_interaction(db, task, "original-interaction-one")
    return db, task


def _getter(original, *, fault=None, project=PROJECT, principal=PRINCIPAL):
    return OfflineFakeGoogleInteractionsGetter(
        original, project_ref_sha256=project,
        principal_ref_sha256=principal, fault=fault,
    )


def test_valid_get_only_reads_original_id_leaves_ledger_and_hold_unchanged(client):
    db, task = _acknowledged_origin(client)
    before = _read_state(db, task)
    getter = _getter("original-interaction-one")
    result = inspect_offline_original_google_tts_get(db, task, getter)
    assert result["original_get_attempts"] == 1
    assert result["new_generation_requests"] == 0
    assert result["real_google_get_executed"] is False
    assert result["durable_verification_written"] is False
    assert result["origin_google_project_and_permissions_verified"] is False
    assert result["publish_approved"] is False
    assert len(result["wav_sha256"]) == 64
    assert result["duration_seconds"] > 0
    assert _read_state(db, task) == before
    assert before[1]["status"] == "held"
    assert "original-interaction-one" not in str(result)
    assert "original-interaction-one" not in repr(getter)
    with pytest.raises(OriginalTtsReadbackDenied, match="unused"):
        inspect_offline_original_google_tts_get(db, task, getter)
    assert getter.get_calls == 1


@pytest.mark.parametrize("fault", [
    "timeout", "permission", "expired", "wrong_id",
    "missing_audio", "corrupt_audio", "wrong_mime",
])
def test_failed_or_expired_google_get_never_resubmits_or_mutates(client, fault):
    db, task = _acknowledged_origin(client)
    before = _read_state(db, task)
    getter = _getter(
        "original-interaction-one", fault=fault,
    )
    with pytest.raises(OriginalTtsReadbackDenied, match="no generation") as exc:
        inspect_offline_original_google_tts_get(db, task, getter)
    assert getter.get_calls == 1
    assert "PRIVATE" not in str(exc.value)
    assert "original-interaction-one" not in str(exc.value)
    assert _read_state(db, task) == before


def test_wrong_persisted_id_and_subclasses_blocked_before_get(client):
    db, task = _acknowledged_origin(client)
    wrong = _getter("another-original-id")
    with pytest.raises(OriginalTtsReadbackDenied, match="Original ID"):
        inspect_offline_original_google_tts_get(db, task, wrong)
    assert wrong.get_calls == 0

    class PretendSdk(OfflineFakeGoogleInteractionsGetter):
        pass

    forged = PretendSdk("original-interaction-one", PROJECT, PRINCIPAL)
    with pytest.raises(OriginalTtsReadbackDenied, match="exact offline"):
        inspect_offline_original_google_tts_get(db, task, forged)
    assert forged.get_calls == 0
    with pytest.raises(OriginalTtsReadbackDenied, match="exact offline"):
        inspect_offline_original_google_tts_get(db, task, object())


def test_unsubmitted_unknown_ack_and_already_verified_all_block_before_get(client):
    db, _, _, task, _, _ = _ready(client)
    getter = _getter("original-interaction-one")
    with pytest.raises(OriginalTtsReadbackDenied):
        inspect_offline_original_google_tts_get(db, task, getter)
    commit_tts_submission_intent(db, task)
    with pytest.raises(OriginalTtsReadbackDenied):
        inspect_offline_original_google_tts_get(db, task, getter)
    quarantine_tts_unknown_ack(db, task)
    with pytest.raises(OriginalTtsReadbackDenied):
        inspect_offline_original_google_tts_get(db, task, getter)
    assert getter.get_calls == 0

    db2, acknowledged = _acknowledged_origin(client)
    recover_offline_existing_tts_wav(
        db2, acknowledged, OfflineFakeExistingAudioReader("original-interaction-one"),
    )
    already = _getter("original-interaction-one")
    with pytest.raises(OriginalTtsReadbackDenied):
        inspect_offline_original_google_tts_get(db2, acknowledged, already)
    assert already.get_calls == 0


def test_get_refuses_tampered_audit_before_external_operation(client):
    db, task = _acknowledged_origin(client)
    db.exec(
        """INSERT INTO tts_task_events
           (id,task_id,action,previous_state,next_state,details_json,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        ("extra-readback-test-event", task, "paid_intent_committed",
         "prepared", "submission_intent", "{}", "2026-10-14T00:00:00Z"),
    )
    getter = _getter("original-interaction-one")
    with pytest.raises(OriginalTtsReadbackDenied, match="audit"):
        inspect_offline_original_google_tts_get(db, task, getter)
    assert getter.get_calls == 0


def test_same_wav_already_verified_for_other_cue_requires_operator_review(client):
    db, first = _acknowledged_origin(client)
    recover_offline_existing_tts_wav(
        db, first, OfflineFakeExistingAudioReader("original-interaction-one"),
    )
    db2, _, _, second, _, _ = _ready(client)
    bind_offline_tts_google_origin(
        db2, second, project_ref_sha256=PROJECT, principal_ref_sha256=PRINCIPAL,
    )
    commit_tts_submission_intent(db2, second)
    acknowledge_tts_provider_interaction(db2, second, "other-original-interaction")
    before = _read_state(db2, second)
    getter = _getter("other-original-interaction")
    with pytest.raises(OriginalTtsReadbackDenied, match="no generation"):
        inspect_offline_original_google_tts_get(db2, second, getter)
    assert getter.get_calls == 1
    assert _read_state(db2, second) == before


def test_missing_origin_fails_closed_before_get(client):
    db, task = _acknowledged(client)
    getter = _getter("original-interaction-one")
    with pytest.raises(OriginalTtsReadbackDenied, match="scope"):
        inspect_offline_original_google_tts_get(db, task, getter)
    assert getter.get_calls == 0


@pytest.mark.parametrize("project,principal", [
    ("c" * 64, PRINCIPAL), (PROJECT, "d" * 64),
])
def test_wrong_project_or_principal_fails_closed_before_get(client, project, principal):
    db, task = _acknowledged_origin(client)
    before = _read_state(db, task)
    getter = _getter("original-interaction-one", project=project, principal=principal)
    with pytest.raises(OriginalTtsReadbackDenied, match="origin context"):
        inspect_offline_original_google_tts_get(db, task, getter)
    assert getter.get_calls == 0
    assert _read_state(db, task) == before


def test_scope_binding_only_preintent_immutable_and_no_raw_metadata(client):
    import sqlite3
    db, _, _, task, _, _ = _ready(client)
    denied = [
        ("not-hex", PRINCIPAL),
        (PROJECT.upper(), PRINCIPAL),
        (PROJECT, PROJECT),
        (PROJECT, ""),
    ]
    for project, principal in denied:
        with pytest.raises(TtsGoogleOriginDenied):
            bind_offline_tts_google_origin(
                db, task, project_ref_sha256=project, principal_ref_sha256=principal,
            )
    result = bind_offline_tts_google_origin(
        db, task, project_ref_sha256=PROJECT, principal_ref_sha256=PRINCIPAL,
    )
    assert result["scope_authentication_verified"] is False
    assert result["live_readback_allowed"] is False
    assert PROJECT not in str(result) and PRINCIPAL not in str(result)
    # Same immutable fixture is idempotent, different context is rejected.
    bind_offline_tts_google_origin(
        db, task, project_ref_sha256=PROJECT, principal_ref_sha256=PRINCIPAL,
    )
    with pytest.raises(TtsGoogleOriginDenied, match="cannot change"):
        bind_offline_tts_google_origin(
            db, task, project_ref_sha256="c"*64, principal_ref_sha256=PRINCIPAL,
        )
    for statement in (
        "UPDATE tts_google_origin_scopes SET project_ref_sha256=? WHERE task_id=?",
        "DELETE FROM tts_google_origin_scopes WHERE task_id=?",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            if statement.startswith("UPDATE"):
                db.exec(statement, ("c"*64, task))
            else:
                db.exec(statement, (task,))
    commit_tts_submission_intent(db, task)
    with pytest.raises(TtsGoogleOriginDenied, match="unsubmitted"):
        bind_offline_tts_google_origin(
            db, task, project_ref_sha256=PROJECT, principal_ref_sha256=PRINCIPAL,
        )
