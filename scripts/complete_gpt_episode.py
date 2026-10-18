"""Explicit remaining-nine batch + reuse first three + offline episode delivery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import os

from run_gpt_video_three import load_plan, run_live, SOURCE_HASH
from assemble_gpt_video_three import assemble, probe, sha

FIRST = ["s01", "s02", "s03"]
REST = [f"s{i:02}" for i in range(4, 13)]
OLD_REPORT_SHA = "abb8a516fab68fa92c9fdafa2fb807e0f2d7a210b858475786ee4c873c325b05"


def verify_batch(folder, ids, status, attempts, *, original=False):
    folder = Path(folder)
    report_path = folder / "report.json"
    if folder.is_symlink() or report_path.is_symlink() or not report_path.is_file():
        raise ValueError("Completed source report required")
    if original and sha(report_path) != OLD_REPORT_SHA:
        raise ValueError("First-three report differs from original successful artifact")
    report = json.loads(report_path.read_text("utf-8"))
    if (report.get("status") != status or report.get("generation_attempts") != attempts
            or report.get("source_response_sha256") != SOURCE_HASH
            or [s.get("shot_id") for s in report.get("shots", [])] != ids):
        raise ValueError("Source batch scope mismatch")
    for record in report["shots"]:
        path = folder / (record["shot_id"] + ".mp4")
        if path.is_symlink() or not path.is_file() or sha(path) != record.get("video_sha256"):
            raise ValueError("Clip differs from its source receipt")
        info = probe(path)
        if abs(info["duration_seconds"] - float(record["duration_seconds"])) > .1:
            raise ValueError("Source duration mismatch")
    return report


def stage_episode(prior, generated, destination):
    """Pure local reuse; can run separately after any assembly/staging failure."""
    old = verify_batch(prior, FIRST, "three_clips_completed_pending_human_review", 3, original=True)
    new = verify_batch(generated, REST, "nine_clips_completed_pending_human_review", 9)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for folder, ids in ((Path(prior), FIRST), (Path(generated), REST)):
        for sid in ids:
            shutil.copyfile(folder / (sid + ".mp4"), destination / (sid + ".mp4"))
    report = {**new, "status": "episode_clips_completed_pending_human_review",
        "reused_shot_ids": FIRST, "reused_source_run_id": old.get("run_id"),
        "reused_source_report_sha256": sha(Path(prior) / "report.json"),
        "new_generation_attempts": 9, "shots": old["shots"] + new["shots"],
        "all_script_shots_present": True, "publish_approved": False}
    (destination / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writer-dir", type=Path, required=True)
    parser.add_argument("--prior-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/gpt-episode"))
    parser.add_argument("--generated-dir", type=Path, help="Reuse completed nine-shot artifact; no generation")
    parser.add_argument("--paid", action="store_true")
    parser.add_argument("--reported-spend-today-usd")
    args = parser.parse_args(argv)
    if args.paid and args.generated_dir:
        parser.error("Existing clips and paid generation are mutually exclusive")
    # Verify original completed clips before any claim or supplier request.
    verify_batch(args.prior_dir, FIRST, "three_clips_completed_pending_human_review", 3, original=True)
    plan = load_plan(args.writer_dir, shot_ids=REST)
    if not args.paid and args.generated_dir is None:
        print(json.dumps({"status": "offline_only", "new_shots": REST, "reused_shots": FIRST,
                          "model_calls": 0, "paid_execution_authorized": False}))
        return 0
    if args.paid:
        if args.reported_spend_today_usd is None:
            parser.error("Operator-checked daily spend required")
        generated = args.output_dir / "new-shots"
        run_live(plan, generated, args.reported_spend_today_usd,
                 env=os.environ, completion=True)
    else:
        generated = args.generated_dir
    staged = args.output_dir / "episode"
    stage_episode(args.prior_dir, generated, staged)
    delivery = assemble(staged, args.output_dir / "delivery")
    print(json.dumps(delivery, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
