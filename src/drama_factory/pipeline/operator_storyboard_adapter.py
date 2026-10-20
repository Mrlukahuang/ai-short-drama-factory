"""G4/R4.4: generic operator storyboard -> existing typed film-factory stages.

This is NOT an extra CityDiscount video pipeline. It adapts reviewed creative
cards for any series/cast to the existing StoryBible, FakeTextProvider,
Screenplay, EpisodeDraft and screenplay_video_plan contracts.

This function neither authors a story with AI nor approves/reviews it.
Provider reference images, live video, speech and FFmpeg remain independent
existing downstream stages with their own approval gates.
"""
from __future__ import annotations

import hashlib
import json

from drama_factory.models import StoryBible
from drama_factory.pipeline.screenplay import Screenplay
from drama_factory.pipeline.screenplay_video_plan import build_screenplay_video_plan
from drama_factory.pipeline.text import (
    FakeTextProvider, ScriptContext, ScriptPlanRequest,
)


class StoryboardAdapterError(ValueError):
    """Conceal private creative input in errors."""


def _sha(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_operator_storyboard_preview(
    *, series_id: str, story_bible_id: str, story_bible: StoryBible,
    episode_number: int, episode_title: str, scene_id: str,
    style_prompt: str, actor_descriptions: dict[str, str],
    shot_cards: list[dict], source_description: str,
) -> dict:
    """Make a deterministic, *unapproved* preview from real typed contracts.

    shot_cards are operator/author supplied, never FakeTextProvider-authored.
    Voiceover is kept outside in-character dialogue; the existing W3 audio/
    subtitle layer must separately align any approved actual narration.
    """
    if not isinstance(story_bible, StoryBible):
        raise StoryboardAdapterError("Canonical StoryBible required")
    if (type(series_id) is not str or not series_id
            or type(story_bible_id) is not str or not story_bible_id
            or type(scene_id) is not str or not scene_id
            or type(episode_title) is not str or not episode_title.strip()
            or type(source_description) is not str or not source_description.strip()
            or len(source_description) > 5000
            or type(style_prompt) is not str or not style_prompt.strip()
            or type(episode_number) is not int or not 1 <= episode_number <= 9999
            or type(actor_descriptions) is not dict
            or not 1 <= len(actor_descriptions) <= 8
            or any(type(a) is not str or not a or
                   type(v) is not str or not v.strip()
                   for a,v in actor_descriptions.items())
            or type(shot_cards) is not list
            or not 1 <= len(shot_cards) <= 12):
        raise StoryboardAdapterError("Invalid creative scope, style or cast")
    actors = list(actor_descriptions)
    ids = []
    normalized = []
    audio_plan = []
    overlays = []
    dependencies = []
    total = 0
    for number, card in enumerate(shot_cards):
        if type(card) is not dict:
            raise StoryboardAdapterError("Invalid storyboard card")
        if (card.get("paid_execution_authorized") is True
                or card.get("media_submission_approved") is True
                or card.get("operator_reviewed") is True):
            raise StoryboardAdapterError("Untrusted shot card cannot grant production approval")
        name = card.get("shot_id")
        duration = card.get("duration_seconds")
        visible = card.get("character_ids")
        dialogue = card.get("dialogue", [])
        parents = card.get("depends_on", [])
        if (type(name) is not str or not name
                or name in ids or type(duration) is not int
                or not 3 <= duration <= 10
                or type(visible) is not list
                or len(set(visible)) != len(visible)
                or not set(visible).issubset(actors)
                or type(dialogue) is not list
                or type(parents) is not list
                or len(set(parents)) != len(parents)
                or any(p not in ids for p in parents)
                or type(card.get("action")) is not str
                or not card["action"].strip()
                or type(card.get("camera")) is not str
                or not card["camera"].strip()
                or any(type(c) is not dict or
                       c.get("speaker_actor_id") not in visible or
                       type(c.get("text")) is not str or not c["text"].strip()
                       for c in dialogue)):
            raise StoryboardAdapterError("Foreign cast, dialogue, duration or dependency")
        narration = card.get("voiceover_text", "")
        overlay = card.get("overlay_text", "")
        if (type(narration) is not str or len(narration) > 500
                or type(overlay) is not str or len(overlay) > 500):
            raise StoryboardAdapterError("Invalid narration or overlay")
        continuity_start = card.get("continuity_start", f"shot_{number:02d}_start")
        continuity_end = card.get("continuity_end", f"shot_{number:02d}_end")
        if (type(continuity_start) is not str or not continuity_start
                or type(continuity_end) is not str or not continuity_end):
            raise StoryboardAdapterError("Missing continuity endpoints")
        normalized.append({
            "shot_id": name, "duration_seconds": duration,
            "action": card["action"], "camera": card["camera"],
            "character_ids": visible, "scene_id": scene_id,
            "dialogue": dialogue,
            "continuity_start": continuity_start,
            "continuity_end": continuity_end,
        })
        audio_plan.append({
            "shot_id": name, "text": narration,
            "kind": "out_of_character_narration",
            "actual_speech_generated": False,
        })
        overlays.append({"shot_id": name, "text": overlay,
                         "status": "not_rendered"})
        dependencies.append({"shot_id": name, "depends_on": list(parents)})
        ids.append(name)
        total += duration
    if not 30 <= total <= 90:
        raise StoryboardAdapterError("G4 preview must cover 30 to 90 seconds")
    context = ScriptContext(
        series_id=series_id, story_bible_id=story_bible_id,
        story_bible_json=story_bible.model_dump(mode="json"),
        allowed_actor_ids=actors, allowed_scene_id=scene_id,
    )
    outline = FakeTextProvider().generate(
        ScriptPlanRequest(
            story_bible_id=story_bible_id,
            episode_number=episode_number,
            target_duration_seconds=total,
            creative_brief=source_description,
            actor_asset_ids=actors, scene_asset_id=scene_id,
        ), context,
    )
    screenplay = Screenplay.model_validate({
        "series_id": series_id, "story_bible_id": story_bible_id,
        "episode_number": episode_number,
        "episode_title": episode_title,
        "target_duration_seconds": total,
        "shots": normalized,
        "hook": shot_cards[0]["action"][:300],
        "ending_cliffhanger": shot_cards[-1]["action"][:300],
    })
    episode_draft = screenplay.to_episode_draft()
    video_plan = build_screenplay_video_plan(
        screenplay, context, style_prompt=style_prompt,
        actor_descriptions=actor_descriptions,
    )
    input_doc = {
        "series_id": series_id, "story_bible_id": story_bible_id,
        "story_bible": story_bible.model_dump(mode="json"),
        "episode_number": episode_number, "episode_title": episode_title,
        "scene_id": scene_id, "style_prompt": style_prompt,
        "actor_descriptions": actor_descriptions,
        "shot_cards": shot_cards,
        "source_description": source_description,
    }
    return {
        "schema": "g4-operator-storyboard-adapter.v1",
        "source_sha256": _sha(input_doc),
        "story_bible": story_bible.model_dump(mode="json"),
        "outline": outline.model_dump(mode="json"),
        "screenplay": screenplay.model_dump(mode="json"),
        "episode_draft": episode_draft.model_dump(mode="json"),
        "video_request_plan": video_plan,
        "narration_plan": audio_plan,
        "overlay_plan": overlays,
        "shot_dependencies": dependencies,
        "shot_count": len(ids), "duration_seconds": total,
        "operator_supplied_storyboard": True,
        "fake_outline_is_not_an_authored_story": True,
        "script_reviewed_by_operator": False,
        "visual_assets_authenticated": False,
        "provider_reference_applied": False,
        "real_speech_generated": False,
        "real_video_generated": False,
        "paid_model_calls": 0, "actual_fee_usd": None,
        "publish_approved": False, "g4_exit_approved": False,
    }
