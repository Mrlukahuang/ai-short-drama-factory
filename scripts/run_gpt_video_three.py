"""Manual three-video test of existing Sol output. Default is offline preparation.

Estimated budget is NOT a provider billing cap; explicit owner acceptance needed.
No OpenAI calls, no whole-episode launch, no automatic generation retries.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from prepare_writer_comparison import case_inputs
from run_writer_pilot import REPO, claim_once, request_json, write_json
from drama_factory.pipeline.screenplay_video_plan import build_screenplay_video_plan
from drama_factory.pipeline.writer_execution_prep import prepare_request, parse_response

CONFIRM = "RUN_GPT_VIDEO3_ESTIMATE_USD2"
MARKER = "[GPT_SCREENPLAY_VIDEO3_20261018_ONE_TIME]"
SOURCE_HASH = "c5665e198eb3d30110a0bb6dc30d5f2cfadf74979eb5e6e0596d64751ff1a6f9"
ROOT = Path(__file__).resolve().parents[1]


def load_plan(source_dir: Path) -> dict:
    path = source_dir / "gpt-6.1-sol.response.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Original Sol response file required")
    response = json.loads(path.read_text("utf-8"))
    canonical = json.dumps(response, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    if hashlib.sha256(canonical.encode()).hexdigest() != SOURCE_HASH:
        raise ValueError("Response differs from approved source artifact")
    req, context = case_inputs("misunderstanding")
    result = parse_response(prepare_request("gpt-6.1-sol", req, context), response,
                            on=datetime(2026, 10, 17).date(), simulated=False)
    if result.status != "validated_draft" or result.screenplay is None:
        raise ValueError("Original Sol screenplay failed validation")
    style = json.loads((ROOT / "config/style_presets/felt_diorama.json").read_text())
    plan = build_screenplay_video_plan(result.screenplay, context,
        style_prompt=style["style_prompt"], actor_descriptions=context.story_bible_json["characters"],
        shot_ids=["s01", "s02", "s03"])
    plan["source_response_sha256"] = SOURCE_HASH
    return plan


def estimate_budget(plan: dict, reported_spend: str, on) -> dict:
    if not datetime(2026, 10, 17).date() <= on <= datetime(2026, 10, 31).date():
        raise ValueError("Reverify stale budget snapshot")
    spend = Decimal(reported_spend)
    if not spend.is_finite() or spend < 0 or spend + 2 > 5:
        raise ValueError("Invalid or insufficient same-day budget")
    if plan["selected_shot_ids"] != ["s01", "s02", "s03"] or len(plan["shots"]) != 3:
        raise ValueError("Exactly the approved first three shots required")
    prompt_bytes = sum(len(s["prompt"].encode()) for s in plan["shots"])
    if prompt_bytes > 100000:
        raise ValueError("Prompt outside estimated input reserve")
    # These are declared estimate assumptions, NOT proven token upper bounds.
    output = Decimal(".0337925") * Decimal("10.1") * 3
    estimated = output + Decimal(".15") + Decimal(".25")
    return {"estimated_total_usd": str(estimated), "output_10_1s_each_usd": str(output),
        "input_reserve_usd": ".15", "text_thinking_reserve_usd": ".25",
        "acknowledged_usd": "2.00", "reported_spend_today_usd": str(spend),
        "budget_upper_bound_verified": False, "provider_billing_cap": False,
        "prompt_bytes": prompt_bytes, "actual_fee_usd": None}


def provider_factory(key):
    from google import genai
    from drama_factory.providers.google_omni_video import GoogleOmniVideoProvider
    # SDK default retries must not submit another paid generation request.
    client = genai.Client(api_key=key, http_options={"retry_options": {"attempts": 1}})
    return GoogleOmniVideoProvider(client=client)


def media_tools():
    import felt_style_omni_test as media
    return media


def run_live(plan, out: Path, spend: str, *, env, post=request_json,
             make_provider=provider_factory, get_media=media_tools):
    if (env.get("GITHUB_REPOSITORY") != REPO or env.get("GITHUB_ACTOR") != "Mrlukahuang"
            or env.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or env.get("GITHUB_REF") != "refs/heads/main" or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or env.get("VIDEO_CONFIRM") != CONFIRM or env.get("ACK_ESTIMATE_NOT_CAP") != "YES"
            or env.get("DRAMA_ENABLE_PAID_GENERATION") != "YES"):
        raise RuntimeError("Owner must explicitly accept estimate risk for one manual attempt")
    if not env.get("GEMINI_API_KEY") or not env.get("GITHUB_TOKEN"):
        raise RuntimeError("Existing secrets required; values never printed")
    budget = estimate_budget(plan, spend, datetime.now(ZoneInfo("Pacific/Auckland")).date())
    out.mkdir(parents=True, exist_ok=False)
    report = {"status": "preflight", "source_response_sha256": plan["source_response_sha256"],
        "run_id": env["GITHUB_RUN_ID"], "source_sha": env.get("GITHUB_SHA"),
        "budget": budget, "generation_attempts": 0, "claim_recorded": False, "shots": [],
        "actual_fee_usd": None, "publish_approved": False, "native_dialogue_verified": False}
    try:
        write_json(out / "report.json", report)
        claim_once(env["GITHUB_TOKEN"], env["GITHUB_RUN_ID"], post,
            marker=MARKER, scope="Sol s01-s03 video; estimated USD2 NOT billing cap, explicit risk acceptance")
        report["claim_recorded"] = True
        write_json(out / "report.json", report)
        provider = make_provider(env["GEMINI_API_KEY"])
        media = get_media()
        from drama_factory.providers.google_omni_video import OmniVideoSpec
        for shot in plan["shots"]:
            report["generation_attempts"] += 1
            report["current_shot"] = shot["shot_id"]
            report["status"] = "request_in_flight"
            write_json(out / "report.json", report)
            target = out / (shot["shot_id"] + ".mp4")
            receipt = provider.generate(OmniVideoSpec(prompt=shot["prompt"],
                min_duration_seconds=3, maximum_acknowledged_spend_usd=Decimal("2"),
                operator_approved=True), target)
            if receipt.get("is_mock") is not False or receipt.get("model_calls") != 1:
                raise ValueError("Unexpected provider receipt")
            info = media.probe(target)
            duration = Decimal(str(info["duration"]))
            if not media.is_portrait(info) or not info["has_audio"] or not Decimal("3") <= duration <= Decimal("10.1"):
                raise ValueError("Video media outside accepted test bounds")
            report["shots"].append({"shot_id": shot["shot_id"], "duration_seconds": str(duration),
                "prompt_sha256": shot["prompt_sha256"], "provider_task_id": receipt.get("provider_task_id"),
                "video_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "actual_fee_usd": None})
            write_json(out / "report.json", report)
        # Preserve original clips without time stretching, trimming dialogue or claiming 15s.
        report["status"] = "three_clips_completed_pending_human_review"
    except Exception as exc:
        report["status"] = "halted_no_retry"
        report["error_category"] = type(exc).__name__
        raise RuntimeError("Video test halted; preserve receipts, do not rerun") from None
    finally:
        write_json(out / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("artifacts/gpt-video3"))
    parser.add_argument("--paid", action="store_true")
    parser.add_argument("--reported-spend-today-usd")
    args = parser.parse_args(argv)
    plan = load_plan(args.source_dir)
    if not args.paid:
        print(json.dumps({"status": "offline_only", "shots": plan["selected_shot_ids"],
                          "paid_api_calls": 0, "paid_execution_authorized": False}))
        return 0
    if args.reported_spend_today_usd is None:
        parser.error("Operator-confirmed same-day spend required")
    run_live(plan, args.out, args.reported_spend_today_usd, env=os.environ)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
