#!/usr/bin/env python3
"""G1/R1.6 offline Chinese CER and ffprobe QA; no transcription API calls.

A manually supplied transcript is NOT proof that Gemini 3.5 transcribed a
real video. Real model/transcription provenance stays unverified here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import unicodedata

MODELS = ("gemini-omni-1.1-flash", "doubao-seedance-2-5-260628", "kling-v3-omni")
EXPECTED = {
    "G1-S1": "你确定要走吗？我会回来。",
    "G1-S2": "我其实一直都相信你。",
    "G1-S3": "",
}


def _characters(value: str) -> str:
    if type(value) is not str:
        raise ValueError("Transcript must be text")
    return "".join(c for c in unicodedata.normalize("NFKC", value)
                   if not unicodedata.category(c).startswith(("P", "Z", "C")))


def character_accuracy(reference: str, hypothesis: str) -> dict:
    """Unicode codepoint CER (edit distance / reference length), not word accuracy."""
    ref, hyp = _characters(reference), _characters(hypothesis)
    if not ref:
        raise ValueError("No spoken reference for this shot")
    row = list(range(len(hyp) + 1))
    for i, a in enumerate(ref, 1):
        nxt = [i]
        for j, b in enumerate(hyp, 1):
            nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j-1] + (a != b)))
        row = nxt
    edits = row[-1]
    return {"reference_characters": len(ref), "transcript_characters": len(hyp),
            "edit_distance": edits, "character_error_rate": round(edits / len(ref), 6),
            "character_accuracy": round(max(0.0, 1 - edits / len(ref)), 6)}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe_media(path: Path, *, requires_audio: bool = False) -> dict:
    """Inspect a local MP4 without network fetch or any model/SDK dispatch."""
    if path.suffix.lower() != ".mp4" or not path.is_file() or path.is_symlink():
        raise ValueError("Expected existing non-symlink local MP4")
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height",
             "-of", "json", str(path.resolve())],
            capture_output=True, text=True, timeout=15, check=True,
        )
        info = json.loads(proc.stdout)
        video = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
        audio = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
        duration = float(info.get("format", {}).get("duration", 0))
        width = video[0].get("width") if video else None
        height = video[0].get("height") if video else None
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise ValueError("Local ffprobe failed or returned invalid media metadata") from exc
    issues = []
    if len(video) != 1:
        issues.append("expected_one_video_stream")
    if not (isinstance(width, int) and isinstance(height, int) and
            width > 0 and height > 0 and abs(width / height - 9 / 16) < 0.02):
        issues.append("wrong_vertical_aspect_ratio")
    if not math.isfinite(duration) or not 4.0 <= duration <= 6.0:
        issues.append("outside_five_second_tolerance")
    if requires_audio and not audio:
        issues.append("missing_dialogue_audio_stream")
    return {"passed": not issues, "issues": issues, "duration_seconds": round(duration, 3),
            "width": width, "height": height,
            "video_codec": video[0].get("codec_name") if video else None,
            "audio_codec": audio[0].get("codec_name") if audio else None,
            "has_audio": bool(audio), "sha256": _file_sha256(path)}


def build_results(shots: dict, observations: list[dict] | None = None) -> dict:
    entries = shots.get("shots") if type(shots) is dict else None
    if (type(shots) is not dict or shots.get("schema") != "g1.fixed-shots.v1" or
            type(entries) is not list or
            [s.get("shot_id") for s in entries if type(s) is dict] != list(EXPECTED) or
            len(entries) != 3 or
            any(s.get("duration_seconds") != 5 for s in entries)):
        raise ValueError("R1.6 only supports G1 fixed three-shot benchmark")
    seen: dict[tuple[str, str], dict] = {}
    if observations is None:
        observations = []
    if type(observations) is not list:
        raise ValueError("Observations must be a list")
    for item in observations:
        if type(item) is not dict or set(item) - {"shot_id", "provider_model", "media_path", "transcript"}:
            raise ValueError("Invalid offline observation fields")
        key = (item.get("shot_id"), item.get("provider_model"))
        if key[0] not in EXPECTED or key[1] not in MODELS or key in seen:
            raise ValueError("Unknown or duplicate G1 observation")
        if "transcript" in item and type(item["transcript"]) is not str:
            raise ValueError("Transcript must be text")
        seen[key] = item
    rows = []
    for shot_id in EXPECTED:
        for model in MODELS:
            item = seen.get((shot_id, model), {})
            media = item.get("media_path")
            if media is not None and (type(media) is not str or not media):
                raise ValueError("Invalid local media path")
            technical = probe_media(Path(media), requires_audio=bool(EXPECTED[shot_id])) if media else None
            transcript = item.get("transcript")
            accuracy = (character_accuracy(EXPECTED[shot_id], transcript)
                        if transcript is not None and EXPECTED[shot_id] else None)
            rows.append({
                "shot_id": shot_id, "provider_model": model,
                "technical_qa": technical, "chinese_character_metrics": accuracy,
                "transcript_source": "operator_supplied_unverified" if transcript is not None else None,
                "transcription_model_verified": None,
                "real_video_origin_verified": False,
                "real_benchmark_evaluation_verified": False,
                "status": "offline_observation_unverified" if item else "pending_real_media",
            })
    return {"schema": "g1.qa-results.v1", "stage": "G1", "req": "R1.6",
            "real_benchmark_completed": False, "transcription_api_calls": 0,
            "video_generation_calls": 0, "paid_api_cost_usd": "0",
            "note": "Offline metrics only; Gemini 3.5 transcription and real AI video provenance NOT verified.",
            "results": rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G1 offline CER/ffprobe QA; no API calls")
    parser.add_argument("--shots", type=Path, default=Path(__file__).resolve().parents[1] / "benchmarks/g1/shots.json")
    parser.add_argument("--observations", type=Path, help="Local-only JSON list; do not commit private paths or transcripts")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.suffix.lower() != ".json":
        parser.error("Output must be JSON")
    observations = json.loads(args.observations.read_text("utf-8")) if args.observations else []
    data = build_results(json.loads(args.shots.read_text("utf-8")), observations)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("G1/R1.6 offline QA only: 0 model calls; real benchmark unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
