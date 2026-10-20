"""G4/R4.4: one real, public-location establishing plate for CityDiscount s03.

This is *not* the completed s03 shot: it deliberately excludes the Owner
mascot, Logo, offers, and any user-supplied PNG to avoid premature media upload.
Uses the existing single-call Google Omni provider and MP4 validation; no
fallback to Fake. The human runs a workflow manually after fee review.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path

from drama_factory.providers.google_omni_video import (
    GoogleOmniVideoProvider, OmniVideoSpec, VideoCallDisabled,
)

MODEL = "gemini-omni-1.1-flash"
EXPECTED_TITLE = "把奥克兰的好折扣，挖到你身边"
RESERVED_RUN_USD = Decimal("2.00")
DAILY_USD = Decimal("5.00")
DEFAULT_PILOT = (Path(__file__).resolve().parents[1] /
                 "config/pilots/citydiscount_first_promo_v1.json")

def _amount(value: str) -> Decimal:
    try:
        d = Decimal(value)
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise VideoCallDisabled("Invalid NZ-day spend declaration") from exc
    if not d.is_finite() or d < 0:
        raise VideoCallDisabled("Invalid NZ-day spend declaration")
    return d

def prepare_s03_city_plate(
    pilot_path: Path, *, spent_today_usd: str,
    text_only: bool = True,
) -> tuple[OmniVideoSpec, dict]:
    """Deterministic production prompt, no API call and no reference files."""
    spent = _amount(spent_today_usd)
    if spent + RESERVED_RUN_USD > DAILY_USD:
        raise VideoCallDisabled("Insufficient USD 2 reserve within NZ-day USD 5")
    if text_only is not True:
        raise VideoCallDisabled("This route MUST NOT transmit any character images")
    source = Path(pilot_path).read_bytes()
    script = json.loads(source.decode("utf-8"))
    if (script.get("project") != "CityDiscount"
            or script.get("revision") != 3
            or script.get("storyline", {}).get("title_zh") != EXPECTED_TITLE
            or len(script.get("shots", [])) != 12
            or script["shots"][2].get("shot_id") != "s03"
            or script["shots"][2].get("shot_title_zh") != "奥克兰藏着宝"
            or script["shots"][2].get("duration_seconds") != 5
            or script["shots"][2].get("media_submission_approved") is not False
            or script.get("controls", {}).get("real_paid_call_authorized") is not False):
        raise VideoCallDisabled("Owner screenplay changed; reconfirm exact shot")
    # Owner's s03 plate (Auckland micro-city) WITHOUT inserting the mascot;
    # actual s03 still requires owner-approved character-reference integration.
    prompt = (
        "A SINGLE continuous 5-second vertical 9:16 establishing shot of a "
        "warm needle-felted miniature AUCKLAND city treasure map on a table. "
        "All objects visibly handcrafted from soft wool with fibers, seams "
        "and natural morning light. Auckland Sky Tower in the city center, "
        "the Auckland Harbour Bridge, a calm blue harbor, tiny white sailboats "
        "and hills in coherent geographical perspective. Camera starts close "
        "on the intricate textile map, then gently cranes backward and upward "
        "to reveal these landmarks as several small abstract golden light "
        "beacons blink between the neighborhoods; stop-motion animation "
        "feeling, smooth gentle motion, whimsical treasure-hunt wonder. "
        "NO people, NO mascot or lamb, NO brands, NO logos, NO written words, "
        "NO numbers, NO pricing, NO real discounts, NO legible commercial "
        "signs, NO split-screen, NO shot cuts. Do not present any discount "
        "as verified. Gentle original whimsical ambient soundtrack, NO "
        "voiceover: the Owner's exact Chinese narration is planned for "
        "separate deterministic postproduction."
    )
    spec = OmniVideoSpec(
        prompt=prompt, aspect_ratio="9:16", resolution="360p",
        min_duration_seconds=5,
        maximum_acknowledged_spend_usd=RESERVED_RUN_USD,
        operator_approved=True,
    )
    plan = {
        "schema": "g4-citydiscount-s03-city-plate.v1",
        "campaign_id": script["campaign_id"],
        "owner_screenplay_sha256": hashlib.sha256(source).hexdigest(),
        "owner_shot_id": "s03",
        "owner_shot_title": script["shots"][2]["shot_title_zh"],
        "source_shot_duration_seconds": 5,
        "purpose": "text_only_auckland_city_environment_plate",
        "NOT_full_owner_shot": True,
        "mascot_character_reference_applied": False,
        "source_pngs_transmitted": 0,
        "rights_restricted_images_transmitted": False,
        "model": MODEL, "resolution": "360p",
        "max_run_usd_declaration": str(RESERVED_RUN_USD),
        "nz_day_spend_before_run_declared_usd": str(spent),
        "google_provider_hard_spend_cap_exists": False,
        "price_estimate_is_not_invoice": True,
        "owner_approved_publication": False,
        "output_media": "not_generated",
        "model_calls": 0,
        "actual_fee_usd": None,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        # Prompt contains *no* personal assets. Safe for local receipt.
        "production_prompt": prompt,
        "narration_zh_postproduction": script["shots"][2]["voiceover_zh"],
    }
    return spec, plan

def run_s03(*, pilot_path: Path, output_dir: Path, spent_today_usd: str,
            paid: bool, confirmation: str, provider=None) -> dict:
    spec, plan = prepare_s03_city_plate(
        pilot_path, spent_today_usd=spent_today_usd,
    )
    output = Path(output_dir)
    if output.exists():
        raise VideoCallDisabled("One-shot destination exists; no reruns or overwrites")
    if paid:
        if confirmation != "GENERATE_ONE_S03_PAID_PLATE":
            raise VideoCallDisabled("Owner action must explicitly confirm one paid shot")
        if os.getenv("DRAMA_ENABLE_PAID_GENERATION") != "YES":
            raise VideoCallDisabled("Google paid mode disabled")
    output.mkdir(parents=True, exist_ok=False)
    # Preflight writes no provider video/secret or private assets.
    plan_path = output / "receipt.json"
    if not paid:
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return plan
    try:
        real_provider = provider or GoogleOmniVideoProvider()
        result = real_provider.generate(spec, output / "s03_city_plate.mp4")
        if (result.get("is_mock") is not False
                or result.get("model_calls") != 1
                or not result.get("media_path")
                or not (output / "s03_city_plate.mp4").is_file()):
            raise VideoCallDisabled("Real s03 clip absent; reject fake/empty receipt")
        plan.update({
            "output_media": "real_model_video_downloaded",
            "model_calls": 1,
            "provider_video_sha256": result["source_sha256"],
            "reported_duration_seconds": result["source_duration_seconds"],
            "provider_task_id": result.get("provider_task_id"),
            "actual_fee_usd": None,
            "provider_billing_unverified": True,
            "owner_approved_publication": False,
        })
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return plan
    except Exception:
        # Never silently invoke a second generation after a failed request.
        raise

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CityDiscount s03 PUBLIC Auckland establishing-plate only")
    parser.add_argument("--pilot", type=Path, default=DEFAULT_PILOT)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--nz-spend-today-usd", type=str, required=True)
    parser.add_argument("--paid", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args(argv)
    try:
        result = run_s03(
            pilot_path=args.pilot, output_dir=args.out,
            spent_today_usd=args.nz_spend_today_usd,
            paid=args.paid, confirmation=args.confirmation,
        )
    except (VideoCallDisabled, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, "BLOCKED: " + exc.__class__.__name__ + "\n")
    print(json.dumps({
        k: result[k] for k in (
            "owner_shot_id", "purpose", "output_media", "model_calls",
            "actual_fee_usd", "owner_approved_publication",
        )
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
