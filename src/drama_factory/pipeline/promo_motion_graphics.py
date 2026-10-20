"""G4 CityDiscount: isolate a brand-motion promo from the drama-only cast schema.

An offline creative planning adapter, NOT a real provider or media renderer.
No fabricated 'actor' to satisfy the original W2 drama schema; background
video and deterministic postproduction graphic/text tracks are separate.
"""
from __future__ import annotations

import hashlib
import json
import re

SCHEMA = "g4-citydiscount-first-promo.v1"
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_PRICE = re.compile(r"(?:NZ\$|\$|\bNZD\s*)\s*\d+(?:\.\d+)?", re.I)
_UNCLEARED_BRANDS = ("kfc", "woolworths", "apple", "iphone", "samsung")
_FALSE_PRODUCTS = ("扫码领券", "CityDiscount App", "官方独家优惠", "保底省钱")


class PromoPlanError(ValueError):
    pass


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def build_offline_citydiscount_promo_plan(candidate: dict) -> dict:
    """Validate the approved-direction creative scope, never authorize a model.

    Brand and media rights approval remains outside this creative contract.
    A truthful offline storyboard is not equivalent to a rendered video.
    """
    if (type(candidate) is not dict
            or candidate.get("schema_version") != SCHEMA
            or candidate.get("project") != "CityDiscount"
            or candidate.get("stage") != "G4"
            or candidate.get("req") != "R4.4"
            or candidate.get("purpose") != "first_real_video_target_brand_promo"
            or candidate.get("status") != "creative_proposal_offline_only"):
        raise PromoPlanError("Invalid pilot source or campaign scope")
    fmt = candidate.get("format")
    shots = candidate.get("shots")
    style = candidate.get("style")
    ctl = candidate.get("controls")
    if (type(fmt) is not dict or fmt.get("aspect_ratio") != "9:16"
            or fmt.get("total_duration_seconds") != 60
            or fmt.get("shot_count") != 12 or type(shots) is not list
            or len(shots) != 12 or type(style) is not dict
            or style.get("style_asset_approved") is not False
            or type(ctl) is not dict or ctl.get("model_calls") != 0
            or ctl.get("real_paid_call_authorized") is not False
            or ctl.get("media_rights_and_remote_upload") != "not_approved"
            or ctl.get("publish_approved") is not False
            or ctl.get("g4_exit_approved") is not False):
        raise PromoPlanError("Promo media authorization and shot format inconsistent")
    storyline = candidate.get("storyline")
    if (type(storyline) is not dict
            or type(storyline.get("title_zh")) is not str
            or not storyline["title_zh"].strip()
            or type(storyline.get("logline_zh")) is not str
            or not storyline["logline_zh"].strip()
            or type(storyline.get("dramatic_spine")) is not list
            or len(storyline["dramatic_spine"]) != 4
            or storyline.get("script_reviewed_by_owner") is not False
            or storyline.get("brand_use_approved_for_render") is not False):
        raise PromoPlanError("Missing or prematurely approved story arc")
    ordered = []
    seen = set()
    for i, shot in enumerate(shots):
        sid = f"s{i+1:02d}"
        if (type(shot) is not dict or shot.get("shot_id") != sid
                or shot.get("start_ms") != i * 5000
                or shot.get("end_ms") != (i+1) * 5000
                or shot.get("duration_seconds") != 5
                or shot.get("media_submission_approved") is not False
                or shot.get("real_model_result") != "not_run"
                or shot.get("human_visual_review") != "not_run"):
            raise PromoPlanError("Wrong shot identity, duration or review state")
        deps = shot.get("shot_dependencies")
        if (type(deps) is not list or len(set(deps)) != len(deps)
                or any(d not in seen for d in deps)):
            raise PromoPlanError("Unsafe or future shot dependency")
        fields = [shot.get(x) for x in (
            "background_prompt_zh", "voiceover_zh", "on_screen_text_zh",
        )]
        if (any(type(x) is not str or not 1 <= len(x.strip()) <= 250 for x in fields)
                or any(_PRICE.search(x) for x in fields)
                or any(b.lower() in " ".join(fields).lower()
                       for b in _UNCLEARED_BRANDS + _FALSE_PRODUCTS)):
            raise PromoPlanError("Unchecked price, brand mark or marketing claim")
        if (type(shot.get("asset_roles")) is not list
                or "approved_citydiscount_brand_identity" not in shot["asset_roles"]):
            raise PromoPlanError("Brand reference cannot be replaced by text alone")
        view = shot.get("mascot_camera_view")
        action = shot.get("mascot_expression_or_action_hint")
        camera = shot.get("camera_direction_zh")
        continuity = shot.get("continuity_instruction_zh")
        valid_views = {"front", "side", "back", "three_quarter"}
        valid_actions = valid_views | {
            "happy", "wink", "sparkle", "jump", "thumbsup", "coin"
        }
        if (view not in valid_views or action not in valid_actions
                or type(camera) is not str or not camera.strip()
                or type(continuity) is not str or not continuity.strip()
                or shot.get("storybeat") != (
                    {0: "hook", 3: "reversal", 10: "resolution",
                     11: "cta"}.get(i, shot.get("storybeat"))
                )):
            raise PromoPlanError("Incomplete visual continuity or dramatic turn")
        # Explicitly keep source-image prompt and guaranteed later text overlay apart:
        # generated video model has no need to render logotypes or Chinese text.
        ordered.append({
            "shot_id": sid, "start_ms": shot["start_ms"],
            "end_ms": shot["end_ms"],
            "scene_anchor": shot["scene_anchor"],
            "storybeat": shot["storybeat"],
            "mascot_camera_view": view,
            "mascot_expression_or_action_hint": action,
            "camera_direction_zh": camera,
            "continuity_instruction_zh": continuity,
            "depends_on": deps,
            "video_background_prompt": shot["background_prompt_zh"],
            "postproduction_overlay_text": shot["on_screen_text_zh"],
            "audio_narration_expected": shot["voiceover_zh"],
            "style_id": style["id"],
            "asset_roles": list(shot["asset_roles"]),
            "media_pending_approval": True,
        })
        seen.add(sid)
    output = {
        "schema": "g4-citydiscount-promo-offline-plan.v1",
        "campaign_id": candidate["campaign_id"],
        "source_sha256": _canonical_sha(candidate),
        "story_title_zh": storyline["title_zh"],
        "story_logline_zh": storyline["logline_zh"],
        "dramatic_spine": list(storyline["dramatic_spine"]),
        "script_reviewed_by_owner": False,
        "purpose": "brand_first_motion_graphics",
        "shot_count": len(ordered), "duration_seconds": 60,
        "shots": ordered, "approval_gate": "blocked_pending_brand_assets_and_real_provider",
        "model_submission_allowed": False, "provider_reference_applied": False,
        "model_calls": 0, "actual_fee_usd": None, "video_generated": False,
        "g4_exit_approved": False, "publish_approved": False,
    }
    output["offline_plan_sha256"] = _canonical_sha(output)
    return output
