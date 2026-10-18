"""Offline assembly/QA of completed GPT three-shot artifacts. No model imports."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

IDS = ["s01", "s02", "s03"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(path):
    data = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True))
    video = [s for s in data["streams"] if s["codec_type"] == "video"]
    audio = [s for s in data["streams"] if s["codec_type"] == "audio"]
    if len(video) != 1 or len(audio) != 1:
        raise ValueError("Exactly one video stream and native audio stream required")
    v, a = video[0], audio[0]
    if (v["codec_name"], v["width"], v["height"], a["codec_name"]) != ("h264", 360, 640, "aac"):
        raise ValueError("Expected existing 360x640 H264/AAC clips")
    return {"duration_seconds": float(data["format"]["duration"]),
        "stream_signature": [v["codec_name"], v.get("profile"), v["width"], v["height"],
            v.get("pix_fmt"), v.get("time_base"), v.get("r_frame_rate"),
            a["codec_name"], a.get("sample_rate"), a.get("channels"), a.get("channel_layout")]}


def assemble(source: Path, output: Path) -> dict:
    source, output = Path(source), Path(output)
    report_path = source / "report.json"
    if source.is_symlink() or report_path.is_symlink() or not report_path.is_file():
        raise ValueError("Regular completed source artifact required")
    report = json.loads(report_path.read_text("utf-8"))
    if (report.get("status") != "three_clips_completed_pending_human_review"
            or report.get("generation_attempts") != 3
            or [s.get("shot_id") for s in report.get("shots", [])] != IDS):
        raise ValueError("Incomplete or reordered generation report; never regenerate")
    clips, metadata = [], []
    for record in report["shots"]:
        path = source / (record["shot_id"] + ".mp4")
        if path.is_symlink() or not path.is_file() or sha(path) != record.get("video_sha256"):
            raise ValueError("Source clip hash mismatch or missing clip")
        info = probe(path)
        if abs(info["duration_seconds"] - float(record["duration_seconds"])) > .1:
            raise ValueError("Source duration disagrees with receipt")
        if metadata and info["stream_signature"] != metadata[0]["stream_signature"]:
            raise ValueError("Incompatible clips require separate explicit normalization")
        clips.append(path)
        metadata.append(info)
    # No output is touched until every source has passed validation.
    output.mkdir(parents=True, exist_ok=False)
    final = output / "gpt-three-shot-preview.mp4"
    with tempfile.TemporaryDirectory(prefix="gpt-concat-") as temp:
        folder = Path(temp)
        for i, clip in enumerate(clips):
            shutil.copyfile(clip, folder / f"clip{i}.mp4")
        (folder / "clips.txt").write_text("".join(f"file 'clip{i}.mp4'\n" for i in range(3)))
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", "-f", "concat", "-safe", "1",
            "-i", str(folder / "clips.txt"), "-map", "0:v:0", "-map", "0:a:0", "-c", "copy",
            "-movflags", "+faststart", str(final)], check=True, capture_output=True, timeout=120)
    joined = probe(final)
    expected = sum(m["duration_seconds"] for m in metadata)
    if abs(joined["duration_seconds"] - expected) > .25:
        raise ValueError("Assembly duration drift")
    subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-i", str(final),
        "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"],
        check=True, capture_output=True, timeout=120)
    result = {"status": "technical_preview_passed_pending_human_review",
        "source_run_id": report.get("run_id"), "source_report_sha256": sha(report_path),
        "source_response_sha256": report.get("source_response_sha256"),
        "source_provenance": "supplied_report_and_matching_bytes_not_authenticated_provider_proof",
        "shot_order": IDS, "source_shots": report["shots"],
        "duration_seconds": joined["duration_seconds"], "width": 360, "height": 640,
        "native_audio_preserved": True, "stream_copy": True, "full_decode_passed": True,
        "mp4_sha256": sha(final), "new_model_calls": 0, "new_api_cost_usd": "0",
        "actual_original_generation_fee_usd": None,
        "subtitle_alignment_verified": False, "dialogue_content_verified": False,
        "full_episode_complete": False, "publish_approved": False}
    (output / "delivery.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = assemble(args.source, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
