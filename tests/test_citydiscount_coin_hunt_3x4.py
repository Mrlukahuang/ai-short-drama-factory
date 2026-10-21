"""G4 first CityDiscount film: Owner v2 coin digging, three evidenced source types, EXACT 3:4 output."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import pytest
from drama_factory.pipeline.promo_motion_graphics import (
    PromoPlanError, build_offline_citydiscount_promo_plan,
)

ROOT=Path(__file__).resolve().parents[1]
CURRENT=ROOT/"config/pilots/citydiscount_coin_hunt_1080x1440_v2.json"
HISTORY=ROOT/"config/pilots/citydiscount_first_promo_v1.json"
TITLES=[
    "心愿清单","小羊拿铲子出发","城市跑跑地图",
    "第一站，买菜","挖两下，第一枚！",
    "第二站，咖啡美食","再挖两下，第二枚！",
    "第三站，购物发现","两铲，第三枚 CD！",
    "东跑西跑，好累呀","把金币交给一家人",
    "CityDiscount 品牌定格"
]

def new():
    return json.loads(CURRENT.read_text("utf-8"))

def test_v2_is_the_owners_current_1080x1440_3by4_production_plan():
    raw=new()
    out=build_offline_citydiscount_promo_plan(raw)
    assert raw["revision"]==4
    assert (out["output_width"],out["output_height"],out["output_aspect_ratio"]) == (1080,1440,"3:4")
    assert raw["format"]["width"]*4==raw["format"]["height"]*3
    assert out["fps_target"]==24
    assert out["duration_seconds"]==60 and out["shot_count"]==12
    assert [s["shot_title_zh"] for s in out["shots"]]==TITLES
    assert [s["start_ms"] for s in out["shots"]]==list(range(0,60000,5000))
    assert [s["end_ms"] for s in out["shots"]]==list(range(5000,65000,5000))
    assert out["mascot_max_frame_height_fraction"] == .27
    assert raw["production_requirements"]["mascot_height_fraction_target"]==[.15,.22]
    assert out["production_audio"]=="instrumental_and_sfx_only"
    assert out["model_calls"]==0 and out["video_generated"] is False
    assert out["publish_approved"] is False and out["model_submission_allowed"] is False

def test_third_party_source_types_are_real_code_evidence_not_fake_offers():
    d=new()
    bindings=d["production_requirements"]["source_to_scene"]
    assert [b["scene"] for b in bindings] == [
        "supermarket", "restaurant_cafe", "community_shopping"]
    assert "issue-281" in bindings[0]["evidence"]
    assert "grabone_handler.py" in bindings[1]["evidence"]
    assert "cheapies_handler.py" in bindings[2]["evidence"]
    assert all(b["safety"] and b["example"] for b in bindings)
    assert d["production_requirements"]["not_live_offers"] is True
    assert all("NZ$" not in s["voiceover_zh"] for s in d["shots"])

def test_every_location_requires_two_distinct_shovels_before_one_coin():
    plan=build_offline_citydiscount_promo_plan(new())
    digs=[s for s in plan["shots"] if s["storybeat"].endswith("_dig")]
    assert [s["shot_id"] for s in digs] == ["s05", "s07", "s09"]
    for shot in digs:
        assert [(a["relative_ms"],a["event"]) for a in shot["action_phases"]] == [
            (0, "first_shovel_dig"), (1500, "second_shovel_dig"),
            (3000, "single_CD_coin_found"), (4000,"pack_coin_and_depart")]
    assert [s["shot_id"] for s in plan["shots"] if s["coin_mark_required"]] == [
        "s05","s07","s09","s10","s11","s12"]
    assert "疲" in new()["shots"][9]["owner_visual_direction_zh"] or "喘" in new()["shots"][9]["owner_visual_direction_zh"]
    assert "跑走" in new()["shots"][10]["owner_visual_direction_zh"]

def test_exact_logo_end_hold_and_incomplete_rights_still_gate_paid_video():
    out=build_offline_citydiscount_promo_plan(new())
    assert [(s["shot_id"],s["logo_placement"]) for s in out["shots"]
            if s["logo_placement"]] == [
        ("s02","mascot_bag_or_scarf"),
        ("s11","coin_delivery_bag"),("s12","end_card")]
    assert out["shots"][11]["logo_hold_seconds"]==3
    assert out["shots"][11]["postproduction_overlay_text"]=="\n".join(
        ["CityDiscount","替你到处挖折扣，让生活多一点。",
         "关注 CityDiscount","下次消费前，先来找找折扣。"])
    assert new()["brand_asset_requirements"]["coin"]["canonical_coin_artwork_verified"] is False
    assert new()["brand_asset_requirements"]["family"]["version_locked"] is False

@pytest.mark.parametrize("modify",[
    lambda d: d["format"].update(width=1080,height=1920,aspect_ratio="9:16"),
    lambda d: d["format"].update(width=1024),
    lambda d: d["production_requirements"].update(mascot_height_fraction_max=.5),
    lambda d: d["production_requirements"].update(digging_actions_per_stop=1),
    lambda d: d["shots"][4].update(coins_newly_found=2),
    lambda d: d["shots"][4]["action_phases"][1].update(event="single_CD_coin_found"),
    lambda d: d["shots"][6].update(coin_mark_required=False),
    lambda d: d["shots"][10].update(logo_placement=None),
    lambda d: d["shots"][11].update(logo_hold_seconds=1),
    lambda d: d["controls"].update(real_paid_call_authorized=True),
    lambda d: d["controls"].update(media_rights_and_remote_upload="approved"),
    lambda d: d["controls"].update(publish_approved=True),
    lambda d: d["production_requirements"]["source_to_scene"][1].update(evidence="made_up.py"),
    lambda d: d["shots"][4].update(on_screen_text_zh="限时NZ$19.99"),
])
def test_wrong_dimension_dig_safety_or_claim_is_rejected(modify):
    x=copy.deepcopy(new());modify(x)
    with pytest.raises(PromoPlanError):
        build_offline_citydiscount_promo_plan(x)

def test_old_9_16_file_is_historical_and_still_reproducible():
    previous=json.loads(HISTORY.read_text("utf-8"))
    assert previous["revision"]==3
    legacy=build_offline_citydiscount_promo_plan(previous)
    assert legacy["schema"].endswith(".v1") and legacy["shot_count"]==12
    assert previous["format"]["aspect_ratio"]=="9:16"
    assert legacy["model_submission_allowed"] is False
