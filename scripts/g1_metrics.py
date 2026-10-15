#!/usr/bin/env python3
"""G1/R1.6 write the canonical 9-trial, PENDING report without media/API calls.

Does not query Gemini, upload content, run any model, invoke ffprobe, or score
fake results as if they came from actual video.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ab_benchmark import build_plan, CONFIRMATION
from drama_factory.pipeline.g1_benchmark_metrics import build_pending_results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1 offline-only results skeleton")
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--shots", type=Path,
                        default=root / "benchmarks/g1/shots.json")
    parser.add_argument("--out", type=Path,
                        default=root / "benchmarks/g1/results.json")
    args = parser.parse_args(argv)
    if args.out.suffix != ".json" or args.out.is_symlink():
        parser.error("Output must be a non-symlink JSON file")
    shots = json.loads(args.shots.read_text(encoding="utf-8"))
    plan = build_plan(shots, confirmation=CONFIRMATION, budget_usd="30.00")
    report = build_pending_results(plan, shots)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("G1 R1.6: 9 pending trials, no real videos or transcripts, $0 provider calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
