#!/usr/bin/env python3
"""Owner-approved felt-diorama style test: 3 real Gemini Omni shots -> one MP4.

Issue #132. Real generation only with --paid AND DRAMA_ENABLE_PAID_GENERATION=YES
(enforced by GoogleOmniVideoProvider). Budget: estimated <= 2 USD per shot and
<= 3 USD total; the run stops before any shot that would exceed the total.

Omni's adapter is prompt-only (no reference images), so character consistency
is tested through fixed text descriptions from the style preset.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESET_PATH = ROOT / "config" / "style_presets" / "felt_diorama.json"

# Public list-price estimate for 360p (~1/3 of 720p's ~0.10 USD/s). Not a bill.
EST_USD_PER_SECOND_360P = Decimal("0.035")
ASSUMED_MAX_SECONDS_PER_SHOT = 10
PER_SHOT_LIMIT_USD = Decimal("2.00")
TOTAL_LIMIT_USD = Decimal("3.00")

SHOTS = [
    {
        "id": "s1_street",
        "seconds": 6,
        "action": "Wide establishing shot. Slow push-in down the felt street toward a "
                  "corner coffee shop with a green awning. A-Jie walks along the "
                  "pavement carrying a small felt coffee cup.",
        "dialogue": None,
    },
    {
        "id": "s2_meet",
        "seconds": 8,
        "action": "Medium two-shot in front of the coffee shop. Xiao-Yu steps out of "
                  "the door and bumps gently into A-Jie; both stop and look at each "
                  "other, a little embarrassed. Warm window light behind them.",
        "dialogue": "Xiao-Yu says softly in Mandarin Chinese: “对不起，我没看路。” "
                    "A-Jie replies in Mandarin Chinese: “没关系，咖啡还在。”",
    },
    {
        "id": "s3_smile",
        "seconds": 6,
        "action": "Close-up on Xiao-Yu, slight slow orbit. She smiles and tucks her "
                  "red scarf; the Sky Tower glows softly out of focus behind her.",
        "dialogue": "Xiao-Yu says in Mandarin Chinese: “那……明天还在这里见？”",
    },
]


def load_preset(path: Path = PRESET_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_prompt(preset: dict, shot: dict) -> str:
    chars = preset["characters"]
    parts = [
        f"One continuous shot, about {shot['seconds']} seconds, vertical 9:16 portrait.",
        preset["style_prompt"],
        preset["setting"],
        f"Male lead: {chars['male_lead']}",
        f"Female lead: {chars['female_lead']}",
        preset["consistency_rule"],
        f"Action: {shot['action']}",
        f"Dialogue: {shot['dialogue']}" if shot["dialogue"] else
        "No dialogue; soft ambient street sound and gentle music only.",
    ]
    return "\n".join(parts)


def estimate_shot_usd() -> Decimal:
    return EST_USD_PER_SECOND_360P * ASSUMED_MAX_SECONDS_PER_SHOT


def plan_budget(n_shots: int) -> dict:
    per = estimate_shot_usd()
    total = per * n_shots
    if per > PER_SHOT_LIMIT_USD:
        raise RuntimeError(f"Per-shot estimate {per} exceeds {PER_SHOT_LIMIT_USD}")
    if total > TOTAL_LIMIT_USD:
        raise RuntimeError(f"Total estimate {total} exceeds {TOTAL_LIMIT_USD}")
    return {"per_shot_estimate_usd": str(per), "total_estimate_usd": str(total)}


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    return {
        "width": int(video["width"]), "height": int(video["height"]),
        "duration": float(data["format"]["duration"]),
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
    }


def is_portrait(info: dict) -> bool:
    return info["width"] < info["height"]


def normalize(src: Path, dst: Path, has_audio: bool) -> None:
    """Re-encode to 360x640 H.264/AAC so clips concat cleanly; add silence if needed."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src)]
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest"]
    cmd += ["-vf", "scale=360:640:force_original_aspect_ratio=decrease,"
                   "pad=360:640:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000",
            "-ac", "2", str(dst)]
    subprocess.run(cmd, check=True)


def concat(clips: list[Path], dst: Path) -> None:
    lst = dst.with_suffix(".txt")
    lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", str(dst)], check=True)


def run(out: Path, provider, *, max_retries_on_landscape: int = 1) -> dict:
    from drama_factory.providers.google_omni_video import OmniVideoSpec

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    preset = load_preset()
    budget = plan_budget(len(SHOTS))
    spent_est = Decimal("0")
    results, normalized = [], []
    for shot in SHOTS:
        prompt = build_prompt(preset, shot)
        attempt = 0
        while True:
            if spent_est + estimate_shot_usd() > TOTAL_LIMIT_USD:
                raise RuntimeError("Stopping: next call would exceed total budget")
            raw = out / f"{shot['id']}_try{attempt}.mp4"
            spec = OmniVideoSpec(
                prompt=prompt, resolution="360p", min_duration_seconds=3,
                maximum_acknowledged_spend_usd=PER_SHOT_LIMIT_USD,
                operator_approved=True,
            )
            receipt = provider.generate(spec, raw)
            spent_est += estimate_shot_usd()
            info = probe(raw)
            ok = is_portrait(info)
            results.append({
                "shot": shot["id"], "attempt": attempt, "file": raw.name,
                "provider_task_id": receipt.get("provider_task_id"),
                "width": info["width"], "height": info["height"],
                "duration": round(info["duration"], 2), "has_audio": info["has_audio"],
                "portrait_check": "PASS" if ok else "FAIL",
                "est_usd": str(EST_USD_PER_SECOND_360P * Decimal(str(round(info["duration"], 2)))),
            })
            if ok or attempt >= max_retries_on_landscape:
                break
            attempt += 1
        if ok:
            norm = out / f"{shot['id']}_norm.mp4"
            normalize(raw, norm, info["has_audio"])
            normalized.append(norm)
    final = out / "felt_style_3shot.mp4"
    if normalized:
        concat(normalized, final)
    manifest = {
        "issue": 132, "model": "gemini-omni-1.1-flash", "style": preset["id"],
        "budget_plan": budget, "estimated_spend_usd": str(spent_est),
        "billing_note": "Estimates from public list price; check Google AI Studio billing for actual charge.",
        "reference_images_used": False,
        "shots": results,
        "final_mp4": final.name if normalized else None,
        "all_portrait": all(r["portrait_check"] == "PASS" for r in results
                            if r["attempt"] == max(x["attempt"] for x in results
                                                   if x["shot"] == r["shot"])),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--paid", action="store_true", help="Make real, billable Omni calls")
    p.add_argument("--out", type=Path, default=Path("artifacts/felt-style-test"))
    p.add_argument("--print-prompts", action="store_true")
    args = p.parse_args(argv)
    if args.print_prompts or not args.paid:
        preset = load_preset()
        print(json.dumps({"budget": plan_budget(len(SHOTS)),
                          "prompts": {s["id"]: build_prompt(preset, s) for s in SHOTS}},
                         ensure_ascii=False, indent=2))
        if not args.paid:
            return
    from drama_factory.providers.google_omni_video import GoogleOmniVideoProvider
    manifest = run(args.out, GoogleOmniVideoProvider())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
