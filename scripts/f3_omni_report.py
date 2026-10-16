"""F3 manual six-shot run preflight + truthful final cost/media report.

DOES NOT create any model request. The CLI generation only runs after an
independent preflight permits it; AMEND-004 USD2 is a hard boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

RATE_360P = Decimal("0.0337925")  # 1931 output tokens/s × $17.50 / 1M
SINGLE_RUN_LIMIT = Decimal("2.00")
DAILY_LIMIT = Decimal("5.00")
MAX_DURATION = 10
SIX_SHOTS = 6
MODEL = "gemini-omni-1.1-flash"


class F3BudgetBlocked(RuntimeError):
    pass


def preflight() -> dict:
    """Reject six paid model calls before any network/credential access."""
    worst_video_only = RATE_360P * MAX_DURATION * SIX_SHOTS
    verdict = {
        "stage": "F3", "model": MODEL,
        "resolution": "360p", "aspect_ratio": "9:16", "shots": SIX_SHOTS,
        "single_run_limit_usd": str(SINGLE_RUN_LIMIT),
        "today_limit_usd": str(DAILY_LIMIT),
        "worst_case_video_output_usd": str(worst_video_only),
        "input_usd": None, "actual_provider_fee_usd": None,
        "real_requests_made": 0,
        "all_checks_satisfied": worst_video_only < SINGLE_RUN_LIMIT,
        "blocking_issue": 137 if worst_video_only >= SINGLE_RUN_LIMIT else None,
    }
    return verdict


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
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    if args.preflight == (args.run_dir is not None):
        p.error("Specify exactly --preflight or --run-dir")
    result = preflight() if args.preflight else build_delivery_manifest(args.run_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    if args.preflight and not result["all_checks_satisfied"]:
        raise F3BudgetBlocked("F3 exceeds AMEND-004 <=USD2: see owner Issue #137")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
