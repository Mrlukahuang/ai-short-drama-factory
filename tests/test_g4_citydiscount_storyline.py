"""G4: Owner's actual CityDiscount Auckland treasure-hunt ad script.

12 shots / 60 seconds; production plan is OFFLINE, no video, no remote media.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path

import pytest
from drama_factory.pipeline.promo_motion_graphics import (
    PromoPlanError, build_offline_citydiscount_promo_plan,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/pilots/citydiscount_first_promo_v1.json"
INVENTORY = ROOT / "assets/citydiscount/v1/character_views_inventory.json"
ASSET_MANIFEST = ROOT / "assets/citydiscount/v1/asset_manifest.json"

TITLES = [
    "钱包的小烦恼", "寻宝员出发", "奥克兰藏着宝", "第一站，买菜",
    "第二站，美食", "第三站，购物", "第四站，出去玩",
    "把发现整理好", "折扣来到身边", "愿望慢慢实现",
    "省下来的小幸福", "品牌定格",
]
NARRATION = [
    "在奥克兰，想把日子过丰富，钱包却总得算一算。",
    "找折扣这件事，交给 CityDiscount。",
    "我们跑遍城市，寻找藏在日常里的好优惠。",
    "一篮新鲜，找找更划算的买法。",
    "一顿好吃，也值得替你多找一找。",
    "发现优惠，再把条件看清楚。",
    "连周末的小快乐，也一起找。",
    "东找一点，西找一点，再替你整理好。",
    "把城市各处的好折扣，带到你身边。",
    "该买的买，想吃的吃，周末也能出去走走。",
    "省下来的，留给下一份小幸福。",
    "CityDiscount，替你到处挖折扣，让生活多一点。",
]


def _draft():
    return json.loads(SOURCE.read_text("utf-8"))


def test_owner_twelve_shot_script_and_audio_match_without_rewrites():
    source = _draft()
    plan = build_offline_citydiscount_promo_plan(source)
    assert plan["story_title_zh"] == "把奥克兰的好折扣，挖到你身边"
    assert plan["shot_count"] == 12 and plan["duration_seconds"] == 60
    assert source["revision"] == 3
    assert [s["shot_title_zh"] for s in plan["shots"]] == TITLES
    assert [s["audio_narration_expected"] for s in plan["shots"]] == NARRATION
    assert [s["start_ms"] for s in plan["shots"]] == list(range(0, 60000, 5000))
    assert [s["end_ms"] for s in plan["shots"]] == list(range(5000, 65000, 5000))
    assert [s["storybeat"] for s in plan["shots"]] == [
        "setup", "mission", "city_map", "hunt_groceries",
        "hunt_food", "hunt_shopping", "hunt_outing",
        "organise", "deliver", "payoff", "savings", "cta",
    ]
    assert len(plan["dramatic_spine"]) == 4
    assert "天空塔" in source["shots"][2]["owner_visual_direction_zh"]
    assert "海港大桥" in source["shots"][2]["owner_visual_direction_zh"]
    assert "海港" in source["shots"][6]["owner_visual_direction_zh"]
    assert all(s["owner_visual_direction_zh"]
               and s["camera_direction_zh"]
               and s["continuity_instruction_zh"]
               and s["sfx_cues_zh"]
               and s["music_beat_zh"] for s in plan["shots"])


def test_family_only_shots_are_not_falsely_forced_to_include_mascot():
    result = build_offline_citydiscount_promo_plan(_draft())
    assert result["shots"][0]["visible_roles"] == ["family"]
    assert result["shots"][9]["visible_roles"] == ["family"]
    assert result["shots"][0]["mascot_camera_view"] is None
    assert result["shots"][9]["mascot_camera_view"] is None
    assert result["shots"][10]["visible_roles"] == ["family", "mascot"]
    assert result["brand_requirements"]["family_asset_version_locked"] is False


def test_actual_mascot_inventory_angles_and_cd_coin_brand_constraints():
    reference = json.loads(INVENTORY.read_text("utf-8"))
    roles = {r["role"] for r in reference["images"]}
    asset_manifest = json.loads(ASSET_MANIFEST.read_text("utf-8"))
    logo = next(a for a in asset_manifest["assets"] if a["role"] == "brand_reference")
    result = build_offline_citydiscount_promo_plan(_draft())
    for shot in result["shots"]:
        if "mascot" in shot["visible_roles"]:
            assert shot["mascot_camera_view"] in {
                "front", "side", "back", "three_quarter"
            }
            assert shot["mascot_camera_view"] in roles
            assert shot["mascot_expression_or_action_hint"] in roles
        else:
            assert shot["mascot_camera_view"] is None
            assert shot["mascot_expression_or_action_hint"] is None
    assert [x["shot_id"] for x in result["shots"] if x["coin_mark_required"]] == [
        "s01", "s11", "s12"
    ]
    assert [x["logo_placement"] for x in result["shots"]
            if x["logo_placement"] is not None] == [
                "mascot_chest", "discount_book_cover", "end_card",
            ]
    assert result["shots"][-1]["logo_hold_seconds"] == 3
    assert result["brand_requirements"]["coin_face_mark"] == "CD"
    assert result["brand_requirements"]["logo_source_sha256"] == logo["source_sha256"]
    assert result["brand_requirements"]["canonical_coin_artwork_verified"] is False
    assert result["model_calls"] == 0
    assert result["model_submission_allowed"] is False
    assert result["video_generated"] is False
    assert result["publish_approved"] is False
    assert result["script_reviewed_by_owner"] is False


def test_end_card_is_exact_owner_copy_and_cta_only_at_end():
    plan = build_offline_citydiscount_promo_plan(_draft())
    assert plan["end_card_lines"] == [
        "CityDiscount", "替你到处挖折扣，让生活多一点。",
        "关注 CityDiscount", "下次消费前，先来找找折扣。",
    ]
    assert all(x["postproduction_overlay_text"] == ""
               for x in plan["shots"][:-1])
    assert plan["shots"][-1]["postproduction_overlay_text"] == "\n".join(
        plan["end_card_lines"]
    )
    assert plan["sound_direction"]["mascot_nonverbal"]


@pytest.mark.parametrize("mutate", [
    lambda s: s["shots"][0].update(coin_mark_required=False),
    lambda s: s["shots"][11].update(logo_hold_seconds=2),
    lambda s: s["shots"][9].update(mascot_camera_view="front"),
    lambda s: s["shots"][1].update(logo_placement=None),
    lambda s: s["shots"][11].update(on_screen_text_zh="关注 App"),
    lambda s: s["shots"][3].update(storybeat="reversal"),
    lambda s: s["storyline"].update(script_reviewed_by_owner=True),
    lambda s: s["brand_asset_requirements"]["coin"].update(
        canonical_coin_artwork_verified=True),
])
def test_cannot_silently_drop_owner_scene_requirements_or_mint_approval(mutate):
    source = copy.deepcopy(_draft())
    mutate(source)
    with pytest.raises(PromoPlanError):
        build_offline_citydiscount_promo_plan(source)


def test_narration_change_invalidates_hash_but_never_mints_media_permission():
    source = _draft()
    initial = build_offline_citydiscount_promo_plan(source)
    updated = copy.deepcopy(source)
    updated["shots"][4]["voiceover_zh"] += "啊"
    changed = build_offline_citydiscount_promo_plan(updated)
    assert changed["source_sha256"] != initial["source_sha256"]
    assert changed["offline_plan_sha256"] != initial["offline_plan_sha256"]
    assert changed["provider_reference_applied"] is False
