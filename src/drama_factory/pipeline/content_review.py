"""G4/R4.3 W4: read-only, version-pinned real-shot content review.

No model inference, network access, media writes, publication, or provider calls.
An HMAC authenticates an operator-held reviewer credential, not the fact of viewing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from drama_factory.pipeline.offline_qa import _subtitle_items

IDS = [f"s{i:02}" for i in range(1, 13)]
HEX = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = (
    "visual_character_identity", "appearance_age", "costume_prop_continuity",
    "scene_camera", "split_screen", "overlay_text", "voice_identity",
    "expected_vs_heard_dialogue", "lip_sync", "subtitle_alignment",
)
AUDIO_FIELDS = {"voice_identity", "expected_vs_heard_dialogue", "lip_sync", "subtitle_alignment"}
STATUS = {"pass", "fail", "unknown"}
MAX_MEDIA = 200 * 1024 * 1024
# Prior observations are NEGATIVE-only, bound to the historical source clip SHA.
# These are not new W4 human reviews or a claim of complete frame/audio coverage.
HISTORICAL = {
    "s03": ("9bc4aefb7cb615a6146a0399d242060109ad8e19c720c4f8f81b76f837594ea0",
            "appearance_age", "age_identity_drift", "P0"),
    "s09": ("108490fc1c441dec72fd006206a23089bdf965f47c397842e5af1176723f30f5",
            "appearance_age", "age_identity_drift", "P0"),
    "s07": ("ba02d9778df4fa78e436b104d7ac8a605db3b46d2a3dc06c2a8fa339350defc4",
            "split_screen", "three_panel_split_screen", "P0"),
}
HISTORY_SOURCE = "docs/GPT_EPISODE_VISUAL_REVIEW_20261019.md"


class ContentReviewError(ValueError):
    """Do not emit protected media paths or dialogue in errors."""


def _hex(value: Any) -> bool:
    return type(value) is str and HEX.fullmatch(value) is not None


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha_file(path: Path, *, max_bytes: int = MAX_MEDIA) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ContentReviewError("Missing, symlinked or oversized W3 evidence")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> dict:
    _sha_file(path, max_bytes=256 * 1024)
    try:
        value = json.loads(path.read_text("utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise ContentReviewError("Invalid W3 JSON evidence") from None
    if type(value) is not dict:
        raise ContentReviewError("W3 evidence must be an object")
    return value


def load_w3_bundle(directory: Path, *, artifact_id: int, version: str,
                   expected_mp4_sha256: str, parent: dict | None = None) -> dict:
    """Re-verify the W3 output files; for FAKE require a separately checked parent."""
    if type(artifact_id) is not int or artifact_id <= 0 or version not in {"original", "w1_fake"}:
        raise ContentReviewError("Invalid artifact identity")
    if not _hex(expected_mp4_sha256):
        raise ContentReviewError("Expected MP4 SHA is required")
    render_path = directory / "09_render.json"
    render = _json(render_path)
    qa = _json(directory / "10_qa.json")
    if (render.get("contract") != "g4-w3-render-provenance.v1"
            or render.get("step") != "09_render" or qa.get("step") != "10_qa"
            or qa.get("render_receipt_sha256") != _sha_file(render_path, max_bytes=256 * 1024)
            or qa.get("technical_decode_passed") is not True
            or qa.get("embedded_draft_subtitles_verified") is not True
            or qa.get("publish_approved") is not False
            or qa.get("dialogue_content_verified") is not False
            or qa.get("subtitle_alignment_verified") is not False
            or render.get("asset_manifest_sha256") is not None
            or render.get("production_assets_verified") is not False
            or render.get("subtitle_mode") != "screenplay_timed_draft_not_asr"
            or render.get("audio_stream_copy") is not True):
        raise ContentReviewError("W3 technical/provenance contract mismatch")
    final_sha = _sha_file(directory / "gpt-episode-caption-draft.mp4")
    srt_sha = _sha_file(directory / "draft-captions.srt", max_bytes=128 * 1024)
    if (final_sha != expected_mp4_sha256 or render.get("mp4_sha256") != final_sha
            or qa.get("mp4_sha256") != final_sha
            or render.get("srt_sha256") != srt_sha
            or render.get("subtitle_cues") != qa.get("subtitle_cue_count")
            or not _hex(render.get("source_response_sha256"))
            or render.get("source_response_sha256") != qa.get("source_response_sha256")
            or not _hex(render.get("original_source_report_sha256"))
            or render.get("original_source_report_sha256") != qa.get("original_source_report_sha256")):
        raise ContentReviewError("W3 bytes or source receipts do not match")
    try:
        cues = _subtitle_items((directory / "draft-captions.srt").read_text("utf-8-sig"))
    except (ValueError, OSError, UnicodeError):
        raise ContentReviewError("Malformed DRAFT subtitle evidence") from None
    if len(cues) != render["subtitle_cues"]:
        raise ContentReviewError("DRAFT subtitle cue count mismatch")
    shots = render.get("shots")
    if (type(shots) is not list or len(shots) != 12
            or render.get("shot_order") != IDS):
        raise ContentReviewError("Not an exact 12-shot episode")
    cursor = 0
    for expected, shot in zip(IDS, shots, strict=True):
        if (type(shot) is not dict or shot.get("shot_id") != expected
                or not _hex(shot.get("clip_sha256"))
                or type(shot.get("start_ms")) is not int
                or type(shot.get("end_ms")) is not int
                or type(shot.get("duration_ms")) is not int
                or shot["start_ms"] != cursor
                or shot["end_ms"] - shot["start_ms"] != shot["duration_ms"]
                or shot["duration_ms"] <= 0):
            raise ContentReviewError("Shot order, timeline or media SHA mismatch")
        cursor = shot["end_ms"]
    if render.get("measured_shot_total_ms") != cursor or any(
        start < 0 or end > cursor for start, end, _ in cues
    ):
        raise ContentReviewError("DRAFT timing outside measured episode")
    repair = render.get("repair")
    if type(repair) is not dict:
        raise ContentReviewError("Missing W3 repair provenance")
    if version == "original":
        if (parent is not None or repair.get("replacement_mode") != "original_completed_episode"
                or repair.get("replacements") != [] or repair.get("parent_source_crosschecked") is not False):
            raise ContentReviewError("Original cannot carry a repair lineage")
    else:
        replacements = repair.get("replacements")
        if (parent is None or parent.get("version") != "original"
                or repair.get("replacement_mode") != "operator_existing_media_offline_simulation"
                or repair.get("parent_source_crosschecked") is not True
                or type(replacements) is not list or len(replacements) != 1
                or type(replacements[0]) is not dict
                or replacements[0].get("shot_id") != "s07"
                or replacements[0].get("old_sha256") != parent["shots"][6]["clip_sha256"]
                or replacements[0].get("new_sha256") != shots[6]["clip_sha256"]
                or shots[6]["clip_sha256"] != shots[3]["clip_sha256"]
                or repair.get("parent_preview_sha256") != parent["original_mp4_sha256"]
                or parent["source_response_sha256"] != render["source_response_sha256"]):
            raise ContentReviewError("W1 FAKE parent linkage mismatch")
        for i in range(12):
            if i != 6 and shots[i] != parent["shots"][i]:
                raise ContentReviewError("Unexpected change outside s07")
    return {
        "artifact_id": artifact_id, "version": version, "final_mp4_sha256": final_sha,
        "original_mp4_sha256": render.get("original_mp4_sha256"),
        "source_response_sha256": render["source_response_sha256"],
        "render_receipt_sha256": qa["render_receipt_sha256"],
        "srt_sha256": srt_sha, "subtitle_mode": render["subtitle_mode"],
        "shots": shots, "repair": repair,
        "parent_final_mp4_sha256": parent["final_mp4_sha256"] if parent else None,
    }


def sign_review(record: dict, credential: bytes) -> str:
    """Operator-side helper. Signing alone cannot prove eyes/ears were used."""
    if not credential or not isinstance(credential, bytes):
        raise ContentReviewError("Nonempty reviewer credential required")
    unsigned = {k: v for k, v in record.items() if k != "attestation_hmac_sha256"}
    return hmac.new(credential, _canonical(unsigned), hashlib.sha256).hexdigest()


def _valid_review(record: dict, bundle: dict, shot: dict, reviewer_keys: dict[str, bytes]) -> None:
    if type(record) is not dict or record.get("review_mode") != "human_attested":
        raise ContentReviewError("Only explicit human attestations are accepted")
    reviewer = record.get("reviewer")
    if type(reviewer) is not str or reviewer not in reviewer_keys:
        raise ContentReviewError("Untrusted reviewer identity")
    credential = reviewer_keys[reviewer]
    signature = record.get("attestation_hmac_sha256")
    if not _hex(signature) or not hmac.compare_digest(signature, sign_review(record, credential)):
        raise ContentReviewError("Unsigned or altered human attestation")
    for field, value in (
        ("artifact_id", bundle["artifact_id"]),
        ("final_mp4_sha256", bundle["final_mp4_sha256"]),
        ("parent_final_mp4_sha256", bundle["parent_final_mp4_sha256"]),
        ("shot_id", shot["shot_id"]),
        ("shot_video_sha256", shot["clip_sha256"]),
        ("start_ms", shot["start_ms"]), ("end_ms", shot["end_ms"]),
        ("srt_sha256", bundle["srt_sha256"]),
    ):
        if record.get(field) != value or type(record.get(field)) is not type(value):
            raise ContentReviewError("Stale or mismatched per-shot review")
    try:
        timestamp = datetime.fromisoformat(record["reviewed_at"].replace("Z", "+00:00"))
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ContentReviewError("Invalid review timestamp") from None
    if timestamp.tzinfo is None or timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
        raise ContentReviewError("Timestamp must be UTC with offset")
    evidence = record.get("evidence")
    verdicts = record.get("verdicts")
    if (type(evidence) is not dict or type(evidence.get("note")) is not str
            or not evidence["note"].strip() or len(evidence["note"]) > 500
            or type(evidence.get("watched_video")) is not bool
            or type(evidence.get("listened_audio")) is not bool
            or type(verdicts) is not dict or set(verdicts) != set(FIELDS)
            or any(type(v) is not str or v not in STATUS for v in verdicts.values())
            or record.get("review_source") not in {"local_media_manual", "operator_screening"}):
        raise ContentReviewError("Incomplete reviewer evidence or verdicts")
    if (any(verdicts[k] != "unknown" for k in AUDIO_FIELDS) and not evidence["listened_audio"]
            or any(verdicts[k] != "unknown" for k in set(FIELDS) - AUDIO_FIELDS)
            and not evidence["watched_video"]):
        raise ContentReviewError("Cannot score media that was not observed")


def assess_bundle(bundle: dict, reviews: list[dict], *,
                  reviewer_keys: dict[str, bytes] | None = None) -> dict:
    """Returns deterministic technical/content/release gates and W5 repair hints."""
    keys = reviewer_keys or {}
    if type(reviews) is not list:
        raise ContentReviewError("Reviews must be a list")
    by_id = {}
    for review in reviews:
        if type(review) is not dict or review.get("shot_id") not in IDS:
            raise ContentReviewError("Invalid review shot ID")
        shot_id = review["shot_id"]
        if shot_id in by_id:
            raise ContentReviewError("Multiple attestations for one versioned shot")
        shot = bundle["shots"][IDS.index(shot_id)]
        _valid_review(review, bundle, shot, keys)
        by_id[shot_id] = review
    reviewed = 0
    rows = []
    for shot in bundle["shots"]:
        sid = shot["shot_id"]
        entry = by_id.get(sid)
        if entry:
            reviewed += 1
        values = dict(entry["verdicts"]) if entry else dict.fromkeys(FIELDS, "unknown")
        reasons = []
        provenance = []
        known = HISTORICAL.get(sid)
        if known and shot["clip_sha256"] == known[0]:
            field, reason, priority = known[1:]
            values[field] = "fail"  # historical negatives override optimistic manual passes
            reasons.append(reason)
            provenance.append({"reason": reason, "priority": priority, "source": HISTORY_SOURCE,
                               "kind": "previously_documented_negative_not_new_W4_review"})
        if bundle["version"] == "w1_fake" and sid == "s07":
            reasons.append("existing_s04_as_s07_fake_not_content_repair")
        if entry:
            reasons.extend("human_" + k for k in FIELDS if entry["verdicts"][k] == "fail")
        disposition = ("needs_repair" if reasons else
                       "usable" if entry and all(v == "pass" for v in values.values()) else "unknown")
        rows.append({
            "artifact_id": bundle["artifact_id"], "version": bundle["version"],
            "final_mp4_sha256": bundle["final_mp4_sha256"],
            "parent_final_mp4_sha256": bundle["parent_final_mp4_sha256"],
            "shot_id": sid, "shot_video_sha256": shot["clip_sha256"],
            "start_ms": shot["start_ms"], "end_ms": shot["end_ms"],
            "disposition": disposition, "checks": values,
            "reason_codes": sorted(set(reasons)), "historical_evidence": provenance,
            "human_review_attested": entry is not None,
            "reviewer": entry["reviewer"] if entry else None,
            "reviewed_at": entry["reviewed_at"] if entry else None,
            "review_mode": entry["review_mode"] if entry else None,
            "review_source": entry["review_source"] if entry else None,
            "review_evidence": entry["evidence"] if entry else None,
            "review_record_sha256": hashlib.sha256(_canonical(entry)).hexdigest() if entry else None,
        })
    failures = [row for row in rows if row["disposition"] == "needs_repair"]
    usable = sum(row["disposition"] == "usable" for row in rows)
    report = {
        "contract": "g4-w4-content-review.v1",
        "artifact_id": bundle["artifact_id"], "version": bundle["version"],
        "final_mp4_sha256": bundle["final_mp4_sha256"],
        "parent_final_mp4_sha256": bundle["parent_final_mp4_sha256"],
        "render_receipt_sha256": bundle["render_receipt_sha256"],
        "srt_sha256": bundle["srt_sha256"],
        "shots": rows,
        "human_review_attested_count": reviewed, "usable_shot_count": usable,
        "known_needs_repair_count": len(failures),
        "unknown_shot_count": sum(r["disposition"] == "unknown" for r in rows),
        "technical_qa": "pass",  # W3 byte/receipt/technical flags; not content
        "content_qa": "fail" if failures else "pass" if usable == 12 else "unknown",
        "release_qa": "blocked",
        "publish_approved": False, "g4_exited": False,
        "dialogue_content_verified": False, "subtitle_alignment_verified": False,
        "visual_auto_precheck_status": "not_run",
        "gemini_adjacent_shot_scoring": "not_run",
        "asr_status": "not_run", "r4_3_exit_status": "pending",
        "repair_suggestions": [
            {"shot_id": r["shot_id"], "reason_codes": r["reason_codes"],
             "shot_video_sha256": r["shot_video_sha256"], "action": "operator_review_then_w1_plan_only"}
            for r in failures
        ],
    }
    report["report_sha256"] = hashlib.sha256(_canonical(report)).hexdigest()
    return report
