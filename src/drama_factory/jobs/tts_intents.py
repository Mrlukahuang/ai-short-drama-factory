"""PR-10g: local-only persistent Gemini TTS submission fence and cost ledger.

Never instantiates a Google client and NEVER sends a request. Atomic SQLite
transactions make an intended external submission terminal for the right to
submit, including ACK loss. Operator may reconcile provider invoice evidence,
but not replay a possibly charged utterance.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from decimal import Decimal

from drama_factory.db import Database, new_id, timestamp
from drama_factory.jobs.budgets import _amount, _latest, _usd, BudgetDenied
from drama_factory.providers.dialogue_audio import DialogueGenerationSpec
from drama_factory.providers.gemini_tts_contract import (
    GeminiTtsPreparation, PreparedGeminiSpeech,
    InspectedGeminiSpeech, prepare_gemini_tts_request,
)


class TtsLedgerDenied(ValueError):
    """Fixed non-sensitive error messages; never reveal script or auth."""


def _event(conn, task_id: str, action: str, before: str | None,
           after: str, evidence: dict | None = None) -> None:
    conn.execute(
        """INSERT INTO tts_task_events
           (id,task_id,action,previous_state,next_state,details_json,created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (new_id("ttsev"), task_id, action, before, after,
         json.dumps(evidence or {}, sort_keys=True, separators=(",", ":")), timestamp()),
    )


def prepare_tts_task(
    db: Database, spec: DialogueGenerationSpec, control: GeminiTtsPreparation,
) -> dict:
    """Preflight real reviewed cue, persist fingerprint only (not user text)."""
    plan = prepare_gemini_tts_request(db, spec, control)
    spend = _usd(_amount(plan.max_acknowledged_spend_usd))
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Same actor/script/version can only have ONE immutable TTS job per cue.
        found = conn.execute(
            """SELECT * FROM tts_tasks WHERE production_id=? AND shot_id=?
               AND cue_index=?""",
            (spec.production_id, spec.shot_id, spec.cue_index),
        ).fetchone()
        if found:
            if (
                found["request_sha256"] != plan.fingerprint
                or found["max_acknowledged_spend_usd"] != spend
                or found["model_id"] != plan.model_id
                or found["voice_name"] != plan.voice_name
            ):
                raise TtsLedgerDenied("Existing TTS cue has immutable request settings")
            return _safe_task(dict(found))
        row = conn.execute(
            """SELECT e.project_id FROM productions p
               JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
            (spec.production_id,),
        ).fetchone()
        if row is None or row["project_id"] != spec.series_id:
            raise TtsLedgerDenied("Reviewed TTS series scope changed")
        task_id = new_id("ttstask")
        conn.execute(
            """INSERT INTO tts_tasks
               (id,production_id,series_id,shot_id,cue_index,request_sha256,
                model_id,voice_name,max_acknowledged_spend_usd,
                approved_slot_seconds,status,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id, spec.production_id, spec.series_id, spec.shot_id,
             spec.cue_index, plan.fingerprint, plan.model_id, plan.voice_name,
             spend, plan.approved_slot_seconds, "prepared", timestamp(), timestamp()),
        )
        _event(conn, task_id, "prepared_offline", None, "prepared", {
            "input_sha256": plan.fingerprint,
            "real_sdk_submission_enabled": False,
            "vendor_spend_cap_verified": False,
        })
        return _safe_task(dict(conn.execute(
            "SELECT * FROM tts_tasks WHERE id=?", (task_id,),
        ).fetchone()))


def _safe_task(row: dict) -> dict:
    """Do not return script, actor ID, voice consent reference or private WAV."""
    return {
        "id": row["id"], "status": row["status"],
        "request_sha256": row["request_sha256"],
        "model_id": row["model_id"],
        "voice_name": row["voice_name"],
        "max_acknowledged_spend_usd": row["max_acknowledged_spend_usd"],
        "approved_slot_seconds": row["approved_slot_seconds"],
        "provider_interaction_recorded": bool(row["interaction_id"]),
        "wav_receipt_recorded": bool(row["output_sha256"]),
        "submitted_to_provider_by_this_module": False,
        "automated_retry_allowed": False,
        "vendor_billing_verified": False,
        "publish_approved": False,
    }


def reserve_tts_task_budget(
    db: Database, task_id: str, *, estimated_charge_usd: str,
    now: datetime | None = None,
) -> dict:
    """Atomic three-scope hold counted jointly with video reservations."""
    point = now or datetime.now(timezone.utc)
    if point.tzinfo is None:
        raise TtsLedgerDenied("UTC-aware reservation time is required")
    day = point.astimezone(timezone.utc).date().isoformat()
    amount = _amount(estimated_charge_usd)
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        task = conn.execute(
            """SELECT t.*,p.column_id FROM tts_tasks t JOIN projects p
               ON p.id=t.series_id WHERE t.id=?""", (task_id,),
        ).fetchone()
        if task is None or task["status"] != "prepared":
            raise TtsLedgerDenied("Only untouched reviewed TTS cues may reserve budget")
        if amount > _amount(task["max_acknowledged_spend_usd"]):
            raise TtsLedgerDenied("TTS estimate exceeds approved per-cue allowance")
        existing = conn.execute(
            "SELECT * FROM tts_budget_reservations WHERE task_id=?", (task_id,),
        ).fetchone()
        if existing:
            if (
                existing["status"] == "held"
                and existing["day_utc"] == day
                and existing["reserved_usd"] == _usd(amount)
            ):
                return _safe_reserve(dict(existing))
            raise TtsLedgerDenied("TTS reservation is immutable")
        scopes = [
            ("column", task["column_id"]),
            ("series", task["series_id"]),
            ("provider", task["provider"]),
        ]
        policy = [_latest(conn, name, ident) for name, ident in scopes]
        active = conn.execute(
            """SELECT column_id,series_id,provider,reserved_usd,actual_usd,status
               FROM job_budget_reservations WHERE day_utc=?
               UNION ALL
               SELECT column_id,series_id,provider,reserved_usd,actual_usd,status
               FROM tts_budget_reservations WHERE day_utc=?""", (day,day),
        ).fetchall()
        keys = {"column": "column_id", "series": "series_id", "provider": "provider"}
        for (name, ident), current in zip(scopes, policy, strict=True):
            items = [r for r in active if r[keys[name]] == ident]
            held = [r for r in items if r["status"] == "held"]
            used = sum((
                _amount(r["reserved_usd"]) if r["status"] == "held"
                else _amount(r["actual_usd"], allow_zero=True)
            ) for r in items if r["status"] in ("held", "reconciled"))
            if used + amount > _amount(current["daily_limit_usd"]):
                raise BudgetDenied(name + " daily budget would be exceeded")
            if len(held) >= current["max_active_jobs"]:
                raise BudgetDenied(name + " active job limit reached")
        hold_id = new_id("ttsreserve")
        snapshot = [
            {"scope": name, "scope_id": ident,
             "policy_id": pol["id"], "revision": pol["revision"]}
            for (name, ident), pol in zip(scopes, policy, strict=True)
        ]
        conn.execute(
            """INSERT INTO tts_budget_reservations
               (id,task_id,column_id,series_id,provider,day_utc,
                reserved_usd,status,policy_snapshot_json,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (hold_id, task_id, task["column_id"], task["series_id"],
             task["provider"], day, _usd(amount), "held",
             json.dumps(snapshot, sort_keys=True), timestamp(), timestamp()),
        )
        _event(conn, task_id, "budget_held", "prepared", "prepared", {
            "reserved_usd": _usd(amount), "day_utc": day,
            "billing_vendor_verified": False,
        })
        return _safe_reserve(dict(conn.execute(
            "SELECT * FROM tts_budget_reservations WHERE id=?", (hold_id,),
        ).fetchone()))


def _safe_reserve(row: dict) -> dict:
    return {
        "id": row["id"], "task_id": row["task_id"],
        "day_utc": row["day_utc"], "status": row["status"],
        "reserved_usd": row["reserved_usd"],
        "real_provider_hard_cap": False,
    }


def commit_tts_submission_intent(
    db: Database, task_id: str, *, now: datetime | None = None,
) -> dict:
    """Atomic point-of-no-return before ANY future SDK attempt.

    This module does not submit. Once this durable flag commits there is no
    automatic retry, even if the future HTTP call returns no task ID.
    """
    point = now or datetime.now(timezone.utc)
    if point.tzinfo is None:
        raise TtsLedgerDenied("UTC-aware submission time is required")
    day = point.astimezone(timezone.utc).date().isoformat()
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM tts_tasks WHERE id=?", (task_id,)).fetchone()
        reserve = conn.execute(
            "SELECT * FROM tts_budget_reservations WHERE task_id=?", (task_id,),
        ).fetchone()
        if (
            row is None or row["status"] != "prepared" or reserve is None
            or reserve["status"] != "held" or reserve["day_utc"] != day
        ):
            raise TtsLedgerDenied("Current held three-scope reserve and unused task required")
        conn.execute(
            "UPDATE tts_tasks SET status='submission_intent',updated_at=? WHERE id=?",
            (timestamp(), task_id),
        )
        _event(conn, task_id, "paid_intent_committed", "prepared",
               "submission_intent", {"ack_may_be_lost": True, "retry_allowed": False})
        return _safe_task(dict(conn.execute(
            "SELECT * FROM tts_tasks WHERE id=?", (task_id,),
        ).fetchone()))


def acknowledge_tts_provider_interaction(
    db: Database, task_id: str, interaction_id: str,
) -> dict:
    """Attach external interaction receipt; NEVER create a second request."""
    if type(interaction_id) is not str or not re.fullmatch(r"[A-Za-z0-9_./:-]{2,300}", interaction_id):
        raise TtsLedgerDenied("Invalid TTS interaction receipt")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM tts_tasks WHERE id=?", (task_id,)).fetchone()
        if row is None or row["status"] != "submission_intent" or row["interaction_id"]:
            raise TtsLedgerDenied("A single committed TTS request is required")
        conn.execute(
            "UPDATE tts_tasks SET status='acknowledged',interaction_id=?,updated_at=? WHERE id=?",
            (interaction_id, timestamp(), task_id),
        )
        _event(conn, task_id, "interaction_id_recorded",
               "submission_intent", "acknowledged", {"has_external_interaction_id": True})
        return _safe_task(dict(conn.execute(
            "SELECT * FROM tts_tasks WHERE id=?", (task_id,),
        ).fetchone()))


def quarantine_tts_unknown_ack(db: Database, task_id: str) -> dict:
    """Unknown API outcome may have been billed. Never release its hold."""
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM tts_tasks WHERE id=?", (task_id,)).fetchone()
        if row is None or row["status"] != "submission_intent":
            raise TtsLedgerDenied("Only unknown unacknowledged TTS requests may quarantine")
        conn.execute(
            "UPDATE tts_tasks SET status='quarantined',updated_at=? WHERE id=?",
            (timestamp(), task_id),
        )
        _event(conn, task_id, "unknown_ack_quarantined", "submission_intent",
               "quarantined", {"may_have_been_billed": True, "retry_allowed": False})
        return _safe_task(dict(conn.execute(
            "SELECT * FROM tts_tasks WHERE id=?", (task_id,),
        ).fetchone()))


def record_offline_verified_tts_wav(
    db: Database, task_id: str, inspected: InspectedGeminiSpeech,
) -> dict:
    """Persist validation metadata, not audio or verified speech/rights claim."""
    if type(inspected) is not InspectedGeminiSpeech:
        raise TtsLedgerDenied("Actual WAV verification receipt required")
    if hashlib.sha256(inspected.wav_bytes).hexdigest() != inspected.sha256:
        raise TtsLedgerDenied("WAV payload does not match inspection digest")
    if not (0 < inspected.duration_seconds <= 30.25):
        raise TtsLedgerDenied("Invalid inspected WAV duration")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM tts_tasks WHERE id=?", (task_id,)).fetchone()
        if row is None or row["status"] != "acknowledged" or not row["interaction_id"]:
            raise TtsLedgerDenied("Acknowledged TTS interaction required")
        if inspected.duration_seconds > row["approved_slot_seconds"] + 0.25:
            raise TtsLedgerDenied("Validated WAV exceeds approved director slot")
        conn.execute(
            """UPDATE tts_tasks SET status='verified',
               output_sha256=?,output_duration_seconds=?,updated_at=? WHERE id=?""",
            (inspected.sha256, str(inspected.duration_seconds), timestamp(), task_id),
        )
        _event(conn, task_id, "format_verified_not_speech_reviewed",
               "acknowledged", "verified", {
                   "wav_sha256": inspected.sha256, "no_publication_authority": True,
               })
        return _safe_task(dict(conn.execute(
            "SELECT * FROM tts_tasks WHERE id=?", (task_id,),
        ).fetchone()))


def record_tts_vendor_charge(
    db: Database, task_id: str, *, amount_usd: str,
    evidence_reference: str, reviewer: str,
) -> dict:
    """Explicit operator invoice entry; does not verify vendor API invoices."""
    money = _amount(amount_usd, allow_zero=True)
    if not 3 <= len(evidence_reference) <= 500 or not 2 <= len(reviewer) <= 120:
        raise TtsLedgerDenied("Billing evidence and reviewer are required")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        task = conn.execute("SELECT status FROM tts_tasks WHERE id=?", (task_id,)).fetchone()
        hold = conn.execute(
            "SELECT * FROM tts_budget_reservations WHERE task_id=?", (task_id,),
        ).fetchone()
        if task is None or task["status"] not in (
            "submission_intent", "acknowledged", "quarantined", "verified",
        ) or hold is None or hold["status"] != "held":
            raise TtsLedgerDenied("Unreconciled paid TTS intent and held budget required")
        conn.execute(
            """UPDATE tts_budget_reservations SET status='reconciled',actual_usd=?,
               evidence_reference=?,reviewed_by=?,updated_at=? WHERE id=?""",
            (_usd(money), evidence_reference, reviewer, timestamp(), hold["id"]),
        )
        _event(conn, task_id, "operator_entered_vendor_charge",
               task["status"], task["status"], {
                   "actual_usd": _usd(money), "billing_evidence_supplied": True,
                   "over_reserved": money > _amount(hold["reserved_usd"]),
               })
        return {
            "id": hold["id"], "status": "reconciled",
            "actual_usd": _usd(money), "vendor_invoice_independently_verified": False,
            "retry_allowed": False,
        }


def list_tts_task_events(db: Database, task_id: str) -> list[dict]:
    """Return only redacted audit metadata; no script or SDK body."""
    rows = db.many(
        """SELECT action,previous_state,next_state,details_json,created_at
           FROM tts_task_events WHERE task_id=? ORDER BY rowid""", (task_id,),
    )
    return [{**{k:v for k,v in row.items() if k != "details_json"},
             "details": json.loads(row["details_json"])} for row in rows]
