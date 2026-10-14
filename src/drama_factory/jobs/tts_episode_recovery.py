"""PR-10m: episode-level TTS recovery triage from ONE SQLite read snapshot.

Not a dispatcher. Never attempts generation, changes budgets, or releases
holds. A single inconsistent task or missing approved cue fails the WHOLE
episode closed, without revealing text, voice identities or interaction IDs.
"""
from __future__ import annotations

import re
from collections import Counter

from drama_factory.db import Database
from drama_factory.models import EpisodeDraft
from drama_factory.jobs.tts_recovery_readonly import (
    TtsRecoveryDenied, _classify_tts_snapshot,
)


def inspect_episode_tts_recovery(db: Database, production_id: str) -> dict:
    if type(production_id) is not str or not re.fullmatch(
        r"run_[a-f0-9]{14}", production_id
    ):
        raise TtsRecoveryDenied("Invalid opaque production identifier")
    with db.connection() as conn:
        conn.execute("BEGIN")
        row = conn.execute(
            """SELECT p.status,e.body_json FROM productions p
               JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
            (production_id,),
        ).fetchone()
        if row is None:
            raise TtsRecoveryDenied("TTS production missing")
        try:
            approved = EpisodeDraft.model_validate_json(row["body_json"])
        except Exception:
            raise TtsRecoveryDenied("Approved TTS episode schema invalid") from None
        expected = {
            (shot.shot_id, index)
            for shot in approved.shots
            for index, cue in enumerate(shot.dialogue_cues)
        }
        # Legacy unstructured dialogue cannot silently be accepted as a
        # complete set of voice assignments.
        if any(shot.dialogue and not shot.dialogue_cues for shot in approved.shots):
            raise TtsRecoveryDenied("Legacy dialogue lacks reviewed speaker mapping")
        if not expected or len(expected) > 96:
            raise TtsRecoveryDenied("Invalid episode TTS cue coverage")
        tasks = conn.execute(
            """SELECT t.id,t.shot_id,t.cue_index,t.status,t.interaction_id,
                      t.output_sha256,t.output_duration_seconds,
                      t.approved_slot_seconds,b.status AS budget_status,
                      b.actual_usd,b.evidence_reference,b.reviewed_by
               FROM tts_tasks t
               LEFT JOIN tts_budget_reservations b ON b.task_id=t.id
               WHERE t.production_id=?
               ORDER BY t.shot_id,t.cue_index""",
            (production_id,),
        ).fetchall()
        if len(tasks) != len(expected):
            raise TtsRecoveryDenied("Episode TTS cue tasks incomplete or duplicated")
        seen = set()
        results = []
        for task in tasks:
            cue_key = (task["shot_id"], task["cue_index"])
            if cue_key not in expected or cue_key in seen:
                raise TtsRecoveryDenied("TTS task points to unknown or repeated cue")
            seen.add(cue_key)
            events = conn.execute(
                """SELECT action,previous_state,next_state
                   FROM tts_task_events WHERE task_id=? ORDER BY rowid""",
                (task["id"],),
            ).fetchall()
            results.append(_classify_tts_snapshot(task, events))
        if seen != expected:
            raise TtsRecoveryDenied("Episode TTS cue coverage mismatch")
    statuses = Counter(x["task_status"] for x in results)
    recovery = Counter(x["recovery_class"] for x in results)
    reserved = Counter(x["three_scope_reservation"] for x in results)
    return {
        "kind": "episode_tts_readonly_recovery_triage",
        "all_approved_cues_have_tasks": True,
        "total_cues_checked": len(expected),
        "task_status_counts": dict(sorted(statuses.items())),
        "recovery_class_counts": dict(sorted(recovery.items())),
        "reservation_status_counts": dict(sorted(reserved.items())),
        "all_audio_format_receipts_present": statuses["verified"] == len(expected),
        "any_unknown_ack_or_unresolved_submission": bool(
            statuses["submission_intent"] or statuses["quarantined"]
        ),
        "any_existing_interaction_needing_readback": bool(statuses["acknowledged"]),
        "invoice_vendor_verified": False,
        "voice_consent_independently_verified": False,
        "paid_provider_calls": 0,
        "external_database_writes": 0,
        "automatic_generation_or_retry_allowed": False,
        "operator_review_required": True,
        "publish_approved": False,
        "production_cutover_permitted": False,
        "immutable_audit_consistent": True,
    }
