"""Replace ONE completed episode clip with already-existing local media (offline).

No provider, credentials, paid requests or implicit generation. The original
batch and all other clips stay immutable; produces a fresh 12-shot delivery.
An operator-supplied replacement is NOT proof of provider provenance or quality.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil

from assemble_gpt_video_three import assemble, probe, sha

SHOT_IDS = [f"s{i:02}" for i in range(1, 13)]
FIRST = SHOT_IDS[:3]
HEX = re.compile(r"[a-f0-9]{64}\Z")


def _file(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular, non-linked media/report file required")
    return path


def replace_completed_shot(source: Path, shot_id: str, replacement: Path,
                           output_root: Path) -> dict:
    """Reassemble 12 verified files after replacing exactly one existing shot.

    The new clip must have the same H264/AAC stream signature. This is a
    local-media handoff, NOT a paid single-shot generation/retry mechanism.
    """
    source, replacement, output_root = map(Path, (source, replacement, output_root))
    if shot_id not in SHOT_IDS:
        raise ValueError("Unknown shot id")
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Regular completed episode directory required")
    report_path = _file(source / "report.json")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    records = report.get("shots")
    if (report.get("status") != "episode_clips_completed_pending_human_review"
            or report.get("generation_attempts") != 9
            or report.get("new_generation_attempts") != 9
            or report.get("reused_shot_ids") != FIRST
            or type(records) is not list
            or [s.get("shot_id") for s in records if type(s) is dict] != SHOT_IDS
            or len(records) != len(SHOT_IDS)
            or not isinstance(report.get("source_response_sha256"), str)
            or not HEX.fullmatch(report["source_response_sha256"])):
        raise ValueError("Verified completed twelve-shot receipt required")

    # Check every existing source before making any destination directory.
    original_hashes = {}
    signature = None
    for record in records:
        name = record["shot_id"]
        path = _file(source / (name + ".mp4"))
        digest = record.get("video_sha256")
        if not isinstance(digest, str) or not HEX.fullmatch(digest) or sha(path) != digest:
            raise ValueError("Original shot hash mismatch")
        info = probe(path)
        if abs(info["duration_seconds"] - float(record["duration_seconds"])) > .1:
            raise ValueError("Original shot duration mismatch")
        if signature is not None and info["stream_signature"] != signature:
            raise ValueError("Original streams incompatible")
        signature = info["stream_signature"]
        original_hashes[name] = digest

    _file(replacement)
    replacement_hash = sha(replacement)
    new_media = probe(replacement)
    if (replacement_hash == original_hashes[shot_id]
            or new_media["stream_signature"] != signature
            or not 3 <= new_media["duration_seconds"] <= 10.1):
        raise ValueError("Replacement must be a new compatible 3–10.1 second clip")

    base = source.resolve()
    output = output_root.resolve()
    if output_root.is_symlink() or output_root.exists() or output == base or base in output.parents:
        raise ValueError("A new output directory outside the original episode is required")

    history = report.get("offline_replacements", [])
    if type(history) is not list or any(type(item) is not dict for item in history):
        raise ValueError("Invalid previous replacement history")

    output_root.mkdir(parents=True, exist_ok=False)
    staged = output_root / "episode"
    staged.mkdir()
    for name in SHOT_IDS:
        shutil.copyfile(replacement if name == shot_id else source / (name + ".mp4"),
                        staged / (name + ".mp4"))

    old_hash = original_hashes[shot_id]
    new_records = [dict(s) for s in records]
    target = new_records[SHOT_IDS.index(shot_id)]
    prior_receipt = dict(target)\n    target.pop("provider_task_id", None)  # Never attribute supplied bytes to old task.\n    target.pop("prompt_sha256", None)  # Old prompt is not the replacement provenance.
    target.update({
        "video_sha256": replacement_hash,
        "duration_seconds": str(new_media["duration_seconds"]),
        "replaced_prior_video_sha256": old_hash,
        "replacement_origin": "operator_supplied_local_media_unverified_provider",
        "actual_fee_usd": None,
    })
    changed = {
        "shot_id": shot_id, "old_sha256": old_hash,
        "new_sha256": replacement_hash,
        "operator_supplied_media_not_provider_authenticated": True,\n        "prior_shot_receipt": prior_receipt,
    }
    staged_report = {**report, "shots": new_records,
        "offline_replacements": [*history, changed],
        "parent_episode_report_sha256": sha(report_path),
        "offline_replacement_model_calls": 0,
        "dialogue_content_verified": False,
        "publish_approved": False}
    (staged / "report.json").write_text(
        json.dumps(staged_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    delivery = assemble(staged, output_root / "delivery")
    return {
        "status": delivery["status"],
        "replaced_shot_id": shot_id,
        "unchanged_shot_count": 11,
        "new_model_calls": 0,
        "delivery_mp4": str(output_root / "delivery" / "gpt-episode-preview.mp4"),
        "delivery_sha256": delivery["mp4_sha256"],
        "technical_decode_passed": delivery["full_decode_passed"],
        "human_review_required": True,
        "publish_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-dir", type=Path, required=True,
                        help="Existing verified 12-shot episode/ folder")
    parser.add_argument("--shot-id", choices=SHOT_IDS, required=True)
    parser.add_argument("--replacement", type=Path, required=True,
                        help="Already-existing compatible MP4; no API calls")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New empty destination path; original remains untouched")
    args = parser.parse_args(argv)
    print(json.dumps(replace_completed_shot(args.episode_dir, args.shot_id,
                                             args.replacement, args.output_dir),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
