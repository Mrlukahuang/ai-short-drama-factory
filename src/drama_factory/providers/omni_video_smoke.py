"""Manual Gemini Omni one-clip -> existing episode MP4 integration smoke test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from drama_factory.pipeline.offline_demo import build_offline_demo
from drama_factory.providers.google_omni_video import (
    GoogleOmniVideoProvider, OmniVideoSpec,
)

VIDEO_PROMPT = (
    "One continuous cinematic shot, approximately 3 seconds, vertical 9:16. "
    "A small bright red toy ball rolls smoothly from left to right across a "
    "wooden table in a sunlit apartment. Close camera, steady natural motion, "
    "subtle natural room ambience; original fictional scene, no people, "
    "no brand logos and no overlaid text."
)


def run_manual_test(
    out: Path, *, paid: bool = False, provider=None,
) -> dict:
    output = Path(out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if not paid:
        preview = build_offline_demo(output)
        return {
            "mode": "offline", "provider_calls": 0,
            "final_mp4": str(output / "demo.mp4"),
            "preview": preview,
        }
    spec = OmniVideoSpec(
        prompt=VIDEO_PROMPT,
        operator_approved=True,
        maximum_acknowledged_spend_usd="2.00",
    )
    selected = provider or GoogleOmniVideoProvider()
    receipt = selected.generate(spec, output / "omni_raw.mp4")
    if receipt["is_mock"] or receipt["model_calls"] != 1 or not receipt["media_path"]:
        raise RuntimeError("Cannot claim success without exactly one real video result")
    preview = build_offline_demo(
        output, source_override=Path(receipt["media_path"]),
    )
    if preview["supplied_local_clips"] != 1:
        raise RuntimeError("Generated video did not reach the compositor")
    return {
        "mode": "paid-manual", "provider_calls": 1,
        "model_receipt": receipt, "final_mp4": str(output / "demo.mp4"),
        "preview": preview,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Google Omni one-clip to playable MP4")
    parser.add_argument("--paid", action="store_true",
                        help="Submit one potentially billable video generation request")
    parser.add_argument("--out", type=Path, default=Path("artifacts/omni-video-smoke"))
    args = parser.parse_args(argv)
    result = run_manual_test(args.out, paid=args.paid)
    print(json.dumps({
        "mode": result["mode"], "provider_calls": result["provider_calls"],
        "final_mp4": result["final_mp4"],
        "video_codec": result["preview"]["media"]["video_codec"],
        "audio_codec": result["preview"]["media"]["audio_codec"],
        "subtitle_codec": result["preview"]["media"]["subtitle_codec"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
