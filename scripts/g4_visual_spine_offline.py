#!/usr/bin/env python3
"""G4 complete visual spine OFFLINE replay. No upload, network or model calls.

Use verified PNGs and operator-signed per-shot grants from an independently
approved local process. This CLI cannot mint approvals. It never writes image
bytes, Base64 or credentials to reports and never alters historical artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from drama_factory.pipeline.visual_media_admission import MediaAdmissionError
from drama_factory.pipeline.visual_spine_offline import fake_episode_visual_replay


def _read(path: str):
    file = Path(path)
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 2_000_000:
        raise MediaAdmissionError("Invalid or oversized local input JSON")
    try:
        return json.loads(file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise MediaAdmissionError("Cannot parse local visual spine input") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline G4 12-shot visual asset and Omni request replay (USD0)",
    )
    for arg in ("w2-manifest", "shot-specs", "gallery", "prompts",
                "image-index", "operator-grants"):
        parser.add_argument("--" + arg, required=True)
    parser.add_argument("--approved-frames")
    parser.add_argument("--require-first-frame", action="store_true")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        raw_key = os.environ.get("DRAMA_VISUAL_OPERATOR_HMAC_KEY_HEX", "")
        if len(raw_key) < 64:
            raise MediaAdmissionError("Independent local operator key not configured")
        try:
            key = bytes.fromhex(raw_key)
        except ValueError:
            raise MediaAdmissionError("Invalid independent operator key encoding") from None
        image_paths = _read(args.image_index)
        if type(image_paths) is not dict:
            raise MediaAdmissionError("Image index must be a SHA-to-path object")
        report = fake_episode_visual_replay(
            _read(args.w2_manifest), _read(args.shot_specs), _read(args.gallery),
            prompts=_read(args.prompts),
            image_paths_by_sha256={sha: Path(file) for sha, file in image_paths.items()},
            grants_by_shot=_read(args.operator_grants),
            operator_verification_key=key,
            approved_frames=(_read(args.approved_frames) if args.approved_frames else None),
            first_frame_required=args.require_first_frame,
        )
        output = Path(args.out)
        if output.is_symlink() or output.exists() or not output.parent.is_dir():
            raise MediaAdmissionError("Output path exists or is unsafe")
        output.write_text(
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status": "offline_complete", "shot_count": report["shot_count"],
            "replay_sha256": report["replay_sha256"],
            "model_calls": 0, "actual_fee_usd": None,
            "provider_reference_applied": False,
        }, sort_keys=True))
        return 0
    except (MediaAdmissionError, TypeError, KeyError, OSError) as exc:
        # Keep local private file paths, media, and credentials out of stderr.
        print("G4 visual spine offline replay BLOCKED: invalid input, grant, or media",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
