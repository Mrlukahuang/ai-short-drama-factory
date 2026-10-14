#!/usr/bin/env python3
"""G1/R1.5 fixed 3×3 benchmark planner, SAFE PLAN ONLY.

No paid model dispatch until independent verified vendor budget enforcement
and AMEND-004 owner approval (Issue #120); deliberately no --execute path.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

MAX_BENCHMARK_USD = Decimal("30.00")
CONFIRMATION = "G1-PLAN-ONLY"
PROVIDERS = (
    "gemini-omni-1.1-flash",
    "doubao-seedance-2-5-260628",
    "kling-v3-omni",
)


def build_plan(shots: dict, *, confirmation: str, budget_usd: str) -> dict:
    if confirmation != CONFIRMATION:
        raise ValueError("Manual G1 plan confirmation phrase mismatch")
    try:
        budget = Decimal(budget_usd)
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid G1 budget amount") from None
    if not budget.is_finite() or not Decimal("0") < budget <= MAX_BENCHMARK_USD:
        raise ValueError("G1 aggregate plan budget outside $30 cap")
    if (type(shots) is not dict or shots.get("schema") != "g1.fixed-shots.v1"
            or shots.get("aspect_ratio") != "9:16"):
        raise ValueError("Invalid fixed G1 benchmark input")
    entries = shots.get("shots")
    if type(entries) is not list or len(entries) != 3:
        raise ValueError("G1 benchmark must have exactly three shots")
    expected_ids = ("G1-S1", "G1-S2", "G1-S3")
    if tuple(x.get("shot_id") for x in entries if type(x) is dict) != expected_ids:
        raise ValueError("G1 benchmark shot identities or order changed")
    for shot in entries:
        if (type(shot.get("duration_seconds")) is not int
                or shot["duration_seconds"] != 5
                or type(shot.get("prompt")) is not str
                or not 1 <= len(shot["prompt"]) <= 9000
                or not isinstance(shot.get("test_focus"), list)
                or not shot["test_focus"]):
            raise ValueError("Invalid fixed G1 shot contract")
    plan = [
        {
            "shot_id": shot["shot_id"], "provider_model": model,
            "attempt": 1, "prompt": shot["prompt"],
            "duration_seconds": shot["duration_seconds"],
            "aspect_ratio": shots["aspect_ratio"],
            "reference_asset_versions": None,
            "run_status": "blocked_pending_owner_approval_and_assets",
            "media_path": None, "provider_task_id": None,
            "actual_fee_usd": None, "model_calls": 0,
            "is_real_ai_result": False,
        }
        for shot in entries for model in PROVIDERS
    ]
    assert len(plan) == 9
    return {
        "schema": "g1.benchmark-plan.v1",
        "execution_mode": "plan_only_no_paid_dispatch",
        "manual_confirmation_checked": True,
        "benchmark_budget_limit_usd": str(budget),
        "vendor_hard_billing_cap_verified": False,
        "owner_paid_approval_issue": 120,
        "shot_count": 3, "provider_count": 3, "planned_tasks": 9,
        "model_generation_calls": 0,
        "actual_paid_spend_usd": "0",
        "tasks": plan,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline G1 benchmark plan (never bill)")
    parser.add_argument(
        "--shots", type=Path,
        default=Path(__file__).resolve().parents[1] / "benchmarks/g1/shots.json",
    )
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--budget-usd", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    plan = build_plan(
        json.loads(args.shots.read_text(encoding="utf-8")),
        confirmation=args.confirm, budget_usd=args.budget_usd,
    )
    if args.out.suffix.lower() != ".json":
        parser.error("Plan output must be a JSON file")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    print(
        f"G1 PLAN ONLY: {plan['planned_tasks']} planned tasks, "
        "0 generated clips, $0 paid, owner approval still required"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
