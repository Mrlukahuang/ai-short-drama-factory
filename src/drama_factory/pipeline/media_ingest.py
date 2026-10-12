"""Local media ingress adapter: normalize pre-existing MP4/MOV/WEBM clips.

This component NEVER downloads URLs or invokes video generation APIs.
It is a handoff point for later provider-fetched video bytes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

MAX_SOURCE_BYTES = 200 * 1024 * 1024
EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}


class MediaIngressError(ValueError):
    pass


def inspect_source(path: Path, shot_seconds: int) -> dict:
    try:
        source = Path(path).resolve(strict=True)
    except OSError as exc:
        raise MediaIngressError("Source video path does not exist") from exc
    if not source.is_file() or source.suffix.lower() not in EXTENSIONS:
        raise MediaIngressError("Only local MP4/MOV/WEBM/MKV video files are supported")
    if not (1000 <= source.stat().st_size <= MAX_SOURCE_BYTES):
        raise MediaIngressError("Source file outside size bounds (1 KB to 200 MB)")
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type", "-of", "json", str(source)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        probe = json.loads(result.stdout)
        duration = float(probe["format"]["duration"])
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, KeyError) as exc:
        raise MediaIngressError("Invalid or unreadable source video") from exc
    videos = [v for v in probe.get("streams", []) if v.get("codec_type") == "video"]
    audios = [v for v in probe.get("streams", []) if v.get("codec_type") == "audio"]
    if len(videos) != 1 or duration + 0.05 < shot_seconds:
        raise MediaIngressError("Source requires one video stream and enough footage duration")
    digest = hashlib.sha256()
    with source.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": source, "sha256": digest.hexdigest(),
            "duration": duration, "has_audio": bool(audios)}


def normalize_local_video(source: dict, duration: int, output: Path, *,
                          width: int = 360, height: int = 640, fps: int = 15) -> None:
    """Re-encode one approved shot into deterministic video/audio stream layout."""
    path = source["path"]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(path)]
    if not source["has_audio"]:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000"]
        audio_map = "1:a:0"
    else:
        audio_map = "0:a:0"
    cmd += [
        "-map", "0:v:0", "-map", audio_map,
        "-t", str(duration),
        "-vf", (
            f"fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
        ),
        "-c:v", "libx264", "-preset", "ultrafast", "-r", str(fps),
        "-c:a", "aac", "-ar", "48000", "-ac", "1",
    ]
    if source["has_audio"]:
        cmd += ["-af", "apad"]
    cmd += ["-movflags", "+faststart", str(output)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        message = getattr(exc, "stderr", "") or ""
        raise MediaIngressError(f"FFmpeg local media ingest failed: {message[-1000:]}") from exc
