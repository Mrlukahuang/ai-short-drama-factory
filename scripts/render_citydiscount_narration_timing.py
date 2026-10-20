"""Offline robot Mandarin scratch narration for Owner's CityDiscount first-film animatic.

Temporary timing ONLY: mechanical eSpeak voice is NOT production-ready Chinese
narration. No model APIs, media upload, provider charging, or final approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def cmd(args: list[str]) -> str:
    return subprocess.run(
        args, check=True, capture_output=True, text=True
    ).stdout


def verified_owner_script(pilot: Path) -> dict:
    obj = json.loads(pilot.read_text("utf-8"))
    if (obj.get("schema_version") != "g4-citydiscount-first-promo.v1"
            or obj.get("project") != "CityDiscount"
            or obj.get("revision") != 3
            or len(obj.get("shots", [])) != 12
            or obj.get("format", {}).get("total_duration_seconds") != 60
            or [s.get("shot_id") for s in obj["shots"]]
               != [f"s{i:02d}" for i in range(1, 13)]
            or any(s.get("duration_seconds") != 5
                   or type(s.get("voiceover_zh")) is not str
                   or not s["voiceover_zh"].strip()
                   for s in obj["shots"])):
        raise ValueError("Owner's fixed 12-shot CityDiscount script mismatch")
    return obj


def render(
    *, pilot: Path, animatic: Path, out: Path,
    expected_animatic_sha256: str | None = None
) -> dict:
    if out.exists():
        raise FileExistsError("Review output exists; do not overwrite prior cut")
    for binary in ("ffmpeg", "ffprobe", "espeak"):
        if not shutil.which(binary):
            raise RuntimeError("Required offline binary missing: " + binary)
    if not animatic.is_file():
        raise FileNotFoundError(animatic)
    animatic_sha = digest(animatic)
    if (expected_animatic_sha256 is not None
            and animatic_sha != expected_animatic_sha256):
        raise ValueError("Pinned earlier Owner review MP4 SHA256 mismatch")
    obj = verified_owner_script(pilot)
    probe = json.loads(cmd([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type", "-of", "json", str(animatic),
    ]))
    if not 59.7 <= float(probe["format"]["duration"]) <= 60.3:
        raise ValueError("Input 60 second animatic contract broken")
    if not any(s.get("codec_type") == "audio" for s in probe["streams"]):
        raise ValueError("Source background track missing")
    out.mkdir(parents=True)
    clips = []
    for i, shot in enumerate(obj["shots"], 1):
        p = out / f"vo_{i:02d}.wav"
        # Shell-free invocation; exact Chinese text is from version-pinned Owner source.
        cmd(["espeak", "-v", "zh", "-s", "195", "-a", "155",
             "-w", str(p), shot["voiceover_zh"]])
        with wave.open(str(p), "rb") as wf:
            duration = wf.getnframes() / wf.getframerate()
        if not 0.1 <= duration <= 22:
            raise ValueError("Empty or invalid robotic narration audio")
        clips.append((p, duration))
    graph = [
        "[0:a]atrim=duration=60,asetpts=PTS-STARTPTS,volume=0.16[bed]"
    ]
    labels = ["[bed]"]
    timecodes = []
    for idx, (p, duration) in enumerate(clips):
        ratio = max(1.0, duration / 4.5)
        factors = []
        while ratio > 2:
            factors.append(2.0)
            ratio /= 2.0
        factors.append(ratio)
        speed = "".join(f",atempo={x:.5f}" for x in factors)
        offset = idx * 5000 + 200
        graph.append(
            f"[{idx+1}:a]aresample=48000,volume=1.50{speed},"
            "afade=t=in:st=0:d=0.09,apad=pad_dur=5,"
            f"atrim=duration=4.65,adelay={offset}:all=1[v{idx}]"
        )
        labels.append(f"[v{idx}]")
        timecodes.append({
            "shot_id": f"s{idx+1:02d}",
            "start_seconds": idx * 5 + .2,
            "original_speech_seconds": round(duration, 3),
            "line_zh": obj["shots"][idx]["voiceover_zh"],
        })
    graph.append(
        "".join(labels) +
        "amix=inputs=13:duration=first:normalize=0,"
        "alimiter=limit=0.9,aresample=48000[a]"
    )
    mp4 = out / "CityDiscount_60s_CHINESE_VO_TIMING_PREVIS_NOT_FINAL.mp4"
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(animatic)]
    for p, _ in clips:
        args += ["-i", str(p)]
    cmd(args + [
        "-filter_complex", ";".join(graph),
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-t", "60", "-movflags", "+faststart", str(mp4)
    ])
    verified = json.loads(cmd([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=codec_name,codec_type,channels,width,height",
        "-of", "json", str(mp4),
    ]))
    if (not 59.7 <= float(verified["format"]["duration"]) <= 60.3
            or not any(s.get("codec_type") == "audio"
                       for s in verified["streams"])
            or not any(s.get("codec_type") == "video"
                       for s in verified["streams"])):
        raise RuntimeError("Audible video technical QA rejected")
    receipt = {
        "schema": "g4-citydiscount-vo-scratch-review.v1",
        "owner_script_sha256": digest(pilot),
        "source_animatic_sha256": animatic_sha,
        "narration_mode": "local eSpeak Chinese robotic scratch, NOT finished VO",
        "timed_lines": timecodes,
        "real_ai_scene_video": ["s03 Auckland environment only"],
        "natural_voice_confirmed": False,
        "professional_voice_recording": False,
        "new_paid_calls": 0,
        "prior_google_fee_usd": None,
        "publish_approved": False,
        "g4_exit_approved": False,
        "mp4_name": mp4.name,
        "mp4_sha256": digest(mp4),
        "media_technical_check": verified,
    }
    (out / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), "utf-8"
    )
    for clip, _ in clips:
        clip.unlink()
    return receipt


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Owner's CityDiscount 60s Mandarin scratch rhythm, offline ONLY"
    )
    p.add_argument("--pilot", type=Path, required=True)
    p.add_argument("--animatic", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--expected-animatic-sha", default=None)
    a = p.parse_args(argv)
    report = render(
        pilot=a.pilot, animatic=a.animatic, out=a.out,
        expected_animatic_sha256=a.expected_animatic_sha,
    )
    print(json.dumps({
        "narration_lines": len(report["timed_lines"]),
        "mp4": report["mp4_name"],
        "duration_seconds": report["media_technical_check"]["format"]["duration"],
        "new_paid_calls": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
