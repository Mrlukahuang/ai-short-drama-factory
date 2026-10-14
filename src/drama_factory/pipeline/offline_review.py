"""Local-only, read-only operator preview inspection before playing a file.

PR-07b1: this is a local Streamlit workbench helper, NOT a public download
endpoint and NOT a publication review. Requires the existing independently
verified technical MP4 manifest and re-runs actual FFmpeg/subtitle QA.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from drama_factory.db import Database
from drama_factory.pipeline.offline_qa import OfflineQAError, inspect_offline_delivery


class LocalReviewDenied(ValueError):
    """Keep error messages independent of paths, dialogue and private files."""


def _expected_workdir(root: Path, series_id: str, production_id: str) -> Path:
    # IDs are used as path components only after their exact grammar is checked.
    if (
        re.fullmatch(r"proj_[0-9a-f]{14}", series_id) is None
        or re.fullmatch(r"run_[0-9a-f]{14}", production_id) is None
    ):
        raise LocalReviewDenied("Invalid preview owner identifiers")
    root = Path(root).absolute()
    return root / series_id / production_id


def load_local_offline_review(
    db: Database, production_id: str, root: Path, *, series_id: str,
) -> dict:
    """Only expose a locally verified, owned, already finished MP4.

    Never read arbitrary operator-selected files or expose private dialogue.
    A complete decode is intentionally performed on every open (bounded to
    the existing offline 90s preview); a previous QA result is not enough.
    """
    if type(production_id) is not str or type(series_id) is not str:
        raise LocalReviewDenied("Invalid local review selection")
    work = _expected_workdir(root, series_id, production_id)
    row = db.one(
        """SELECT p.status,p.result_json,e.project_id,e.id AS episode_id
           FROM productions p JOIN episodes e ON e.id=p.episode_id
           WHERE p.id=?""",
        (production_id,),
    )
    if (
        row is None or row["project_id"] != series_id
        or row["status"] != "offline_preview_finished"
        or not row["result_json"] or len(row["result_json"]) > 512_000
    ):
        raise LocalReviewDenied("Finished preview not available in selected series")
    try:
        manifest = json.loads(row["result_json"])
        expected_file = work / "preview.mp4"
        saved = work / "manifest.json"
        # Reject symlinked workspaces and files, even when their resolved
        # contents are within the local artifact directory.
        if any(p.is_symlink() for p in (
            Path(root), work.parent, work, expected_file, saved,
        )):
            raise LocalReviewDenied("Unsafe linked local review asset")
        if (
            not expected_file.is_file() or not saved.is_file()
            or saved.stat().st_size > 512_000
            or manifest["production_id"] != production_id
            or manifest["series_id"] != series_id
            or manifest["episode_id"] != row["episode_id"]
            or manifest["status"] != "offline_preview_finished"
            or manifest["mp4_path"] != str(expected_file.resolve())
            or json.loads(saved.read_text("utf-8")) != manifest
            or manifest.get("paid_api_calls") != 0
            or manifest.get("spoken_dialogue_generated") is not False
            or manifest.get("technical_qa", {}).get("publish_approved") is not False
        ):
            raise LocalReviewDenied("Local review manifest does not match approved preview")
        qa = inspect_offline_delivery(manifest, expected_file)
        if (
            qa.get("technical_decode_passed") is not True
            or qa.get("publish_approved") is not False
            or qa.get("production_ready") is not False
        ):
            raise LocalReviewDenied("Local preview QA rejected playback")
        shots = manifest["shots"]
        if not isinstance(shots, list) or not 1 <= len(shots) <= 12:
            raise LocalReviewDenied("Invalid preview shot list")
        safe_shots = [{
            "shot_number": index,
            "shot_id": shot["shot_id"],
            "duration_seconds": shot["duration_seconds"],
            "source_kind": shot["media_source"],
            "reused_cached_clip": shot["cached"],
        } for index, shot in enumerate(shots, start=1)]
        return {
            "kind": "local_offline_preview_review",
            "preview_path": str(expected_file),
            "production_id": production_id,
            "series_id": series_id,
            "duration_seconds": manifest["media"]["duration_seconds"],
            "shots": safe_shots,
            "placeholder_visuals": manifest["placeholder_visuals"],
            "actual_local_media_clips": manifest["supplied_local_clips"],
            "technical_qa_passed": True,
            "verified_sha256": manifest["mp4_sha256"],
            "real_ai_footage_verified": False,
            "commercial_rights_verified": False,
            "publish_approved": False,
            "paid_model_requests_by_review": 0,
        }
    except LocalReviewDenied:
        raise
    except (OfflineQAError, KeyError, ValueError, TypeError, OSError, UnicodeError):
        raise LocalReviewDenied("Local preview failed manifest or technical QA") from None
