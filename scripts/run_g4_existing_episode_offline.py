"""G4/R4.4: one local/offline command to reuse already generated REAL shot media.

This is NOT synopsis-to-new-video generation. It composes existing general
EpisodeDraft, existing SHA-pinned real-shot admission, existing approved W3
FFmpeg renderer, existing W4 technical inspection and produces a sanitized
review receipt. No Provider import, network traffic, rights grant, G4 exit
or publication. Missing real shots BLOCK by default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from drama_factory.db import Database
from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.existing_real_shots import admit_existing_real_shots
from drama_factory.pipeline.offline_render import render_approved_preview
from drama_factory.pipeline.offline_review import load_local_offline_review

_SERIES = re.compile(r"proj_[a-f0-9]{14}\Z")
_PROD = re.compile(r"run_[a-f0-9]{14}\Z")
_MAX_MANIFEST = 64 * 1024


class G4ReplayDenied(ValueError):
    """Do not expose private source paths or provider/scene data in errors."""


def _safe_existing(path: Path, *, ext: str) -> Path:
    path = Path(path).absolute()
    if path.suffix != ext or any(part.is_symlink() for part in (path, *path.parents)):
        raise G4ReplayDenied("Linked or invalid local input rejected")
    if not path.is_file():
        raise G4ReplayDenied("Required existing local input not found")
    return path


def _inputs(manifest_path: Path) -> list[dict]:
    manifest = _safe_existing(manifest_path, ext=".json")
    if not 10 <= manifest.stat().st_size <= _MAX_MANIFEST:
        raise G4ReplayDenied("Bounded local shot manifest required")
    try:
        doc = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError):
        raise G4ReplayDenied("Local shot manifest JSON invalid") from None
    if (type(doc) is not dict or set(doc) != {"schema", "shots"}
            or doc["schema"] != "g4-existing-real-shot-inputs.v1"
            or type(doc["shots"]) is not list
            or not 1 <= len(doc["shots"]) <= 12):
        raise G4ReplayDenied("Existing real-shot manifest contract invalid")
    source = []
    for shot in doc["shots"]:
        if type(shot) is not dict or set(shot) != {
            "shot_id", "media_path", "receipt_path", "expected_sha256"
        }:
            raise G4ReplayDenied("Only exact per-shot real-media fields allowed")
        if any(type(shot[k]) is not str or not shot[k] for k in shot):
            raise G4ReplayDenied("All per-shot fields must be nonempty strings")
        if len(shot["media_path"]) > 2048 or len(shot["receipt_path"]) > 2048:
            raise G4ReplayDenied("Local path is too long")
        def local(value):
            p = Path(value)
            return p if p.is_absolute() else manifest.parent / p
        source.append({
            "shot_id": shot["shot_id"],
            "media_path": local(shot["media_path"]),
            "receipt_path": local(shot["receipt_path"]),
            "expected_sha256": shot["expected_sha256"],
        })
    return source


def run_existing_episode_preview(
    *, database_path: Path, production_id: str, series_id: str,
    shot_manifest_path: Path, output_root: Path, allow_placeholders: bool = False,
) -> dict:
    """Offline one-command G4 technical draft + sanitized receipt, NOT release."""
    if (type(production_id) is not str or not _PROD.fullmatch(production_id)
            or type(series_id) is not str or not _SERIES.fullmatch(series_id)
            or type(allow_placeholders) is not bool):
        raise G4ReplayDenied("Exact existing series/production IDs and preview scope required")
    database_path = _safe_existing(Path(database_path), ext=".db")
    root = Path(output_root).absolute()
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise G4ReplayDenied("Linked local render directory denied")
    if root.exists() and not root.is_dir():
        raise G4ReplayDenied("Existing local output is not a directory")

    selections = _inputs(shot_manifest_path)
    # No new databases/productions/approvals are invented; this uses the
    # existing locally-created project/approved production and its real draft.
    db = Database(database_path)
    row = db.one(
        """SELECT p.status, e.project_id, e.body_json
           FROM productions p JOIN episodes e ON p.episode_id=e.id
           WHERE p.id=?""", (production_id,),
    )
    if (row is None or row["project_id"] != series_id
            or row["status"] not in ("ready_for_video_generation", "offline_preview_finished")):
        raise G4ReplayDenied("Existing production must match series and pass both review gates")
    try:
        episode = EpisodeDraft.model_validate_json(row["body_json"])
    except (ValueError, TypeError):
        raise G4ReplayDenied("Existing approved EpisodeDraft invalid") from None
    if (len(episode.shots) > 12 or episode.target_duration_seconds > 90
            or episode.target_duration_seconds < 1):
        raise G4ReplayDenied("Existing G4 technical-preview size limits exceeded")

    # All SHAs and receipts checked BEFORE renderer can write any output.
    clips, handoff = admit_existing_real_shots(
        episode, selections, require_full_episode=not allow_placeholders,
    )
    rendered = render_approved_preview(
        db, production_id, root, source_clips=clips,
    )
    verified = load_local_offline_review(
        db, production_id, root, series_id=series_id,
    )
    if (rendered["mp4_sha256"] != verified["verified_sha256"]
            or rendered["paid_api_calls"] != 0
            or rendered["technical_qa"]["technical_decode_passed"] is not True
            or rendered["technical_qa"]["publish_approved"] is not False
            or verified["publish_approved"] is not False
            or rendered["supplied_local_clips"] != len(clips)
            or rendered["placeholder_visuals"] != bool(handoff["missing_real_shot_ids"])
            or verified["actual_local_media_clips"] != len(clips)):
        raise G4ReplayDenied("Existing W3/W4 technical receipt mismatch")
    report = {
        "schema": "g4-existing-real-episode-offline-replay.v1",
        "series_id": series_id,
        "production_id": production_id,
        "episode_sha256": handoff["episode_sha256"],
        "source_handoff_report_sha256": handoff["report_sha256"],
        "real_source_shot_ids": handoff["selected_real_shot_ids"],
        "missing_real_shot_ids": handoff["missing_real_shot_ids"],
        "has_placeholder_shots": rendered["placeholder_visuals"],
        "all_source_shots_supplied": handoff["all_episode_shots_present"],
        "technical_mp4_sha256": rendered["mp4_sha256"],
        "technical_mp4_duration_seconds": rendered["media"]["duration_seconds"],
        "technical_decode_passed": verified["technical_qa_passed"],
        "original_W3_render_used": True,
        "original_W4_technical_reinspection_used": True,
        "cached_shot_count": sum(bool(s["cached"]) for s in rendered["shots"]),
        "new_model_calls": 0,
        "additional_provider_cost_usd": "0",
        "prior_real_provider_invoices_verified": False,
        "provider_video_origin_independently_authenticated": False,
        "human_content_review_status": "not_run",
        "actual_voice_quality_status": "unknown",
        "release_status": "blocked",
        "publish_approved": False,
        "g4_exit_approved": False,
    }
    report["report_sha256"] = hashlib.sha256(json.dumps(
        report, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    folder = root / series_id / production_id
    receipt = folder / "g4-existing-real-episode-replay.json"
    if receipt.is_symlink():
        raise G4ReplayDenied("Linked output receipt denied")
    # W3 has already created a per-production scoped directory. The receipt is
    # additional evidence only, never an approved release or original W4 report.
    tmp = receipt.with_name("." + receipt.name + ".part")
    if tmp.is_symlink():
        raise G4ReplayDenied("Linked temporary receipt denied")
    tmp.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(receipt)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--production-id", required=True)
    parser.add_argument("--series-id", required=True)
    parser.add_argument("--shot-manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--allow-placeholders", action="store_true",
                        help="Internal technical preview ONLY. Incomplete movie is not real.")
    args = parser.parse_args(argv)
    try:
        report = run_existing_episode_preview(
            database_path=args.database, production_id=args.production_id,
            series_id=args.series_id, shot_manifest_path=args.shot_manifest,
            output_root=args.output_root,
            allow_placeholders=args.allow_placeholders,
        )
    except (G4ReplayDenied, ValueError, OSError, RuntimeError):
        parser.exit(2, "BLOCKED: existing real media/approvals/technical QA invalid\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
