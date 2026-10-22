#!/usr/bin/env python3
"""G4/R4.4: rev4 12x5s INTERNAL technical review cut using existing media only.

NOT a new-video generator, content pass, approved soundtrack, or publishable film.
Only s02/s05 are existing AI character performances; s03 is an OLD city-only plate.
Everything else is an explicit still placeholder (s12 uses the true official logo).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render_citydiscount_3x4_priority_boards as boards

SOURCE_IDS = {
    "s02": (39583047905, 12339030552),
    "s03": (39441034483, 12274786001),
    "s05": (39596195021, 12343403535),
}
OLD_S03_SHA = "b718e6b0a6e5a64db66d74e6b1364326d16671823fca12935e8a3667b101af3f"
LIVE_SOURCE_SHOTS = {"s02", "s05"}
ENVIRONMENT_ONLY = {"s03"}
STILL_BOARDS = {"s06": "cafe_arrival", "s07": "dig_1", "s12": "official_logo"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def regular(path: Path, suffix: str) -> Path:
    path = Path(path).absolute()
    if path.suffix != suffix or not path.is_file() or any(
        part.is_symlink() for part in (path, *path.parents)
    ):
        raise ValueError("Missing, linked or unexpected local source")
    return path


def assert_story(story: dict) -> None:
    f = story["format"]
    shots = story["shots"]
    assert story["revision"] == 4 and story["project"] == "CityDiscount"
    assert (f["width"], f["height"], f["aspect_ratio"]) == (1080, 1440, "3:4")
    assert len(shots) == 12 and [x["shot_id"] for x in shots] == [
        f"s{i:02d}" for i in range(1, 13)
    ]
    assert all(
        (x["start_ms"], x["end_ms"], x["duration_seconds"])
        == (i * 5000, (i + 1) * 5000, 5)
        for i, x in enumerate(shots)
    )
    assert story["controls"]["publish_approved"] is False
    assert story["controls"]["real_paid_call_authorized"] is False
    assert story["shots"][-1]["logo_hold_seconds"] >= 3


def check_live_source(shot_id: str, media: Path, receipt: Path) -> dict:
    media = regular(media, ".mp4")
    receipt = regular(receipt, ".json")
    if receipt.stat().st_size > 64 * 1024:
        raise ValueError("Unbounded source receipt")
    record = json.loads(receipt.read_text("utf-8"))
    field = "source_video_sha256" if shot_id == "s02" else "source_mp4_sha256"
    actual = digest(media)
    if (record.get("shot_id") != shot_id
            or record.get("model_calls") != 1
            or record.get("output_media") != "real_omni_video_downloaded"
            or record.get("source_video_real_model") is not True
            or record.get("publication_approved") is not False
            or record.get("actual_fee_usd", "unset") is not None
            or record.get(field) != actual):
        raise ValueError("Historical single-shot media/receipt mismatch")
    run, artifact = SOURCE_IDS[shot_id]
    return {"shot_id": shot_id, "kind": "existing_real_omni_raw_media",
            "source_run": run, "source_artifact_id": artifact,
            "raw_mp4_sha256": actual,
            "source_receipt_sha256": digest(receipt),
            "provider_invoice_verified": False, "creative_review_approved": False}


def check_city_source(media: Path) -> dict:
    media = regular(media, ".mp4")
    if digest(media) != OLD_S03_SHA:
        raise ValueError("Historic s03 city plate SHA mismatch")
    run, artifact = SOURCE_IDS["s03"]
    return {"shot_id": "s03", "kind": "old_real_omni_city_background_only",
            "source_run": run, "source_artifact_id": artifact,
            "raw_mp4_sha256": OLD_S03_SHA, "rev4_shot_fulfilled": False,
            "no_moving_rev4_mascot_confirmed": True}


def placeholder(shot: dict, out: Path, roles: dict, logo: Image.Image) -> dict:
    sid = shot["shot_id"]
    if sid in STILL_BOARDS:
        im, _ = boards.render_board(sid, STILL_BOARDS[sid], roles, logo, boards.source())
        im = im.convert("RGB")
        variant = "existing_original_asset_static_board"
    else:
        # Honest slate instead of imitating a previously ungenerated model shot.
        palettes = ["#e9ebdb", "#cfe4df", "#ece0cd", "#dce5d6"]
        im = Image.new("RGB", (1080, 1440), palettes[int(sid[1:]) % 4])
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((64, 200, 1016, 1160), radius=55, fill="#285448")
        d.text((540, 365), sid.upper(), anchor="mm",
               font=boards.font_family(90, bold=True), fill="#fff6df")
        d.text((540, 565), shot["shot_title_zh"], anchor="mm",
               font=boards.font_family(48, bold=True), fill="#fff6df")
        d.text((540, 780), "占位镜头 / 尚无真实 AI 视频", anchor="mm",
               font=boards.font_family(33), fill="#f1dfbf")
        variant = "explicit_missing_real_shot_slate"
    im.save(out)
    return {"shot_id": sid, "kind": variant, "still_sha256": digest(out),
            "rev4_shot_fulfilled": False, "release_blocked": True}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def segment(source: Path, out: Path, *, still: bool) -> None:
    base = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    if still:
        base += ["-loop", "1", "-framerate", "24"]
    base += ["-i", str(source), "-t", "5.000", "-an"]
    if not still:
        base += ["-vf", ("scale=1080:1440:force_original_aspect_ratio=decrease,"
                          "pad=1080:1440:(ow-iw)/2:(oh-ih)/2:black,"
                          "fps=24,format=yuv420p")]
    base += ["-r", "24", "-c:v", "libx264", "-preset", "ultrafast",
             "-crf", "29", "-pix_fmt", "yuv420p", str(out)]
    run(base)


def make_cut(*, s02: Path, s02_receipt: Path, s03: Path,
             s05: Path, s05_receipt: Path, out: Path) -> dict:
    if out.exists():
        raise FileExistsError("Use a fresh output directory")
    story = boards.source()
    assert_story(story)
    verified = {
        "s02": check_live_source("s02", s02, s02_receipt),
        "s03": check_city_source(s03),
        "s05": check_live_source("s05", s05, s05_receipt),
    }
    roles, logo, logo_sha = boards.owned_assets()
    if logo_sha != story["brand_asset_requirements"]["logo"]["source_sha256"]:
        raise ValueError("Canonical brand logo differs from approved source SHA")
    out.mkdir(parents=True, exist_ok=False)
    (out / "segments").mkdir()
    rows, parts = [], []
    for shot in story["shots"]:
        sid = shot["shot_id"]
        target = out / "segments" / (sid + ".mp4")
        if sid in verified:
            segment({"s02": s02, "s03": s03, "s05": s05}[sid], target, still=False)
            row = verified[sid]
        else:
            frame = out / "segments" / (sid + ".png")
            row = placeholder(shot, frame, roles, logo)
            segment(frame, target, still=True)
            frame.unlink()  # keep only the small technical output and receipt
        row = {**row, "segment_sha256": digest(target)}
        rows.append(row)
        parts.append("file '" + target.name + "'")
    concat = out / "segments" / "concat.txt"
    concat.write_text("\n".join(parts) + "\n", encoding="utf-8")
    mp4 = out / "CityDiscount_rev4_60s_3x4_TECHNICAL_NOT_FINAL.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
         "-f", "concat", "-safe", "0", "-i", str(concat),
         "-f", "lavfi", "-t", "60", "-i", "anullsrc=r=48000:cl=stereo",
         "-map", "0:v:0", "-map", "1:a:0", "-t", "60",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
         "-movflags", "+faststart", str(mp4)])
    probed = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(mp4)], text=True))
    streams = probed["streams"]
    if (not any(x.get("codec_type") == "video" and x.get("codec_name") == "h264"
                and (x.get("width"), x.get("height")) == (1080, 1440) for x in streams)
            or not any(x.get("codec_type") == "audio" and x.get("codec_name") == "aac"
                       for x in streams)
            or not 59.9 <= float(probed["format"]["duration"]) <= 60.2):
        raise ValueError("Technical FFmpeg output out of 60s / 1080x1440 bounds")
    result = {
        "schema": "g4-cd-rev4-technical-review-cut.v1",
        "story_sha256": digest(boards.PILOT),
        "video_sha256": digest(mp4),
        "format": {"width": 1080, "height": 1440, "aspect": "3:4",
                   "duration_seconds": probed["format"]["duration"]},
        "existing_real_rev4_character_motion_shots": ["s02", "s05"],
        "old_environment_reference_only": ["s03"],
        "missing_real_rev4_shots": [f"s{i:02}" for i in range(1, 13)
                                   if f"s{i:02}" not in LIVE_SOURCE_SHOTS],
        "audio": "silent AAC TECHNICAL placeholder (no approved music, SFX or voice)",
        "source_provenance": rows, "new_provider_calls": 0,
        "historical_google_invoice_usd": None,
        "human_content_review": "not_run",
        "all_real_12_shot_episode": False,
        "release_status": "blocked", "publish_approved": False,
        "g4_exited": False, "g5_authorized": False,
    }
    (out / "receipt.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("s02", "s02-receipt", "s03", "s05", "s05-receipt", "out"):
        p.add_argument("--" + name, type=Path, required=True)
    args = vars(p.parse_args(argv))
    result = make_cut(**{k.replace("-", "_"): v for k, v in args.items()})
    print(json.dumps({k: result[k] for k in (
        "video_sha256", "existing_real_rev4_character_motion_shots",
        "missing_real_rev4_shots", "publish_approved")}, sort_keys=True))


if __name__ == "__main__":
    main()
