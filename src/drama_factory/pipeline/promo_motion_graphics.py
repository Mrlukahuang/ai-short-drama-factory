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


SCHEMA_3X4 = "g4-citydiscount-first-promo.v2"


def _build_coin_hunt_3x4(candidate: dict) -> dict:
    """Validate Owner's newest three-source felt sheep coin hunt WITHOUT permission.

    Keep legacy creative revision 3 valid for forensic reproducibility. The
    current production script is revision 4 and must NEVER silently inherit
    the original 9:16 aspect or an unsupported provider source ratio.
    """
    if type(candidate) is dict and candidate.get("schema_version") == SCHEMA_3X4:
        return _build_coin_hunt_3x4(candidate)
    if (type(candidate) is not dict
            or candidate.get("schema_version") != SCHEMA_3X4
            or candidate.get("project") != "CityDiscount"
            or candidate.get("revision") != 4
            or candidate.get("stage") != "G4"
            or candidate.get("req") != "R4.4"
            or candidate.get("status") != "creative_proposal_offline_only"):
        raise PromoPlanError("Owner v2 creative source or G4 stage invalid")
    fmt = candidate.get("format")
    production = candidate.get("production_requirements")
    style = candidate.get("style")
    story = candidate.get("storyline")
    controls = candidate.get("controls")
    brand = candidate.get("brand_asset_requirements")
    shots = candidate.get("shots")
    if (type(fmt) is not dict
            or (fmt.get("width"), fmt.get("height"), fmt.get("aspect_ratio"))
               != (1080, 1440, "3:4")
            or fmt.get("total_duration_seconds") != 60
            or fmt.get("shot_count") != 12 or fmt.get("fps_target") != 24
            or fmt.get("final_output_exact_pixels") is not True
            or fmt.get("provider_source_aspect_ratio") != "not_assumed_3_4_supported"
            or type(production) is not dict
            or production.get("exact_frame_size_px") != [1080, 1440]
            or production.get("frame_ratio") != "3:4"
            or production.get("all_visible_material") is None
            or production.get("mascot_height_fraction_max") != 0.27
            or production.get("mascot_height_fraction_target") != [0.15, 0.22]
            or production.get("digging_actions_per_stop") != 2
            or production.get("coins_discovered_per_stop") != 1
            or production.get("active_scene_categories") != [
                "supermarket", "restaurant_cafe", "community_shopping"]
            or production.get("no_paid_model_calls") is not True
            or production.get("visual_examples_are_illustrative") is not True
            or production.get("not_live_offers") is not True
            or production.get("source_evidence_repository") != "Mrlukahuang/nz-social-trend-radar"
            or type(production.get("source_to_scene")) is not list
            or len(production["source_to_scene"]) != 3
            or type(style) is not dict
            or style.get("owner_visual_direction_approved") is not True
            or style.get("final_3x4_film_approved") is not False
            or type(story) is not dict
            or story.get("script_reviewed_by_owner") is not False
            or story.get("brand_use_approved_for_render") is not False
            or type(controls) is not dict
            or controls.get("model_calls") != 0
            or controls.get("real_paid_call_authorized") is not False
            or controls.get("media_rights_and_remote_upload") != "not_approved"
            or controls.get("publish_approved") is not False
            or controls.get("g4_exit_approved") is not False
            or type(brand) is not dict
            or brand.get("coin",{}).get("face_mark") != "CD"
            or brand["coin"].get("canonical_coin_artwork_verified") is not False
            or brand.get("logo",{}).get("final_min_hold_seconds") != 3
            or brand["logo"].get("rights_verified") is not False
            or brand.get("family",{}).get("version_locked") is not False
            or type(shots) is not list or len(shots) != 12):
        raise PromoPlanError("Owner 1080x1440 and rights contract violated")
    evidence = production["source_to_scene"]
    if ([s.get("scene") for s in evidence] != production["active_scene_categories"]
            or [s.get("evidence") for s in evidence] != [
                "docs/plans/issue-281-col-k-source-writer-inventory.md",
                "system1_pipeline/fetchers/dynamic_handlers/grabone_handler.py",
                "system1_pipeline/fetchers/dynamic_handlers/cheapies_handler.py",
            ]):
        raise PromoPlanError("Unverified source-category evidence")
    expected_beats = [
        "setup", "mission", "city_map", "supermarket_arrival",
        "supermarket_dig", "restaurant_arrival", "restaurant_dig",
        "shopping_arrival", "shopping_dig", "exhausted_city_montage",
        "family_delivery", "cta",
    ]
    coin_indices = {4, 6, 8, 9, 10, 11}
    logo_slots = {1: "mascot_bag_or_scarf", 10: "coin_delivery_bag", 11: "end_card"}
    expected_end = ["CityDiscount", "替你到处挖折扣，让生活多一点。",
                    "关注 CityDiscount", "下次消费前，先来找找折扣。"]
    if story.get("end_card_lines") != expected_end:
        raise PromoPlanError("Official approved brand CTA must remain exact")
    valid_views = {"front", "side", "back", "three_quarter"}
    valid_actions = valid_views | {"happy", "wink", "sparkle", "jump", "thumbsup", "coin"}
    ordered = []
    for i, shot in enumerate(shots):
        fields = [shot.get("background_prompt_zh"),shot.get("voiceover_zh"),
                  shot.get("on_screen_text_zh")]
        cast = shot.get("visible_roles")
        view = shot.get("mascot_camera_view")
        act = shot.get("mascot_expression_or_action_hint")
        if (shot.get("shot_id") != f"s{i+1:02d}"
                or shot.get("start_ms") != i*5000
                or shot.get("end_ms") != (i+1)*5000
                or shot.get("duration_seconds") != 5
                or shot.get("storybeat") != expected_beats[i]
                or shot.get("shot_dependencies") != (
                    [] if i == 0 else [f"s{i:02d}"])
                or type(cast) is not list or not cast
                or not set(cast).issubset({"family","mascot"})
                or (("mascot" in cast) != (view in valid_views and act in valid_actions))
                or any(type(s) is not str or len(s) > 250 for s in fields)
                or not fields[0] or not fields[1]
                or (fields[2] != ("\n".join(expected_end) if i == 11 else ""))
                or any(_PRICE.search(s) for s in fields)
                or any(x.lower() in " ".join(fields).lower()
                       for x in _UNCLEARED_BRANDS + _FALSE_PRODUCTS)
                or shot.get("coin_mark_required") is not (i in coin_indices)
                or shot.get("logo_placement") != logo_slots.get(i)
                or shot.get("logo_hold_seconds") != (3 if i == 11 else 0)
                or shot.get("media_submission_approved") is not False
                or shot.get("real_model_result") != "not_run"
                or shot.get("human_visual_review") != "not_run"):
            raise PromoPlanError(f"Owner shot {i+1:02d} 3:4 or coin contract broken")
        if i in {4, 6, 8}:
            actions = shot.get("action_phases")
            if (type(actions) is not list or len(actions) != 4
                    or [v.get("event") for v in actions] != [
                        "first_shovel_dig", "second_shovel_dig",
                        "single_CD_coin_found", "pack_coin_and_depart",
                    ]
                    or [v.get("relative_ms") for v in actions] != [
                        0,1500,3000,4000]
                    or shot.get("coins_newly_found") != 1):
                raise PromoPlanError("Must have exactly two digs before ONE CD coin")
        if not isinstance(shot.get("owner_visual_direction_zh"),str):
            raise PromoPlanError("Missing owner visual")
        ordered.append({
            "shot_id":shot["shot_id"], "start_ms":shot["start_ms"],
            "end_ms":shot["end_ms"], "shot_title_zh":shot["shot_title_zh"],
            "storybeat":shot["storybeat"], "scene_anchor":shot["scene_anchor"],
            "video_background_prompt":fields[0],
            "owner_visual_direction_zh":shot["owner_visual_direction_zh"],
            "audio_narration_expected":fields[1],
            "postproduction_overlay_text":fields[2],
            "visible_roles":list(cast),
            "mascot_camera_view":view,
            "mascot_expression_or_action_hint":act,
            "action_phases":shot.get("action_phases",[]),
            "coin_mark_required":shot["coin_mark_required"],
            "logo_placement":shot["logo_placement"],
            "logo_hold_seconds":shot["logo_hold_seconds"],
            "camera_direction_zh":shot["camera_direction_zh"],
            "continuity_instruction_zh":shot["continuity_instruction_zh"],
            "sfx_cues_zh":list(shot["sfx_cues_zh"]),
            "media_pending_approval":True,
        })
    out = {
        "schema":"g4-citydiscount-promo-offline-plan.v2",
        "campaign_id":candidate["campaign_id"],
        "source_sha256":_canonical_sha(candidate),
        "story_title_zh":story["title_zh"],
        "story_logline_zh":story["logline_zh"],
        "output_width":1080,"output_height":1440,"output_aspect_ratio":"3:4",
        "fps_target":24,
        "mascot_max_frame_height_fraction":0.27,
        "source_scene_bindings":evidence,
        "production_audio":"instrumental_and_sfx_only",
        "shot_count":12,"duration_seconds":60,
        "shots":ordered,"end_card_lines":expected_end,
        "approval_gate":"blocked_pending_brand_assets_and_real_provider",
        "model_submission_allowed":False,"provider_reference_applied":False,
        "model_calls":0,"actual_fee_usd":None,"video_generated":False,
        "g4_exit_approved":False,"publish_approved":False,
    }
    out["offline_plan_sha256"] = _canonical_sha(out)
    return out


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
    brand = candidate.get("brand_asset_requirements")
    if (storyline.get("story_supplied_by_owner") is not True
            or type(storyline.get("end_card_lines")) is not list
            or storyline["end_card_lines"] != [
                "CityDiscount",
                "替你到处挖折扣，让生活多一点。",
                "关注 CityDiscount",
                "下次消费前，先来找找折扣。",
            ]
            or type(brand) is not dict
            or type(brand.get("logo")) is not dict
            or type(brand.get("coin")) is not dict
            or type(brand.get("family")) is not dict
            or brand["logo"].get("rights_verified") is not False
            or brand["logo"].get("final_min_hold_seconds") != 3
            or brand["coin"].get("canonical_coin_artwork_verified") is not False
            or brand["coin"].get("face_mark") != "CD"
            or brand["family"].get("version_locked") is not False):
        raise PromoPlanError("Brand, coin and owner story gates missing")
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
        if (any(type(x) is not str or len(x) > 250 for x in fields)
                or not fields[0].strip() or not fields[1].strip()
                or (i == 11 and fields[2] != "\n".join(storyline["end_card_lines"]))
                or (i != 11 and fields[2] != "")
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
        cast = shot.get("visible_roles")
        if (type(cast) is not list or not cast or len(set(cast)) != len(cast)
                or not set(cast).issubset({"family", "mascot"})
                or (("mascot" in cast) != (view in valid_views and action in valid_actions))
                or ("mascot" not in cast and (view is not None or action is not None))
                or type(camera) is not str or not camera.strip()
                or type(continuity) is not str or not continuity.strip()
                or type(shot.get("owner_visual_direction_zh")) is not str
                or not shot["owner_visual_direction_zh"].strip()
                or type(shot.get("shot_title_zh")) is not str
                or not shot["shot_title_zh"].strip()
                or type(shot.get("sfx_cues_zh")) is not list
                or any(type(x) is not str or not x.strip() for x in shot["sfx_cues_zh"])
                or type(shot.get("music_beat_zh")) is not str
                or not shot["music_beat_zh"].strip()
                or shot.get("storybeat") != (
                    "setup", "mission", "city_map", "hunt_groceries",
                    "hunt_food", "hunt_shopping", "hunt_outing",
                    "organise", "deliver", "payoff", "savings", "cta",
                )[i]
                or shot.get("coin_mark_required") is not (i in {0, 10, 11})
                or shot.get("logo_placement") != {
                    1: "mascot_chest",
                    7: "discount_book_cover",
                    11: "end_card",
                }.get(i)
                or shot.get("logo_hold_seconds") != (3 if i == 11 else 0)):
            raise PromoPlanError("Incomplete owner story, CD coin or brand continuity")
        # Explicitly keep source-image prompt and guaranteed later text overlay apart:
        # generated video model has no need to render logotypes or Chinese text.
        ordered.append({
            "shot_id": sid, "start_ms": shot["start_ms"],
            "end_ms": shot["end_ms"],
            "scene_anchor": shot["scene_anchor"],
            "shot_title_zh": shot["shot_title_zh"],
            "storybeat": shot["storybeat"],
            "owner_visual_direction_zh": shot["owner_visual_direction_zh"],
            "visible_roles": list(cast),
            "sfx_cues_zh": list(shot["sfx_cues_zh"]),
            "music_beat_zh": shot["music_beat_zh"],
            "coin_mark_required": shot["coin_mark_required"],
            "logo_placement": shot["logo_placement"],
            "logo_hold_seconds": shot["logo_hold_seconds"],
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
        "end_card_lines": list(storyline["end_card_lines"]),
        "sound_direction": dict(storyline["sound_direction"]),
        "brand_requirements": {
            "logo_source_sha256": brand["logo"]["source_sha256"],
            "logo_final_min_hold_seconds": 3,
            "coin_face_mark": "CD",
            "canonical_coin_artwork_verified": False,
            "family_asset_version_locked": False,
        },
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
