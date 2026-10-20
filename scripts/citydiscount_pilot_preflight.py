"""CityDiscount first film: run the REPOSITORY'S offline creative plan and asset gates.

This 11-stage preflight deliberately stops BEFORE paid video generation.
Any local static animatic is a separate preview and must not be reported as
provider-created footage. Original user PNGs must be present with exact SHA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from drama_factory.pipeline.promo_motion_graphics import (
    build_offline_citydiscount_promo_plan,
)

STAGES = (
    "00_input", "01_story_bible", "02_episode_script", "03_screenplay",
    "04_assets", "05_shots", "06_dialogue", "07_subtitles", "08_music",
    "09_render", "10_qa",
)


class CityDiscountPilotGateError(ValueError):
    pass


def _load(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 200_000:
        raise CityDiscountPilotGateError("Missing or unsafe pilot manifest")
    value = json.loads(path.read_text("utf-8"))
    if type(value) is not dict:
        raise CityDiscountPilotGateError("Pilot input must be an object")
    return value


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as data:
        for chunk in iter(lambda: data.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_owner_assets(campaign: dict, asset_manifest: dict,
                         asset_dir: Path) -> list[dict]:
    if (asset_manifest.get("schema") != "g4-citydiscount-owner-supplied-assets.v1"
            or asset_manifest.get("remote_model_use_granted") is not False
            or asset_manifest.get("github_original_binary_upload_status") != "NOT_VERIFIED_NOT_COMMITTED"
            or type(asset_manifest.get("assets")) is not list
            or len(asset_manifest["assets"]) != 2
            or not isinstance(asset_dir, Path)):
        raise CityDiscountPilotGateError("Unknown or falsely approved asset manifest")
    style = campaign["style"]
    expected = {
        "citydiscount-mascot-v1": style["mascot_source_sha256"],
        "citydiscount-logo-v1": style["logo_source_sha256"],
    }
    if set(a.get("asset_id") for a in asset_manifest["assets"]) != set(expected):
        raise CityDiscountPilotGateError("Mascot/logo asset identity mismatch")
    validated = []
    for row in asset_manifest["assets"]:
        aid = row["asset_id"]
        if row.get("sha256") != expected[aid]:
            raise CityDiscountPilotGateError("Campaign uses different asset version")
        filename = Path(row.get("repo_target", "")).name
        if filename not in ("mascot_character_sheet.png", "citydiscount_logo.png"):
            raise CityDiscountPilotGateError("Unknown canonical original asset name")
        local = asset_dir / filename
        if (asset_dir.is_symlink() or local.is_symlink() or not local.is_file()
                or local.stat().st_size != row["size_bytes"]
                or _hash(local) != row["sha256"]):
            raise CityDiscountPilotGateError("Required original source PNG is unavailable or mutated")
        validated.append({
            "asset_id": aid, "sha256": row["sha256"], "source_bytes": row["size_bytes"],
            "source_binary_verified_locally": True, "remote_model_use_approved": False,
        })
    return validated


def preflight(campaign: dict, assets: dict, assets_dir: Path) -> dict:
    plan = build_offline_citydiscount_promo_plan(campaign)
    if (campaign["style"]["id"] != "citydiscount_needle_felt_mascot_v1"
            or campaign["style"].get("owner_confirmed_felt_style") is not True
            or plan["model_submission_allowed"] is not False
            or plan["shot_count"] != 12):
        raise CityDiscountPilotGateError("First-pilot felt visual direction mismatch")
    for shot in campaign["shots"]:
        if (shot.get("character_id") != "citydiscount-mascot-v1"
                or shot.get("character_reference_sha256") != campaign["style"]["mascot_source_sha256"]
                or shot.get("brand_logo_reference_sha256") != campaign["style"]["logo_source_sha256"]):
            raise CityDiscountPilotGateError("Shot differs from pinned canonical mascot or logo")
    verified = inspect_owner_assets(campaign, assets, assets_dir)
    return {
        "schema": "g4-citydiscount-production-preflight.v1",
        "source_sha256": plan["source_sha256"],
        "visual_plan_sha256": plan["offline_plan_sha256"],
        "shot_count": 12, "seconds": 60, "assets": verified,
        "real_paid_provider_calls": 0,
        "actual_cost_usd": None,
        "video_provider_receipt": None,
        "real_model_generated_shots": 0,
        "model_submission_allowed": False,
        "external_media_transfer_approved": False,
        "publish_approved": False,
    }


def run(campaign: dict, assets: dict, assets_dir: Path, out: Path) -> dict:
    """Write 11 stage documents with accurate NOT_RUN media/QA statuses."""
    if out.is_symlink() or out.exists():
        raise CityDiscountPilotGateError("Output directory must be new and not linked")
    report = preflight(campaign, assets, assets_dir)
    plan = build_offline_citydiscount_promo_plan(campaign)
    out.mkdir(parents=True)
    chapters = [
        {"creative_goal": "CityDiscount NZ local info brand promo, needle-felt sheep"},
        {"bible_draft": "Same sheep mascot and official flower-CD logo for every shot",
         "approved": False},
        {"narration_draft": [s["audio_narration_expected"] for s in plan["shots"]]},
        {"shots": plan["shots"], "plan_sha256": plan["offline_plan_sha256"]},
        {"references": report["assets"], "operator_approved_for_remote_model": False},
        {"shot_requests": [{"shot_id": s["shot_id"], "status": "no_real_provider_submission"}
                           for s in plan["shots"]]},
        {"voice": "draft_only", "real_speech": False},
        {"srt": "not_rendered_by_this_preflight", "requires_asr": True},
        {"music": "not_run"},
        {"video": "not_run", "video_provider_call_count": 0},
        {"real_ai_content_qa": "not_run", "publish_approved": False},
    ]
    for step, data in zip(STAGES, chapters, strict=True):
        stage_dir = out / step
        stage_dir.mkdir()
        (stage_dir / "receipt.json").write_text(
            json.dumps({"schema": "g4-stage-receipt.v1",
                        "step": step, "fake_or_offline": True,
                        "paid_model_calls": 0, "payload": data},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (out / "preflight.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return report


def main(argv: list[str] | None = None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--campaign", type=Path, required=True)
    cli.add_argument("--asset-manifest", type=Path, required=True)
    cli.add_argument("--assets-dir", type=Path, required=True)
    cli.add_argument("--out-dir", type=Path, required=True)
    args = cli.parse_args(argv)
    try:
        report = run(
            _load(args.campaign), _load(args.asset_manifest),
            args.assets_dir, args.out_dir,
        )
    except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError):
        cli.exit(2, "CityDiscount pipeline preflight BLOCKED: asset, content or permission gate\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
