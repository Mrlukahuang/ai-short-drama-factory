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



def _record_pipeline_audit(
    output: Path, preview: dict, *, mode: str,
    new_generation_calls: int, receipt: dict | None = None,
) -> dict:
    """Audit both the external generation step and the offline compositor.

    The compositor's existing paid_api_calls=0 remains true for that stage.
    The exported artifact adds the actual model generation count; do not
    invent a dollar figure without a verified Google billing record.
    """
    expected_calls = 1 if mode == "paid-manual" else 0
    if new_generation_calls != expected_calls:
        raise RuntimeError("Unexpected video generation call count for this mode")
    audit = {
        "execution_mode": mode,
        "new_model_generation_calls": new_generation_calls,
        "compositor_paid_api_calls": preview["paid_api_calls"],
        "total_new_paid_api_calls": new_generation_calls + preview["paid_api_calls"],
        "vendor_charge_usd": None,
        "vendor_charge_verified": False,
        "vendor_billing_status": (
            "unverified_paid_request" if mode == "paid-manual"
            else "no_new_generation_request"
        ),
        "source_was_previously_generated": mode == "recover-only",
        "source_video_sha256": (
            receipt.get("source_sha256") if receipt else None
        ),
    }
    result = {**preview, "pipeline_audit": audit}
    # This is the delivered artifact manifest. The in-workdir manifest remains
    # explicitly scoped to the zero-model-call compositor stage.
    (output / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return result


def run_manual_test(
    out: Path, *, paid: bool = False,
    recovery_file_id: str | None = None, provider=None,
) -> dict:
    output = Path(out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if recovery_file_id and paid:
        raise ValueError("Recovery must never request paid generation")
    if recovery_file_id:
        selected = provider or GoogleOmniVideoProvider()
        receipt = selected.recover_existing(
            recovery_file_id, output / "omni_raw.mp4",
            operator_approved=True, min_duration_seconds=2,
        )
        if receipt["model_calls"] != 0 or not receipt["media_path"]:
            raise RuntimeError("Recovery must not generate another model request")
        preview = build_offline_demo(
            output, source_override=Path(receipt["media_path"]),
        )
        if preview["supplied_local_clips"] != 1:
            raise RuntimeError("Recovered clip did not reach the compositor")
        preview = _record_pipeline_audit(
            output, preview, mode="recover-only",
            new_generation_calls=0, receipt=receipt,
        )
        return {
            "mode": "recover-only", "provider_calls": 0,
            "model_receipt": receipt, "final_mp4": str(output / "demo.mp4"),
            "preview": preview,
        }
    if not paid:
        preview = build_offline_demo(output)
        preview = _record_pipeline_audit(
            output, preview, mode="offline", new_generation_calls=0,
        )
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
    preview = _record_pipeline_audit(
        output, preview, mode="paid-manual",
        new_generation_calls=1, receipt=receipt,
    )
    return {
        "mode": "paid-manual", "provider_calls": 1,
        "model_receipt": receipt, "final_mp4": str(output / "demo.mp4"),
        "preview": preview,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Google Omni one-clip to playable MP4")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--paid", action="store_true",
                      help="Submit one potentially billable video generation request")
    mode.add_argument("--resume-file-id", type=str,
                      help="Download existing Google video, NO model generation")
    parser.add_argument("--out", type=Path, default=Path("artifacts/omni-video-smoke"))
    args = parser.parse_args(argv)
    result = run_manual_test(
        args.out, paid=args.paid, recovery_file_id=args.resume_file_id,
    )
    print(json.dumps({
        "mode": result["mode"], "provider_calls": result["provider_calls"],
        "pipeline_model_calls": result["preview"]["pipeline_audit"]["total_new_paid_api_calls"],
        "vendor_charge_usd": None,
        "final_mp4": result["final_mp4"],
        "video_codec": result["preview"]["media"]["video_codec"],
        "audio_codec": result["preview"]["media"]["audio_codec"],
        "subtitle_codec": result["preview"]["media"]["subtitle_codec"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
