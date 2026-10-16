"""F3 manual six-shot run preflight + truthful final cost/media report.

DOES NOT create any model request. Default AMEND-004 USD2 stays intact;
owner's single F3 Issue #137 exception is USD2.50, guarded separately.
The envelope is conservative pricing estimation, NOT a Google billing cap.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

RATE_360P = Decimal("0.0337925")  # 1931 output tokens/s × $17.50 / 1M
SINGLE_RUN_LIMIT = Decimal("2.00")
OWNER_F3_ISSUE_137_LIMIT = Decimal("2.50")
DAILY_LIMIT = Decimal("5.00")
# Deliberately pessimistic: at most 100k billed prompt tokens and a
# 25-cent text/thinking-output contingency for this one limited experiment.
MAX_PROMPT_TOKENS_RESERVED = 100_000
INPUT_USD_PER_MILLION = Decimal("1.50")
TEXT_OUTPUT_CONTINGENCY_USD = Decimal("0.25")
MAX_DURATION = 10
SIX_SHOTS = 6
MODEL = "gemini-omni-1.1-flash"


class F3BudgetBlocked(RuntimeError):
    pass


def preflight(*, owner_137_exception: bool = False,
              reported_spend_today_usd: Decimal | None = None,
              prompt_input_bytes: int | None = None) -> dict:
    """Fail closed without a same-day spending declaration.

    This cannot enforce a supplier-side dollar cap or prove Google's final
    invoice. Operator must independently verify remaining quota/billing.
    """
    limit = OWNER_F3_ISSUE_137_LIMIT if owner_137_exception else SINGLE_RUN_LIMIT
    worst_video_only = RATE_360P * MAX_DURATION * SIX_SHOTS
    prompt_cap = MAX_PROMPT_TOKENS_RESERVED
    reserve_input = Decimal(prompt_cap) * INPUT_USD_PER_MILLION / 1_000_000
    envelope = worst_video_only + reserve_input + TEXT_OUTPUT_CONTINGENCY_USD
    declared = (
        reported_spend_today_usd is not None
        and reported_spend_today_usd.is_finite()
        and reported_spend_today_usd >= 0
    )
    enough_prompt_room = (
        prompt_input_bytes is None
        or (type(prompt_input_bytes) is int
            and 0 <= prompt_input_bytes <= prompt_cap)
    )
    allowed = (
        declared and enough_prompt_room and envelope <= limit
        and reported_spend_today_usd + limit <= DAILY_LIMIT
    )
    return {
        "stage": "F3", "model": MODEL,
        "resolution": "360p", "aspect_ratio": "9:16", "shots": SIX_SHOTS,
        "owner_exception": "issue_137_one_time" if owner_137_exception else None,
        "single_run_limit_usd": str(limit),
        "today_limit_usd": str(DAILY_LIMIT),
        "reported_spend_today_usd": (
            str(reported_spend_today_usd) if declared else None),
        "worst_case_video_output_usd": str(worst_video_only),
        "max_prompt_input_bytes": prompt_cap,
        "prompt_input_bytes": prompt_input_bytes,
        "max_input_estimate_usd": str(reserve_input),
        "text_output_contingency_usd": str(TEXT_OUTPUT_CONTINGENCY_USD),
        "conservative_estimate_usd": str(envelope),
        "supplier_hard_cap_verified": False,
        "actual_provider_fee_usd": None, "real_requests_made": 0,
        "all_checks_satisfied": allowed,
        "blocking_issue": None if allowed else 137,
    }


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def build_delivery_manifest(run_dir: Path) -> dict:
    """Only after actual six clips completed: never fake verified billing."""
    run_dir = Path(run_dir)
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValueError("Expected safe Omni output directory")
    qa = json.loads((run_dir / "10_qa.json").read_text("utf-8"))
    shots = json.loads((run_dir / "05_shots.json").read_text("utf-8"))
    if qa.get("fake_only") is not False or qa.get("model_calls") != SIX_SHOTS:
        raise ValueError("Real six-shot QA manifest required")
    if shots.get("fake_only") is not False:
        raise ValueError("A stub/fake run is not a real F3 result")
    receipts = shots["payload"]["shots"]
    if len(receipts) != SIX_SHOTS:
        raise ValueError("F3 requires six completed real shots")
    from importlib.util import spec_from_file_location, module_from_spec
    path = Path(__file__).resolve().with_name("felt_style_omni_test.py")
    spec = spec_from_file_location("f3_felt_omni_tool", path)
    if spec is None or spec.loader is None:
        raise ValueError("Style verification unavailable")
    style = module_from_spec(spec)
    spec.loader.exec_module(style)
    final = run_dir / "episode.omni.mp4"
    if final.is_symlink() or not final.is_file():
        raise ValueError("Real F3 final MP4 missing")
    info = style.probe(final)
    if not style.is_portrait(info) or not info["has_audio"]:
        raise ValueError("Final is not portrait with native audio")
    report = []
    for row in receipts:
        source = run_dir / (row["shot_id"] + ".mp4")
        if (source.is_symlink() or not source.is_file()
                or row["video_sha256"] != _sha(source)
                or row["is_mock"] or row["model_calls"] != 1):
            raise ValueError("Missing/unverified paid shot media")
        probe = style.probe(source)
        if not style.is_portrait(probe) or not probe["has_audio"]:
            raise ValueError("Non-portrait or no native audio shot")
        report.append({
            "shot": row["shot_id"],
            "provider_task_id": row["provider_task_id"],
            "width": probe["width"], "height": probe["height"],
            "duration_seconds": probe["duration"],
            "portrait": True, "native_audio_present": True,
            "estimated_fee_usd": row["estimated_usd"],
            "actual_fee_usd": None,  # Google API receipt has no billed total
        })
    return {
        "stage": "F3", "model": MODEL, "style": "felt_diorama",
        "shots": report, "shot_count": SIX_SHOTS,
        "video": final.name, "video_sha256": _sha(final),
        "final_width": info["width"], "final_height": info["height"],
        "native_audio_present": info["has_audio"],
        "estimated_total_usd": str(sum(
            Decimal(x["estimated_fee_usd"]) for x in report)),
        "actual_total_usd": None,
        "billing_source": "Google billing pending; API receipt is not invoice",
        "character_consistency": "awaiting owner review",
        "mandarin_dialogue_quality": "awaiting owner review",
        "publish_approved": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="F3 budget preflight and MP4 report")
    p.add_argument("--preflight", action="store_true")
    p.add_argument("--owner-approved-f3-137", action="store_true",
                   help="One-time F3-only USD2.50 exception, not a general limit")
    p.add_argument("--reported-spend-today-usd", type=Decimal,
                   default=None, help="Operator-verified same-day USD spent so far")
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    if args.preflight == (args.run_dir is not None):
        p.error("Specify exactly --preflight or --run-dir")
    result = (
        preflight(owner_137_exception=args.owner_approved_f3_137,
                  reported_spend_today_usd=args.reported_spend_today_usd)
        if args.preflight else build_delivery_manifest(args.run_dir)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    if args.preflight and not result["all_checks_satisfied"]:
        raise F3BudgetBlocked("F3 blocked: owner exception, spend declaration or conservative budget envelope did not pass (#137)")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
