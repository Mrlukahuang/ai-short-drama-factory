"""G4 W2: read-only, version-pinned per-shot assets on top of the existing plan.

No database writes, media transfer, provider calls or approval transitions.
Asset SHA refers to stored *specification JSON*, NOT a reference image/audio.
"""
from __future__ import annotations

import hashlib
import json
import re

from drama_factory.models import ActorBible, SceneBible, StoryBible, VoiceBible
from .screenplay import Screenplay, check_screenplay_scope
from .screenplay_video_plan import build_screenplay_video_plan
from .text import ScriptContext

_SHA = re.compile(r"[a-f0-9]{64}\Z")
SCHEMA = "g4-shot-asset-binding.v1"


class ShotAssetBindingError(ValueError):
    """Invalid or stale pin. Do not leak private asset specifications in errors."""


def canonical_json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _digest(value: str | None, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise ShotAssetBindingError("Missing or invalid source SHA256")


def _asset(db, series_id: str, asset_id: str, kind: str, locks: dict) -> tuple[dict, object]:
    row = db.one(
        """SELECT id,series_id,kind,version,specification_json FROM series_assets
           WHERE id=? AND series_id=? AND kind=?""",
        (asset_id, series_id, kind),
    )
    pin = locks.get(asset_id)
    if (row is None or type(pin) is not dict
            or set(pin) != {"version", "specification_sha256"}
            or type(pin["version"]) is not int or pin["version"] < 1
            or row["version"] != pin["version"]):
        raise ShotAssetBindingError("Unknown, foreign or unpinned asset version")
    _digest(pin["specification_sha256"])
    body = row["specification_json"]
    if not isinstance(body, str) or _sha(body) != pin["specification_sha256"]:
        raise ShotAssetBindingError("Asset specification SHA mismatch")
    klass = {"actor": ActorBible, "scene": SceneBible, "voice": VoiceBible}[kind]
    try:
        spec = klass.model_validate_json(body)
    except ValueError:
        raise ShotAssetBindingError("Invalid asset specification") from None
    return {
        "asset_id": asset_id, "kind": kind, "version": row["version"],
        "source_kind": "series_asset_specification_json",
        "specification_sha256": pin["specification_sha256"],
    }, spec


def build_bound_screenplay_video_plan(
    db, screenplay: Screenplay, context: ScriptContext, *,
    style_prompt: str, style_version: str, source_response_sha256: str,
    locked_assets: dict[str, dict], shot_ids: list[str] | None = None,
    source_episode_report_sha256: str | None = None,
    shot_appearance_anchors: dict[str, dict[str, str]] | None = None,
) -> dict:
    """Bind every declared actor/scene/voice to an explicit current DB version+SHA.

    The original planner and its prompt are retained as a *prior* SHA; the
    returned request previews are OFFLINE only. A pinned historical manifest
    remains auditable, but stale DB versions cannot be silently replayed.
    """
    _digest(source_response_sha256)
    _digest(source_episode_report_sha256, optional=True)
    if type(style_version) is not str or not style_version.strip():
        raise ShotAssetBindingError("Style version must be explicit")
    if type(locked_assets) is not dict:
        raise ShotAssetBindingError("Explicit asset version pins required")
    if (screenplay.series_id != context.series_id
            or screenplay.story_bible_id != context.story_bible_id):
        raise ShotAssetBindingError("Story scope mismatch")
    # Existing production validator: do not duplicate series/actor/scene rules.
    check_screenplay_scope(db, screenplay)
    bible = db.one(
        "SELECT id,version,body_json FROM story_bibles WHERE id=? AND series_id=?",
        (screenplay.story_bible_id, screenplay.series_id),
    )
    if (bible is None or type(bible["version"]) is not int
            or bible["version"] < 1 or not isinstance(bible["body_json"], str)):
        raise ShotAssetBindingError("Story Bible version missing")
    try:
        StoryBible.model_validate_json(bible["body_json"])
    except ValueError:
        raise ShotAssetBindingError("Invalid Story Bible version") from None

    actor_ids = set(a for shot in screenplay.shots for a in shot.character_ids)
    scene_ids = set(shot.scene_id for shot in screenplay.shots if shot.scene_id)
    entries: dict[str, dict] = {}
    actors: dict[str, ActorBible] = {}
    scenes: dict[str, SceneBible] = {}
    for actor_id in sorted(actor_ids):
        entries[actor_id], actor = _asset(db, screenplay.series_id, actor_id, "actor", locked_assets)
        if (not actor.appearance.strip() or not actor.identity_anchors
                or any(not anchor.strip() for anchor in actor.identity_anchors)
                or not actor.costume_notes.strip()):
            raise ShotAssetBindingError("Actor appearance or costume anchor missing")
        actors[actor_id] = actor
    for scene_id in sorted(scene_ids):
        entries[scene_id], scenes[scene_id] = _asset(
            db, screenplay.series_id, scene_id, "scene", locked_assets,
        )
    voice_ids = {actor.voice_asset_id for actor in actors.values() if actor.voice_asset_id}
    for voice_id in sorted(voice_ids):
        if voice_id in entries:
            raise ShotAssetBindingError("Voice asset ID reused for another kind")
        entries[voice_id], _ = _asset(db, screenplay.series_id, voice_id, "voice", locked_assets)
    if set(locked_assets) != set(entries):
        raise ShotAssetBindingError("Extraneous or missing asset version pins")

    descriptions = {
        actor_id: (
            f"{actor.appearance}；身份锚点：{'；'.join(actor.identity_anchors)}"
            f"；固定服装：{actor.costume_notes}"
        ) for actor_id, actor in actors.items()
    }
    # Existing renderer validates timing/selection/visible actors and computes
    # its original SHA. The old return contract remains unchanged.
    old_plan = build_screenplay_video_plan(
        screenplay, context, style_prompt=style_prompt,
        actor_descriptions=descriptions, shot_ids=shot_ids,
    )
    selected = set(old_plan["selected_shot_ids"])
    if shot_appearance_anchors is not None:
        if (type(shot_appearance_anchors) is not dict
                or set(shot_appearance_anchors) != selected):
            raise ShotAssetBindingError("Appearance pins must match selected shots")
        for shot in screenplay.shots:
            if shot.shot_id not in selected:
                continue
            pins = shot_appearance_anchors[shot.shot_id]
            if (type(pins) is not dict or set(pins) != set(shot.character_ids)
                    or any(type(pins[a]) is not str or pins[a] != actors[a].appearance
                           for a in shot.character_ids)):
                raise ShotAssetBindingError("Conflicting shot appearance anchor")

    bindings = []
    for shot in screenplay.shots:
        if shot.shot_id not in selected:
            continue
        cast = []
        for actor_id in shot.character_ids:
            actor = actors[actor_id]
            cast.append({
                **entries[actor_id],
                "appearance_anchor": actor.appearance,
                "identity_anchors": list(actor.identity_anchors),
                "costume_notes": actor.costume_notes,
                # ActorBible currently stores costume in this same asset spec,
                # not in a separate wardrobe-version schema.
                "costume_version": entries[actor_id]["version"],
                "costume_version_source": "actor_asset_version",
                "voice_asset": entries.get(actor.voice_asset_id),
            })
        scene = (
            {**entries[shot.scene_id],
             "name": scenes[shot.scene_id].name,
             "location": scenes[shot.scene_id].location,
             "layout": scenes[shot.scene_id].layout}
            if shot.scene_id else None
        )
        bindings.append({
            "shot_id": shot.shot_id, "character_ids": list(shot.character_ids),
            "characters": cast, "scene_id": shot.scene_id, "scene_asset": scene,
            "speaker_cues": [{
                "speaker_actor_id": cue.speaker_actor_id,
                "expected_dialogue": cue.text,
                "start_second": cue.start_second, "end_second": cue.end_second,
            } for cue in shot.dialogue],
            "reference_mode": "prompt_anchor_only",
            "provider_reference_applied": False,
        })
    manifest = {
        "schema_version": SCHEMA, "series_id": screenplay.series_id,
        "story_bible_id": screenplay.story_bible_id,
        "story_bible_version": bible["version"],
        "story_bible_sha256": _sha(bible["body_json"]),
        "screenplay_sha256": old_plan["screenplay_sha256"],
        "source_response_sha256": source_response_sha256,
        "source_episode_report_sha256": source_episode_report_sha256,
        "style_version": style_version, "style_sha256": _sha(style_prompt),
        "selected_shot_ids": old_plan["selected_shot_ids"],
        "shots": bindings,
        "reference_images_supported": False, "audio_reference_supported": False,
        "provider_reference_applied": False, "production_assets_verified": False,
        "paid_execution_authorized": False, "publish_approved": False,
        "new_paid_model_calls": 0,
    }
    manifest_sha = _sha(canonical_json(manifest))
    by_id = {row["shot_id"]: row for row in bindings}
    for entry in old_plan["shots"]:
        original = entry["prompt"]
        bound = by_id[entry["shot_id"]]
        suffix = canonical_json({
            "asset_binding": bound, "style_version": style_version,
            "source_response_sha256": source_response_sha256,
        })
        updated = original + "\n固定版本的镜头绑定数据（仅提示词；未向模型传入参考媒体）：\n" + suffix
        if len(updated) > 9000:
            raise ShotAssetBindingError("Bound prompt exceeds OmniVideoSpec limit")
        entry["prior_prompt_sha256"] = entry["prompt_sha256"]
        entry["prompt"] = updated
        entry["prompt_sha256"] = _sha(updated)
        entry["request_preview"]["input"] = updated
        entry["asset_binding"] = bound
        entry["manifest_sha256"] = manifest_sha
        entry["provider_reference_applied"] = False
    return {"manifest": manifest, "manifest_sha256": manifest_sha, "plan": old_plan}
