"""Pure offline helpers for the local human-reviewed screenplay workflow.

No paid services or DB access. These functions NEVER grant human approvals.
"""
from __future__ import annotations

import hashlib
import json
import re

from drama_factory.pipeline.screenplay import Screenplay


class LocalStoryWizardError(ValueError):
    pass


def make_storyboard_template(
    series_id: str, story_bible_id: str, actor_ids: list[str],
    scene_id: str | None, *, episode_number: int = 1,
    shot_count: int = 3, seconds_per_shot: int = 20,
) -> dict:
    """Prefill valid, explicitly unfinished scene text using scoped asset IDs.

    The HTTP server must still verify actual Series/Bible/Actor/Scene ownership.
    Template creation has no persistence, approval or generation effect.
    """
    def valid(value: str, prefix: str) -> bool:
        return type(value) is str and re.fullmatch(
            rf"{prefix}_[a-f0-9]{{14}}", value,
        ) is not None

    if (
        not valid(series_id, "proj")
        or not valid(story_bible_id, "bible")
        or type(actor_ids) is not list or not actor_ids
        or len(actor_ids) > 8
        or any(not valid(actor, "asset") for actor in actor_ids)
        or len(set(actor_ids)) != len(actor_ids)
        or (scene_id is not None and not valid(scene_id, "asset"))
        or type(episode_number) is not int or not 1 <= episode_number <= 999
        or type(shot_count) is not int or not 1 <= shot_count <= 12
        or type(seconds_per_shot) is not int or not 1 <= seconds_per_shot <= 30
        or shot_count * seconds_per_shot > 90
    ):
        raise LocalStoryWizardError("Invalid local original storyboard selections")
    draft = {
        "schema_version": "screenplay.zh.v1",
        "series_id": series_id,
        "story_bible_id": story_bible_id,
        "episode_number": episode_number,
        "episode_title": "请填写原创分集标题",
        "target_duration_seconds": shot_count * seconds_per_shot,
        "hook": "请填写开头三秒悬念",
        "ending_cliffhanger": "请填写本集结尾悬念",
        "shots": [
            {
                "shot_id": f"S{i:03d}",
                "duration_seconds": seconds_per_shot,
                "action": f"请编写第 {i} 镜的原创画面动作",
                "camera": "中景",
                "character_ids": actor_ids[:],
                "scene_id": scene_id,
                "dialogue": [],
                "continuity_start": "请核对镜头开始时人物与道具位置",
                "continuity_end": "请核对镜头结束时人物与道具位置",
            }
            for i in range(1, shot_count + 1)
        ],
    }
    return Screenplay.model_validate(draft).model_dump(mode="json")


def canonical_screenplay_digest(payload: dict) -> str:
    """Stable identity of exactly validated screenplay fields and values.

    Used only to detect a changed editor draft before operator presses Commit.
    NOT a digital signature, authenticated review or bypass of API validation.
    """
    screenplay = Screenplay.model_validate(payload)
    normalized = json.dumps(
        screenplay.model_dump(mode="json"),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def validated_draft_still_matches(
    submitted: dict, validated: dict | None, series_id: str,
) -> bool:
    """Guard UI commit against stale validation and cross-series navigation."""
    if type(validated) is not dict or type(series_id) is not str:
        return False
    if validated.get("series_id") != series_id or validated.get("valid") is not True:
        return False
    if validated.get("review_required") is not True or validated.get("paid_api_calls") != 0:
        return False
    try:
        return (
            submitted.get("series_id") == series_id
            and validated.get("fingerprint") == canonical_screenplay_digest(submitted)
        )
    except (ValueError, TypeError, AttributeError):
        return False


def apply_visual_storyboard(
    original: dict, *, episode_number: int, episode_title: str,
    hook: str, ending_cliffhanger: str, edited_shots: list[dict],
    allowed_actor_ids: list[str], allowed_scene_ids: list[str],
) -> dict:
    """Build exact Screenplay from a visual form; never grant an approval.

    No changed shot may disappear or change identity, order, or silently lose
    an approved dialogue cue. Both old and newly supplied actor/scene IDs
    must match the selected series' current asset list. HTTP scope validation
    remains mandatory before committing the returned draft.
    """
    try:
        base = Screenplay.model_validate(original)
        if (
            type(edited_shots) is not list or len(edited_shots) != len(base.shots)
            or len(edited_shots) > 12 or not edited_shots
            or type(allowed_actor_ids) is not list
            or type(allowed_scene_ids) is not list
            or not all(type(x) is str for x in allowed_actor_ids + allowed_scene_ids)
        ):
            raise ValueError("Invalid visual editor shot count or asset inventory")
        output = base.model_dump(mode="json")
        output.update({
            "episode_number": episode_number,
            "episode_title": episode_title,
            "hook": hook,
            "ending_cliffhanger": ending_cliffhanger,
        })
        converted = []
        for current, edit in zip(base.shots, edited_shots):
            if type(edit) is not dict or edit.get("shot_id") != current.shot_id:
                raise ValueError("Shot identity/order changed")
            cast = edit["character_ids"]
            scene = edit["scene_id"]
            cues = edit["dialogue"]
            if (
                type(cast) is not list or len(cast) > 8
                or len(cast) != len(set(cast))
                or any(type(a) is not str or a not in allowed_actor_ids for a in cast)
                or (scene is not None and
                    (type(scene) is not str or scene not in allowed_scene_ids))
                or type(cues) is not list or len(cues) > 20
                or any(type(cue) is not dict for cue in cues)
            ):
                raise ValueError("Unknown actor/scene reference or invalid dialogue rows")
            # Deliberately include all cues, so invalid/half-specified timing
            # fails Pydantic instead of losing a line on conversion.
            changed = current.model_dump(mode="json")
            changed.update({
                key: edit[key] for key in (
                    "duration_seconds", "action", "camera", "character_ids",
                    "scene_id", "continuity_start", "continuity_end", "dialogue",
                )
            })
            converted.append(changed)
        output["shots"] = converted
        output["target_duration_seconds"] = sum(s["duration_seconds"] for s in converted)
        if (
            type(episode_number) is not int
            or type(output["target_duration_seconds"]) is not int
            or not 1 <= output["target_duration_seconds"] <= 90
        ):
            raise ValueError("Local technical preview duration must be 1–90 seconds")
        return Screenplay.model_validate(output).model_dump(mode="json")
    except (ValueError, TypeError, KeyError, OverflowError):
        raise LocalStoryWizardError(
            "Visual storyboard invalid: correct cast, cue timing and shot lengths"
        ) from None
