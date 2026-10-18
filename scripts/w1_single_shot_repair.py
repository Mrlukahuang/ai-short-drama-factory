"""G4/R4.4 W1: one-shot repair handoff, OFFLINE/Fake only.

Reuse existing validated Sol plan, completed episode receipts, FFmpeg repair,
and draft-caption postproduction. No SDK, paid provider calls, old USD5 claim,
new database, retries, or publication authority.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from assemble_gpt_video_three import probe, sha
from repair_gpt_episode_offline import SHOT_IDS, FIRST, replace_completed_shot
from postprocess_gpt_episode_offline import render_draft_postprocess, _verified_screenplay
from run_gpt_video_three import load_plan

SHA = re.compile(r"[a-f0-9]{64}\Z")
SCHEMA = "g4-single-shot-repair.v1"
MAX_JSON = 1024 * 1024


def _json(path: Path) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError("Missing, symlinked or oversized JSON")
    result = json.loads(path.read_text("utf-8"))
    if type(result) is not dict:
        raise ValueError("JSON object required")
    return result


def _digest(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                 separators=(",", ":")).encode("utf-8")).hexdigest()


def _verify_original(episode_dir: Path, delivery_dir: Path, source_hash: str):
    """Read-only parent verification. Reuse actual assembly probe/sha semantics."""
    episode_dir, delivery_dir = Path(episode_dir), Path(delivery_dir)
    if episode_dir.is_symlink() or delivery_dir.is_symlink():
        raise ValueError("Symlinked episode/delivery denied")
    report_path = episode_dir / "report.json"
    manifest_path = delivery_dir / "delivery.json"
    report, delivery = _json(report_path), _json(manifest_path)
    records = report.get("shots")
    if (report.get("status") != "episode_clips_completed_pending_human_review"
            or report.get("generation_attempts") != 9
            or report.get("new_generation_attempts") != 9
            or report.get("reused_shot_ids") != FIRST
            or report.get("source_response_sha256") != source_hash
            or type(records) is not list or len(records) != 12
            or any(type(x) is not dict for x in records)
            or [x["shot_id"] for x in records] != SHOT_IDS):
        raise ValueError("Original completed 12-shot batch failed verification")
    preview = delivery_dir / "gpt-episode-preview.mp4"
    if preview.is_symlink() or not preview.is_file():
        raise ValueError("Missing original delivery MP4")
    if (delivery.get("source_report_sha256") != sha(report_path)
            or delivery.get("source_response_sha256") != source_hash
            or delivery.get("shot_order") != SHOT_IDS
            or delivery.get("mp4_sha256") != sha(preview)
            or delivery.get("full_decode_passed") is not True
            or delivery.get("publish_approved") is not False):
        raise ValueError("Original delivery does not match source report")
    originals = {}
    stream = None
    for shot in records:
        name = shot["shot_id"]
        path = episode_dir / (name + ".mp4")
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing original shot")
        digest = shot.get("video_sha256")
        if type(digest) is not str or not SHA.fullmatch(digest) or sha(path) != digest:
            raise ValueError("Original shot digest mismatch")
        measured = probe(path)
        if abs(float(shot["duration_seconds"]) - measured["duration_seconds"]) > .1:
            raise ValueError("Original shot duration mismatch")
        if stream is not None and stream != measured["stream_signature"]:
            raise ValueError("Original shots are not concat compatible")
        stream = measured["stream_signature"]
        originals[name] = digest
    if probe(preview)["stream_signature"] != stream:
        raise ValueError("Original assembled format mismatches shots")
    return report, delivery, originals


def build_repair_plan(screenplay, single_plan: dict, episode_dir: Path,
                      delivery_dir: Path, review: dict) -> dict:
    """Prepare immutable, *unpaid* single-shot intent from existing evidence."""
    if type(review) is not dict:
        raise ValueError("Explicit human review record required")
    shot_id = review.get("shot_id")
    if (shot_id not in SHOT_IDS or review.get("decision") != "needs_repair"
            or type(review.get("reason")) is not str or not review["reason"].strip()
            or type(review.get("reviewed_by")) is not str
            or not review["reviewed_by"].strip()):
        raise ValueError("Named review of one failed shot required")
    if (single_plan.get("selected_shot_ids") != [shot_id]
            or len(single_plan.get("shots", [])) != 1
            or single_plan["shots"][0].get("shot_id") != shot_id):
        raise ValueError("Exactly one selected shot required")
    source_hash = single_plan.get("source_response_sha256")
    if type(source_hash) is not str or not SHA.fullmatch(source_hash):
        raise ValueError("Invalid writer source digest")
    if [s.shot_id for s in screenplay.shots] != SHOT_IDS:
        raise ValueError("Validated screenplay must contain exactly original twelve shots")
    source, parent, originals = _verify_original(episode_dir, delivery_dir, source_hash)
    if (review.get("source_video_sha256") != originals[shot_id]
            or ("parent_report_sha256" in review
                and review["parent_report_sha256"] != sha(Path(episode_dir) / "report.json"))):
        raise ValueError("Review is stale or refers to another clip version")
    shot = next(s for s in screenplay.shots if s.shot_id == shot_id)
    requested = single_plan["shots"][0]
    prompt = requested.get("prompt")
    if (type(prompt) is not str or not prompt
            or hashlib.sha256(prompt.encode()).hexdigest() != requested.get("prompt_sha256")):
        raise ValueError("Prepared provider prompt fingerprint invalid")
    screenplay_hash = hashlib.sha256(screenplay.model_dump_json().encode()).hexdigest()
    estimated = Decimal("0.0337925") * Decimal("10.1") + Decimal(".40")
    return {
        "schema_version": SCHEMA, "work_package": "W1", "stage": "G4", "req": "R4.4",
        "shot_id": shot_id, "review": {"decision": "needs_repair",
            "reason": review["reason"], "reviewed_by": review["reviewed_by"]},
        "source_response_sha256": source_hash,
        "screenplay_sha256": screenplay_hash,
        "parent_episode_report_sha256": sha(Path(episode_dir) / "report.json"),
        "parent_delivery_manifest_sha256": sha(Path(delivery_dir) / "delivery.json"),
        "parent_video_sha256": parent["mp4_sha256"],
        "original_shot_sha256": originals[shot_id],
        "unchanged_shots_sha256": {k:v for k,v in originals.items() if k != shot_id},
        "previous_shot_receipt": dict(source["shots"][SHOT_IDS.index(shot_id)]),
        "request": {"model_id": "gemini-omni-1.1-flash", "prompt": prompt,
                    "prompt_sha256": requested["prompt_sha256"],
                    "duration_floor_seconds": 3, "aspect_ratio": "9:16",
                    "reference_images_supplied": False, "audio_reference_supplied": False,
                    "asset_versions_verified": False,
                    "speaker_cues": [{"speaker_id": cue.speaker_actor_id,
                                      "expected_text": cue.text,
                                      "start_second": cue.start_second,
                                      "end_second": cue.end_second}
                                     for cue in shot.dialogue]},
        "finance": {"output_estimate_plus_reserves_usd": str(estimated),
                    "estimated_not_invoice": True,
                    "supplier_hard_charge_cap_verified": False,
                    "independent_paid_approval": None,
                    "paid_execution_authorized": False,
                    "prior_usd5_authorization_reusable": False,
                    "invoiced_actual_usd": None},
        "status": "awaiting_new_independent_paid_approval",
        "new_paid_model_calls": 0, "publish_approved": False,
    }


def complete_offline_fake(plan: dict, screenplay, single_plan: dict, review: dict,
                          episode_dir: Path, delivery_dir: Path,
                          replacement: Path, output: Path) -> dict:
    """Fake reception -> existing single-shot replace -> existing post -> QA.

    The operator-provided replacement is *not* a new provider-generated result.
    For real paid mode, this entrypoint always denies; an independently authorized
    executor will be a later, separately approved change.
    """
    expected = build_repair_plan(screenplay, single_plan, episode_dir, delivery_dir, review)
    if plan != expected or plan["finance"]["paid_execution_authorized"] is not False:
        raise ValueError("Stale/modified plan or unauthorized paid mode")
    replacement = Path(replacement)
    if replacement.is_symlink() or not replacement.is_file():
        raise ValueError("Missing safe Fake media source")
    if replacement.resolve() == (Path(episode_dir)/ (plan["shot_id"] + ".mp4")).resolve():
        raise ValueError("Replacement cannot be same source path")
    output = Path(output)
    if output.is_symlink() or output.exists():
        raise ValueError("New output directory required")
    # Existing repair independently verifies every original and replacement.
    result = replace_completed_shot(episode_dir, plan["shot_id"], replacement,
                                    output / "repair")
    repaired = output / "repair"
    edited_report = _json(repaired / "episode" / "report.json")
    new_hash = sha(replacement)
    hashes = {r["shot_id"]: r["video_sha256"] for r in edited_report["shots"]}
    if (hashes[plan["shot_id"]] != new_hash
            or {k:v for k,v in hashes.items() if k != plan["shot_id"]}
            != plan["unchanged_shots_sha256"]):
        raise ValueError("Unchanged eleven-shot hash invariant violated")
    post = render_draft_postprocess(
        screenplay, plan["source_response_sha256"],
        repaired / "episode", repaired / "delivery", output / "post")
    parent = _json(repaired / "delivery" / "delivery.json")
    handoff = {
        "schema_version": "drama-w1-repair-result.v1", "status": "offline_fake_repaired",
        "source_mode": "operator_existing_media_offline_simulation",
        "new_provider_task_id": None, "new_paid_model_calls": 0,
        "new_api_cost_usd": "0", "new_actual_invoice_usd": None,
        "independent_paid_authorization": None,
        "shot_id": plan["shot_id"],
        "parent_episode_report_sha256": plan["parent_episode_report_sha256"],
        "parent_delivery_sha256": plan["parent_video_sha256"],
        "prior_shot_receipt": plan["previous_shot_receipt"],
        "new_shot_sha256": new_hash,
        "unchanged_shots_sha256": plan["unchanged_shots_sha256"],
        "repaired_report_sha256": sha(repaired / "episode" / "report.json"),
        "repaired_delivery_sha256": parent["mp4_sha256"],
        "draft_postprocessed_mp4_sha256": post["mp4_sha256"],
        "technical_qa_passed": post["technical_decode_passed"],
        "content_qa_passed": False, "dialogue_content_verified": False,
        "subtitle_alignment_verified": False, "publish_approved": False,
    }
    output.mkdir(exist_ok=True)  # repair created this parent on success.
    (output / "w1-result.json").write_text(
        json.dumps(handoff, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "fake-apply"):
        cmd = subs.add_parser(name)
        cmd.add_argument("--writer-dir", type=Path, required=True)
        cmd.add_argument("--episode-dir", type=Path, required=True)
        cmd.add_argument("--delivery-dir", type=Path, required=True)
        cmd.add_argument("--review-file", type=Path, required=True)
        if name == "prepare":
            cmd.add_argument("--output-plan", type=Path, required=True)
        else:
            cmd.add_argument("--plan-file", type=Path, required=True)
            cmd.add_argument("--replacement", type=Path, required=True)
            cmd.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    review = _json(args.review_file)
    screenplay, source_hash = _verified_screenplay(args.writer_dir)
    single_plan = load_plan(args.writer_dir, shot_ids=[review["shot_id"]])
    if single_plan.get("source_response_sha256") != source_hash:
        raise ValueError("Wrong approved source")
    expected = build_repair_plan(screenplay, single_plan, args.episode_dir,
                                  args.delivery_dir, review)
    if args.command == "prepare":
        dest = args.output_plan
        if dest.is_symlink() or dest.exists():
            raise ValueError("Refuse to overwrite an existing plan")
        dest.write_text(json.dumps(expected, ensure_ascii=False, sort_keys=True, indent=2)+"\n",
                        encoding="utf-8")
        result = {"status": expected["status"], "plan_sha256": sha(dest),
                  "paid_model_calls": 0, "paid_execution_authorized": False}
    else:
        result = complete_offline_fake(_json(args.plan_file), screenplay, single_plan,
                    review, args.episode_dir, args.delivery_dir,
                    args.replacement, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
