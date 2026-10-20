"""G4 R4.4: ONE real repository adapter, TWO unrelated creative pilots."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from drama_factory.models import StoryBible
from drama_factory.pipeline.operator_storyboard_adapter import (
    StoryboardAdapterError, build_operator_storyboard_preview,
)
from drama_factory.pipeline.screenplay import Screenplay
from drama_factory.pipeline.text import ScriptOutline

ROOT = Path(__file__).resolve().parents[1]


def _bible(*, name="Example"):
    return StoryBible(
        title=name, logline=f"{name} local story prototype",
        genre="短剧与品牌影片的通用测试",
        canon="本测试只是离线的剧情约束，不代表自动编剧完成",
        relationship_notes="角色/场景按照已有资产引用控制",
    )


def _citydiscount():
    """CityDiscount is an input fixture; the adapter never names this brand."""
    src = json.loads((ROOT/"config/pilots/citydiscount_first_promo_v1.json").read_text("utf-8"))
    mascot = "asset_00000000000001"
    cards=[]
    for row in src["shots"]:
        cards.append({
            "shot_id": row["shot_id"],
            "duration_seconds": row["duration_seconds"],
            "action": row["background_prompt_zh"],
            "camera": "毛毡微缩场景中景",
            "character_ids": [mascot],
            "dialogue": [],
            "voiceover_text": row["voiceover_zh"],
            "overlay_text": row["on_screen_text_zh"],
            "depends_on": row["shot_dependencies"],
            "continuity_start": f"{row['shot_id']} 开始",
            "continuity_end": f"{row['shot_id']} 结束",
        })
    return {
        "series_id": "proj_00000000000001",
        "story_bible_id": "bible_00000000000001",
        "story_bible": _bible(name="NZ local discovery"),
        "episode_number": 1,
        "episode_title": "本地选择",
        "scene_id": "asset_00000000000002",
        "style_prompt": "针毡微缩世界，角色面部和绿色围巾外观一致",
        "actor_descriptions": {
            mascot: "奶油白毛毡小羊，棕色大眼睛与墨绿围巾，形象固定"
        },
        "shot_cards": cards,
        "source_description": "在新西兰寻找本地消费信息、了解条件并理性比较",
    }


def _other_story():
    """Completely unrelated dual-character scene, same planning code."""
    a,b = "asset_00000000000003","asset_00000000000004"
    cards=[]
    for i in range(6):
        sid=f"shot{i+1}"
        cards.append({
            "shot_id": sid, "duration_seconds": 5,
            "action": f"两个毛毡玩偶在车站讨论一张失而复得的车票，镜头{i+1}",
            "camera": "车站中景",
            "character_ids": [a,b],
            "dialogue": [
                {"speaker_actor_id": a if i % 2 == 0 else b,
                 "text": "我在这里等你。" if i % 2 == 0 else "我已经找到了。"},
            ],
            "voiceover_text": "",
            "overlay_text": "",
            "depends_on": [f"shot{i}"] if i else [],
        })
    return {
        "series_id": "proj_00000000000002",
        "story_bible_id": "bible_00000000000002",
        "story_bible": _bible(name="Found ticket"),
        "episode_number": 1, "episode_title": "车票",
        "scene_id": "asset_00000000000005",
        "style_prompt": "毛毡玩偶车站实景，统一环境材质",
        "actor_descriptions": {
            a: "棕色卷发毛毡玩偶，蓝色外套",
            b: "红色短发毛毡玩偶，红色大衣",
        },
        "shot_cards": cards,
        "source_description": "两个朋友在车站找回一张丢失的车票",
    }


@pytest.mark.parametrize("fixture,count", [(_citydiscount,12), (_other_story,6)])
def test_two_unrelated_projects_use_same_existing_contract(fixture,count):
    r=build_operator_storyboard_preview(**fixture())
    assert r["shot_count"] == count
    assert r["duration_seconds"] == count*5
    assert r["schema"] == "g4-operator-storyboard-adapter.v1"
    assert Screenplay.model_validate(r["screenplay"]).to_episode_draft().model_dump(mode="json") == r["episode_draft"]
    assert ScriptOutline.model_validate(r["outline"]).is_mock is True
    assert r["video_request_plan"]["video_generated"] is False
    assert len(r["video_request_plan"]["shots"]) == count
    assert r["fake_outline_is_not_an_authored_story"] is True
    assert r["script_reviewed_by_operator"] is False
    assert r["provider_reference_applied"] is False
    assert r["actual_fee_usd"] is None
    assert r["publish_approved"] is False
    assert build_operator_storyboard_preview(**fixture()) == r


def test_narration_does_not_impersonate_the_mascot():
    r=build_operator_storyboard_preview(**_citydiscount())
    assert all(not shot["dialogue"] for shot in r["screenplay"]["shots"])
    assert all(row["text"] and not row["actual_speech_generated"] for row in r["narration_plan"])
    assert r["episode_draft"]["shots"][0]["dialogue"] == []
    assert r["real_speech_generated"] is False
    assert r["overlay_plan"][0]["status"] == "not_rendered"


def test_two_actor_speaker_binding_is_strict():
    r=build_operator_storyboard_preview(**_other_story())
    first=r["screenplay"]["shots"][0]
    assert first["dialogue"][0]["speaker_actor_id"] == "asset_00000000000003"
    assert r["episode_draft"]["shots"][0]["dialogue_cues"]


def test_no_foreign_speaker_or_hidden_identity():
    data=_other_story()
    data["shot_cards"][1]["dialogue"][0]["speaker_actor_id"]="asset_foreign"
    with pytest.raises(StoryboardAdapterError):
        build_operator_storyboard_preview(**data)
    data=_citydiscount()
    data["shot_cards"][0]["character_ids"] = ["unknown_cast"]
    with pytest.raises(StoryboardAdapterError):
        build_operator_storyboard_preview(**data)


def test_no_missing_or_future_dependencies():
    data=_citydiscount()
    data["shot_cards"][1]["depends_on"]=["s12"]
    with pytest.raises(StoryboardAdapterError):
        build_operator_storyboard_preview(**data)
    data=_citydiscount()
    data["shot_cards"][0]["depends_on"]=["s02"]
    with pytest.raises(StoryboardAdapterError):
        build_operator_storyboard_preview(**data)


def test_missing_shot_or_wrong_60_second_timeline_rejected():
    data=_citydiscount()
    data["shot_cards"][0]["duration_seconds"]=2
    with pytest.raises(StoryboardAdapterError):
        build_operator_storyboard_preview(**data)
    data=_citydiscount()
    data["shot_cards"] = data["shot_cards"][:3]
    with pytest.raises(StoryboardAdapterError):
        build_operator_storyboard_preview(**data)


def test_changing_creative_input_invalidates_stable_preview_sha():
    data=_citydiscount()
    a=build_operator_storyboard_preview(**data)
    changed=copy.deepcopy(data)
    changed["shot_cards"][4]["action"]+="，固定左侧构图"
    b=build_operator_storyboard_preview(**changed)
    assert a["source_sha256"] != b["source_sha256"]
    assert a["video_request_plan"]["screenplay_sha256"] != b["video_request_plan"]["screenplay_sha256"]


def test_no_model_provider_calls_even_with_approval_like_fields():
    data=_citydiscount()
    data["shot_cards"][0]["paid_execution_authorized"] = True
    with pytest.raises(StoryboardAdapterError, match="cannot grant"):
        build_operator_storyboard_preview(**data)
    data=_citydiscount()
    result=build_operator_storyboard_preview(**data)
    assert result["paid_model_calls"] == 0
    assert result["real_video_generated"] is False
    assert result["video_request_plan"]["paid_execution_authorized"] is False
