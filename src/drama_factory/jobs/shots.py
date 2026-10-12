"""Offline-only, transactional per-shot job ledger (no provider SDK calls).

Jobs are prepared from a *reviewed* production, with immutable input fingerprints
and a series scope. Starting, retrying, and recovery are explicit internal calls.
Most importantly, a provider task ID blocks creating another paid generation.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from drama_factory.db import Database, new_id, timestamp
from drama_factory.models import EpisodeDraft


class ShotJobError(ValueError):
    pass


def _json(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _at(now: datetime | None = None) -> str:
    point = now or datetime.now(timezone.utc)
    if point.tzinfo is None:
        raise ShotJobError("Timestamp must be timezone-aware")
    return point.astimezone(timezone.utc).isoformat()


def _spend_acknowledgement(value) -> str:
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or not Decimal("0") < amount <= Decimal("100"):
            raise ShotJobError("Acknowledged maximum must be a positive finite amount")
        if amount != amount.quantize(Decimal("0.01")):
            raise ShotJobError("Only two decimal places are supported")
        return f"{amount:.2f}"
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ShotJobError("Invalid acknowledged maximum spend") from exc


def _event(conn, job_id, action, previous_state, state, data: dict | None = None):
    conn.execute(
        """INSERT INTO shot_job_events
        (id,shot_job_id,action,previous_state,next_state,details_json,created_at)
        VALUES (?,?,?,?,?,?,?)""",
        (new_id("evt"), job_id, action, previous_state, state,
         _json(data or {}), timestamp()),
    )


def prepare_shot_jobs(
    db: Database, production_id: str, *, provider: str = "google",
    max_acknowledged_spend_usd: str = "1.00", max_attempts: int = 2,
) -> list[dict]:
    """Idempotently stage every shot; never submits or authorizes provider billing."""
    if not re.fullmatch(r"[a-z0-9_-]{2,60}", provider):
        raise ShotJobError("Provider ID is invalid")
    if not 1 <= max_attempts <= 5:
        raise ShotJobError("Max attempts outside 1..5")
    spend = _spend_acknowledgement(max_acknowledged_spend_usd)
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        p = conn.execute(
            """SELECT p.id,p.status,e.id AS episode_id,e.project_id,e.body_json
            FROM productions p JOIN episodes e ON e.id=p.episode_id
            WHERE p.id=?""", (production_id,),
        ).fetchone()
        if p is None:
            raise ShotJobError("Unknown production")
        if p["status"] not in ("ready_for_video_generation", "offline_preview_finished"):
            raise ShotJobError("Both production approval gates are required")
        draft = EpisodeDraft.model_validate_json(p["body_json"])
        if len(draft.shots) > 500:
            raise ShotJobError("Shot batch exceeds 500")
        for shot in draft.shots:
            referenced = {}
            for asset_id, kind in [
                *[(a, "actor") for a in shot.character_ids],
                *([(shot.scene_id, "scene")] if shot.scene_id else []),
            ]:
                asset = conn.execute(
                    """SELECT id,kind,version,specification_json FROM series_assets
                    WHERE id=? AND series_id=? AND kind=?""",
                    (asset_id, p["project_id"], kind),
                ).fetchone()
                if asset is None:
                    raise ShotJobError("Shot references an asset outside its own series")
                referenced[asset_id] = {
                    "kind": asset["kind"], "version": asset["version"],
                    "spec_sha256": hashlib.sha256(
                        asset["specification_json"].encode("utf-8")
                    ).hexdigest(),
                }
            payload = {
                "production_id": production_id,
                "episode_id": p["episode_id"], "series_id": p["project_id"],
                "shot": shot.model_dump(mode="json"),
                "asset_versions": referenced, "provider": provider,
            }
            fingerprint = hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
            existing = conn.execute(
                "SELECT id,input_sha256,provider,model_id FROM shot_jobs WHERE production_id=? AND shot_id=?",
                (production_id, shot.shot_id),
            ).fetchone()
            if existing:
                if (
                    existing["input_sha256"] != fingerprint
                    or existing["provider"] != provider
                    or existing["max_acknowledged_spend_usd"] != spend
                    or existing["max_attempts"] != max_attempts
                    or existing["model_id"] != shot.video_model
                ):
                    raise ShotJobError("Existing job has different immutable shot inputs")
                continue
            job_id = new_id("shotjob")
            conn.execute(
                """INSERT INTO shot_jobs
                (id,production_id,episode_id,series_id,shot_id,provider,model_id,
                 input_sha256,idempotency_key,max_acknowledged_spend_usd,
                 status,attempts,max_attempts,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job_id, production_id, p["episode_id"], p["project_id"],
                 shot.shot_id, provider, shot.video_model, fingerprint,
                 fingerprint, spend, "pending", 0, max_attempts,
                 timestamp(), timestamp()),
            )
            _event(conn, job_id, "prepared", None, "pending", {
                "model": shot.video_model, "input_sha256": fingerprint,
                "max_acknowledged_spend_usd": spend,
                "note": "Acknowledgement is not a vendor billing cap",
            })
        return [dict(r) for r in conn.execute(
            "SELECT * FROM shot_jobs WHERE production_id=? ORDER BY shot_id",
            (production_id,),
        )]


def claim_next_job(
    db: Database, worker_id: str, *, series_id: str | None = None,
    lease_seconds: int = 90, now: datetime | None = None,
) -> dict | None:
    """Atomically claim exactly one queued job; never calls a provider."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,80}", worker_id):
        raise ShotJobError("Worker ID is invalid")
    if not 10 <= lease_seconds <= 3600:
        raise ShotJobError("Lease must be 10..3600 seconds")
    instant = _at(now)
    deadline = _at(
        datetime.fromisoformat(instant) + timedelta(seconds=lease_seconds)
    )
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        sql = """SELECT * FROM shot_jobs
                 WHERE status='pending' AND attempts < max_attempts"""
        params = []
        if series_id is not None:
            sql += " AND series_id=?"
            params.append(series_id)
        sql += " ORDER BY created_at,id LIMIT 1"
        job = conn.execute(sql, tuple(params)).fetchone()
        if job is None:
            return None
        changed = conn.execute(
            """UPDATE shot_jobs SET status='leased', attempts=attempts+1,
               lease_owner=?,lease_expires_at=?,updated_at=? WHERE id=? AND status='pending'""",
            (worker_id, deadline, instant, job["id"]),
        )
        if changed.rowcount != 1:
            raise ShotJobError("Concurrent claim conflict")
        _event(conn, job["id"], "claimed", "pending", "leased", {
            "worker": worker_id, "lease_expires_at": deadline,
        })
        return dict(conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job["id"],)).fetchone())


def _leased(conn, job_id: str, worker_id: str, now: datetime | None):
    row = conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone()
    if row is None or row["status"] != "leased" or row["lease_owner"] != worker_id:
        raise ShotJobError("Job is not leased by this worker")
    if row["lease_expires_at"] < _at(now):
        raise ShotJobError("Lease expired: operator must reconcile before retry")
    return row


def record_submission_intent(
    db: Database, job_id: str, worker_id: str, *,
    now: datetime | None = None,
) -> dict:
    """MUST be committed before any external generation request is sent.

    If the worker crashes after this point without a task ID, leave the job
    quarantined for manual investigation: DO NOT automatically retry.
    """
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _leased(conn, job_id, worker_id, now)
        conn.execute(
            """UPDATE shot_jobs SET status='submission_intent',
               generation_intent_recorded=1,updated_at=? WHERE id=?""",
            (timestamp(), job_id),
        )
        _event(conn, job_id, "generation_intent_recorded", "leased",
               "submission_intent", {"may_have_been_billed": True})
        return dict(conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone())


def record_submission(
    db: Database, job_id: str, worker_id: str, provider_task_id: str,
    *, now: datetime | None = None,
) -> dict:
    """Attach returned provider task ID; NEVER submit a second generation."""
    if not re.fullmatch(r"[A-Za-z0-9_./:-]{2,300}", provider_task_id):
        raise ShotJobError("Provider task ID is invalid")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone()
        if (
            row is None or row["status"] != "submission_intent"
            or row["lease_owner"] != worker_id
        ):
            raise ShotJobError("Record a generation intent before submission")
        if row["provider_task_id"]:
            raise ShotJobError("Provider task already recorded")
        conn.execute(
            """UPDATE shot_jobs SET status='submitted', provider_task_id=?,
               updated_at=? WHERE id=?""", (provider_task_id, timestamp(), job_id),
        )
        _event(conn, job_id, "provider_task_recorded", "submission_intent", "submitted", {
            "provider_task_id": provider_task_id,
        })
        return dict(conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone())


def record_failure(db: Database, job_id: str, reason: str, *, worker_id: str) -> dict:
    if not 1 <= len(reason) <= 500:
        raise ShotJobError("Provide a short failure reason")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone()
        if (
            row is None or row["status"] not in ("leased", "submission_intent", "submitted")
            or row["lease_owner"] != worker_id
        ):
            raise ShotJobError("Worker cannot fail this job")
        conn.execute(
            """UPDATE shot_jobs SET status='failed',last_error=?,updated_at=?
               WHERE id=?""", (reason, timestamp(), job_id),
        )
        _event(conn, job_id, "failed", row["status"], "failed", {
            "has_provider_task_id": bool(row["provider_task_id"]),
        })
        return dict(conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone())


def restore_failed_job(db: Database, job_id: str, *, operator_reviewed: bool) -> dict:
    """Fail-closed manual recovery: submitted task -> poll; never resubmit that task."""
    if operator_reviewed is not True:
        raise ShotJobError("Human operator review is required")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone()
        if row is None or row["status"] != "failed":
            raise ShotJobError("Only failed jobs may be restored")
        if row["provider_task_id"]:
            new_status = "submitted"
            action = "resume_existing_provider_task"
        else:
            if row["generation_intent_recorded"]:
                raise ShotJobError(
                    "Generation may have been billed; task ID missing. "
                    "Manual provider reconciliation is required, not a new request"
                )
            if row["attempts"] >= row["max_attempts"]:
                raise ShotJobError("Retry count exhausted")
            new_status = "pending"
            action = "approved_local_retry"
        conn.execute(
            """UPDATE shot_jobs SET status=?,lease_owner=NULL,
               lease_expires_at=NULL,last_error=NULL,updated_at=? WHERE id=?""",
            (new_status, timestamp(), job_id),
        )
        _event(conn, job_id, action, "failed", new_status, {
            "new_generation_allowed": new_status == "pending",
            "existing_provider_task_id": row["provider_task_id"],
        })
        return dict(conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone())


def complete_submitted_job(
    db: Database, job_id: str, *, provider_task_id: str,
    result_sha256: str, result_path: str,
) -> dict:
    """Record verified external media metadata, not vendor price or billed dollars."""
    if not re.fullmatch(r"[0-9a-f]{64}", result_sha256):
        raise ShotJobError("Invalid media SHA256")
    if not result_path or len(result_path) > 500:
        raise ShotJobError("Result path missing")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone()
        if (
            row is None or row["status"] != "submitted"
            or row["provider_task_id"] != provider_task_id
        ):
            raise ShotJobError("Existing provider task ID must match")
        conn.execute(
            """UPDATE shot_jobs SET status='succeeded',result_sha256=?,
               result_path=?,updated_at=? WHERE id=?""",
            (result_sha256, result_path, timestamp(), job_id),
        )
        _event(conn, job_id, "result_recorded", "submitted", "succeeded", {
            "result_sha256": result_sha256, "billing": "unverified",
        })
        return dict(conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone())


def list_stalled_jobs(db: Database, *, now: datetime | None = None) -> list[dict]:
    """Introspection only: a timeout never silently creates a second paid request."""
    return db.many(
        """SELECT * FROM shot_jobs
        WHERE status IN ('leased','submission_intent') AND lease_expires_at < ?
        ORDER BY lease_expires_at,id""", (_at(now),),
    )


def list_job_events(db: Database, job_id: str) -> list[dict]:
    return db.many(
        "SELECT * FROM shot_job_events WHERE shot_job_id=? ORDER BY created_at,id",
        (job_id,),
    )


def investigate_stale_job(
    db: Database, job_id: str, *, operator_reviewed: bool,
    now: datetime | None = None,
) -> dict:
    """Only flag a dead lease for manual reconciliation. Never auto-requeue."""
    if operator_reviewed is not True:
        raise ShotJobError("Human operator review is required")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone()
        if (
            row is None or row["status"] not in ("leased", "submission_intent")
            or row["lease_expires_at"] >= _at(now)
        ):
            raise ShotJobError("Job is not an expired active lease")
        conn.execute(
            "UPDATE shot_jobs SET status='failed',last_error=?,updated_at=? WHERE id=?",
            ("Stalled lease requires operator reconciliation", timestamp(), job_id),
        )
        _event(conn, job_id, "manual_stalled_lease_review", row["status"], "failed", {
            "generation_intent_recorded": bool(row["generation_intent_recorded"]),
        })
        return dict(conn.execute("SELECT * FROM shot_jobs WHERE id=?", (job_id,)).fetchone())
