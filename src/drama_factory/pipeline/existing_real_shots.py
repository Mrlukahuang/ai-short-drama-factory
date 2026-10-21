"""G4/R4.4: admit existing REAL shot MP4 + receipt to the existing render path.

No new renderer, DB, remote SDK, retry/recovery client or fees. The returned
source_clips map plugs directly into offline_render.render_approved_preview
AFTER its separate production approvals. A provider's own JSON is NOT a
cryptographic vendor attestation; require an independent SHA pin for the
actual local media, and keep provenance/release status explicitly unverified.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.media_ingest import MediaIngressError, inspect_source

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_MAX_RECEIPT_BYTES = 32 * 1024
_MAX_REAL_SHOTS = 24
_MEDIA_SHA_FIELDS = ("source_video_sha256", "source_mp4_sha256", "video_sha256")


class RealShotHandoffError(ValueError):
    """Deliberately avoid including private video paths or Google payloads."""


def _safe_local_file(value: object, *, suffix: str) -> Path:
    if not isinstance(value, Path) or value.suffix.lower() != suffix:
        raise RealShotHandoffError("Local input type or extension invalid")
    # Refuse symlinked files/ancestors instead of letting .resolve() hide them.
    if any(part.is_symlink() for part in (value, *value.parents)):
        raise RealShotHandoffError("Symlinked local media/receipt denied")
    if not value.is_file():
        raise RealShotHandoffError("Local media or receipt not found")
    return value


def _load_receipt(path: Path) -> dict:
    path = _safe_local_file(path, suffix=".json")
    if not 10 <= path.stat().st_size <= _MAX_RECEIPT_BYTES:
        raise RealShotHandoffError("Existing video receipt size invalid")
    try:
        record = json.loads(path.read_text("utf-8"))
    except (ValueError, UnicodeError, OSError):
        raise RealShotHandoffError("Existing video receipt is not JSON") from None
    if type(record) is not dict:
        raise RealShotHandoffError("Existing video receipt must be a JSON object")
    return record


def _receipt_source_sha(receipt: dict) -> str:
    present = [receipt[key] for key in _MEDIA_SHA_FIELDS if key in receipt]
    if len(present) != 1 or type(present[0]) is not str or not _SHA.fullmatch(present[0]):
        raise RealShotHandoffError("Exactly one pinned real source digest required")
    return present[0]


def admit_existing_real_shots(
    episode: EpisodeDraft,
    inputs: list[dict],
    *,
    require_full_episode: bool = False,
) -> tuple[dict[str, Path], dict]:
    """Validate existing real-media bytes before passing to W3 local renderer.

    Each input is {shot_id, media_path: Path, receipt_path: Path,
                   expected_sha256: an INDEPENDENT operator-pinned SHA}.
    Acceptance means local media and its self-reported provider receipt agree;
    it does NOT independently authenticate Google, merchant permissions,
    provider invoices, content QA, or final publication approval.

    The function NEVER changes files, reaches the network, invokes a model
    or silently fills gaps with Fake. Missing shots remain explicit.
    """
    if not isinstance(episode, EpisodeDraft) or type(inputs) is not list:
        raise RealShotHandoffError("Approved typed episode and local shot inputs required")
    if type(require_full_episode) is not bool:
        raise RealShotHandoffError("Invalid full-episode requirement")
    ids = [shot.shot_id for shot in episode.shots]
    if (not ids or len(ids) > _MAX_REAL_SHOTS
            or len(ids) != len(set(ids))
            or sum(shot.duration_seconds for shot in episode.shots)
               != episode.target_duration_seconds):
        raise RealShotHandoffError("Episode shot order or duration mismatch")
    if not inputs or len(inputs) > len(ids):
        raise RealShotHandoffError("At least one existing real shot required")

    by_id = {shot.shot_id: shot for shot in episode.shots}
    records: dict[str, dict] = {}
    clips: dict[str, Path] = {}
    for entry in inputs:
        if type(entry) is not dict or set(entry) != {
            "shot_id", "media_path", "receipt_path", "expected_sha256"
        }:
            raise RealShotHandoffError("Real shot selection contract invalid")
        sid = entry["shot_id"]
        pin = entry["expected_sha256"]
        if (type(sid) is not str or sid not in by_id or sid in records
                or type(pin) is not str or not _SHA.fullmatch(pin)):
            raise RealShotHandoffError("Unknown, duplicate or unpinned shot")
        receipt = _load_receipt(entry["receipt_path"])
        if (receipt.get("shot_id") != sid
                or receipt.get("model_calls") != 1
                or receipt.get("source_video_real_model") is not True
                or receipt.get("output_media") != "real_omni_video_downloaded"
                or receipt.get("publication_approved") is not False
                or receipt.get("is_mock") is True
                or receipt.get("provider_reference_applied") is not True
                or receipt.get("reference_image_count") not in range(1, 9)
                or receipt.get("source_pngs_transmitted")
                   != receipt["reference_image_count"]):
            raise RealShotHandoffError("Real provider receipt scope or approval mismatch")
        if _receipt_source_sha(receipt) != pin:
            raise RealShotHandoffError("Source SHA differs from independent pin")
        media = _safe_local_file(entry["media_path"], suffix=".mp4")
        try:
            inspected = inspect_source(media, by_id[sid].duration_seconds)
        except (MediaIngressError, OSError, ValueError):
            raise RealShotHandoffError("Real shot media inspection failed") from None
        if inspected["sha256"] != pin:
            raise RealShotHandoffError("Real shot MP4 bytes differ from pinned SHA")
        clips[sid] = media
        records[sid] = {
            "shot_id": sid,
            "source_mp4_sha256": pin,
            "source_duration_seconds": inspected["duration"],
            "source_native_audio_present": inspected["has_audio"],
            "source_receipt_sha256": hashlib.sha256(
                entry["receipt_path"].read_bytes()
            ).hexdigest(),
            "model": receipt.get("model"),
            "model_calls_reported": 1,
            "reference_image_count_reported": receipt["reference_image_count"],
            "provider_task_id_reported": receipt.get("provider_task_id"),
            "provider_reference_applied_reported": True,
            "actual_model_fee_usd": receipt.get("actual_fee_usd"),
            "actual_fee_independently_verified": False,
        }
    present = [sid for sid in ids if sid in records]
    missing = [sid for sid in ids if sid not in records]
    if require_full_episode and missing:
        raise RealShotHandoffError("Cannot claim a complete episode with missing real shots")
    ordered_clips = {sid: clips[sid] for sid in present}
    ordered_records = [records[sid] for sid in present]
    report = {
        "schema": "g4-existing-real-shot-handoff.v1",
        "episode_sha256": hashlib.sha256(
            episode.model_dump_json().encode("utf-8")
        ).hexdigest(),
        "ordered_episode_shot_ids": ids,
        "selected_real_shot_ids": present,
        "missing_real_shot_ids": missing,
        "source_shots": ordered_records,
        "source_real_video_count": len(present),
        "all_episode_shots_present": not missing,
        "ready_for_existing_offline_preview": True,
        "source_clips_keyed_by_shot_id": True,
        "provider_receipts_self_reported_not_authenticated": True,
        "operator_supplied_independent_file_sha_pins": True,
        "new_paid_provider_calls": 0,
        "source_provider_actual_fees_verified": False,
        "new_model_cost_usd": "0",
        "new_video_generated": False,
        "technical_episode_rendered": False,
        "content_quality_human_approved": False,
        "publication_approved": False,
        "g4_exit_approved": False,
    }
    report["report_sha256"] = hashlib.sha256(json.dumps(
        report, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    # Local path bindings live only in the return value, never in the
    # sanitized receipt or network-facing system.
    return ordered_clips, report
