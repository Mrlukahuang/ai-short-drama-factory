"""AMEND-005 P2: local Fake Story Bible -> outline -> valid screenplay.

All IDs here are PROVISIONAL and NOT DB-backed. P3 must map actor/scene/
Bible IDs into properly scoped, existing Series assets before server approval.
No paid models, storage mutation, human approval, or video output.
"""
from __future__ import annotations

import hashlib
import json
import re

from drama_factory.models import StoryBible
from drama_factory.pipeline.fake_story_bible import SCHEMA as FAKE_BIBLE_SCHEMA
from drama_factory.pipeline.screenplay import Screenplay, SCRIPT_SCHEMA_VERSION
from drama_factory.pipeline.text import FakeTextProvider, ScriptContext, ScriptPlanRequest

SCRIPT_STAGE_SCHEMA = "fake-episode-screenplay.zh.v1"
_HASH = re.compile(r"[a-f0-9]{64}\Z")


class FakeScreenplayError(ValueError):
    pass


def _ref(prefix: str, seed: str) -> str:
    return f"{prefix}_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:14]


def build_fake_episode_screenplay(
    fake_bible: dict, *, episode_number: int = 1, target_duration_seconds: int = 60,
) -> dict:
    """Return two typed downstream documents; no DB reference is approved."""
    if not isinstance(fake_bible, dict):
        raise FakeScreenplayError("P1 Fake Story Bible envelope required")
    source = fake_bible.get("source_sha256")
    if (
        fake_bible.get("schema_version") != FAKE_BIBLE_SCHEMA
        or fake_bible.get("fake_only") is not True
        or fake_bible.get("approval_granted") is not False
        or fake_bible.get("model_calls") != 0
        or not isinstance(source, str)
        or _HASH.fullmatch(source) is None
    ):
        raise FakeScreenplayError("Unverified P1 Fake Story Bible envelope")
    if type(episode_number) is not int or not 1 <= episode_number <= 9999:
        raise FakeScreenplayError("Invalid Fake episode number")
    if (type(target_duration_seconds) is not int
            or not 60 <= target_duration_seconds <= 90):
        raise FakeScreenplayError("Fake six-shot episode duration must be 60–90 seconds")
    try:
        bible = StoryBible.model_validate(fake_bible["story_bible"])
    except (KeyError, ValueError, TypeError):
        raise FakeScreenplayError("Invalid canonical Story Bible schema") from None
    actor_a = _ref("asset", source + ":lead-a")
    actor_b = _ref("asset", source + ":lead-b")
    scene_id = _ref("asset", source + ":scene")
    series_id = _ref("proj", source + ":series")
    bible_id = _ref("bible", source + ":bible")
    ref_ids = {"actor_a": actor_a, "actor_b": actor_b, "scene": scene_id}
    context = ScriptContext(
        series_id=series_id,
        story_bible_id=bible_id,
        story_bible_json=bible.model_dump(mode="json"),
        allowed_actor_ids=[actor_a, actor_b],
        allowed_scene_id=scene_id,
    )
    request = ScriptPlanRequest(
        story_bible_id=bible_id,
        episode_number=episode_number,
        target_duration_seconds=target_duration_seconds,
        creative_brief=bible.logline[:5000],
        actor_asset_ids=[actor_a, actor_b],
        scene_asset_id=scene_id,
    )
    outline = FakeTextProvider().generate(request, context)
    base, remaining = divmod(target_duration_seconds, 6)
    shots = []
    for i in range(6):
        duration = base + (1 if i < remaining else 0)
        # Exactly one or two clearly synthetic Chinese lines per shot,
        # no invented plot/voice acting and no claim about the real premise.
        speaker = actor_a if i % 2 == 0 else actor_b
        lines = [
            {"speaker_actor_id": speaker,
             "text": f"FAKE 示例对白 {i+1}：这是时间线占位，不是实际剧本。"}
        ]
        if i == 0:
            lines.append({
                "speaker_actor_id": actor_b,
                "text": "FAKE 双人对白：仅检查双角色与字幕音轨结构。",
            })
        shots.append({
            "shot_id": f"S{i+1:03d}",
            "duration_seconds": duration,
            "action": f"FAKE 占位镜头 {i+1}：只使用梗概来源摘要作连续性上下文；{bible.logline[:100]}",
            "camera": ["双人中景", "女主特写", "全景", "男主近景", "侧面中景", "结尾定镜"][i],
            "character_ids": [actor_a, actor_b],
            "scene_id": scene_id,
            "dialogue": lines,
            "continuity_start": f"FAKE 场景状态 {i}",
            "continuity_end": f"FAKE 场景状态 {i+1}",
        })
    screenplay = Screenplay.model_validate({
        "schema_version": SCRIPT_SCHEMA_VERSION,
        "series_id": series_id,
        "story_bible_id": bible_id,
        "episode_number": episode_number,
        "episode_title": f"第{episode_number}集 · FAKE 分镜演示",
        "target_duration_seconds": target_duration_seconds,
        "shots": shots,
        "hook": "FAKE 首镜钩子占位；无真实内容评价。",
        "ending_cliffhanger": "FAKE 结尾悬念占位；无真实剧情质量保证。",
    })
    # Verify the existing EpisodeDraft conversion, WITHOUT writing it.
    screenplay.to_episode_draft()
    fingerprint = hashlib.sha256(
        json.dumps(fake_bible, sort_keys=True, ensure_ascii=False,
                   separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": SCRIPT_STAGE_SCHEMA,
        "step": "02_episode_script_and_03_screenplay",
        "input_sha256": fingerprint,
        "source_sha256": source,
        "status": "fake_only",
        "fake_only": True,
        "scope_validated_against_database": False,
        "provisional_asset_ids": True,
        "approval_granted": False,
        "publish_approved": False,
        "model_calls": 0,
        "paid_api_calls": 0,
        "actual_fee_usd": None,
        "provisional_refs": ref_ids,
        "script_outline": outline.model_dump(mode="json"),
        "screenplay": screenplay.model_dump(mode="json"),
    }
