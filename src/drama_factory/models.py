from __future__ import annotations
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class VisualStyle(StrEnum):
    LIVE_ACTION = "live_action"
    ANIME_2D = "anime_2d"
    ANIMATION_3D = "animation_3d"

class RightsStatus(StrEnum):
    OWNED = "owned"
    LICENSED = "licensed"
    PENDING = "pending"

class ProductionState(StrEnum):
    SCRIPT_REVIEW = "script_review_pending"
    CHARACTER_REVIEW = "character_review_pending"
    VIDEO_READY = "ready_for_video_generation"
    MOCK_FINISHED = "mock_finished"

class OriginalProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    premise: str = Field(min_length=1, max_length=20000)
    visual_style: VisualStyle = VisualStyle.LIVE_ACTION
    default_ratio: Literal["9:16", "16:9"] = "9:16"
    column_id: str | None = None  # Legacy callers are placed in the default column.

class ShotDraft(BaseModel):
    shot_id: str = Field(min_length=1, max_length=80)
    duration_seconds: int = Field(ge=1, le=30)
    visual_description: str = Field(min_length=1)
    character_ids: list[str] = Field(default_factory=list)
    scene_id: str | None = None
    dialogue: list[str] = Field(default_factory=list)
    reference_asset_ids: list[str] = Field(default_factory=list)
    video_model: str = "gemini-omni-1.1-flash"
    audio_mode: Literal["native", "locked_voice", "silent"] = "native"

class EpisodeDraft(BaseModel):
    title: str = Field(min_length=1)
    episode_number: int = Field(ge=1)
    target_duration_seconds: int = Field(ge=1, le=3600)
    shots: list[ShotDraft] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_shot_ids(self):
        ids = [s.shot_id for s in self.shots]
        if len(ids) != len(set(ids)):
            raise ValueError("shot_id must be unique per episode")
        return self

class AdaptationRequest(BaseModel):
    desired_episodes: int = Field(ge=1, le=300)
    target_seconds_per_episode: int = Field(ge=30, le=1800)
    visual_style: VisualStyle = VisualStyle.LIVE_ACTION
    adaptation_notes: str = Field(default="", max_length=10000)
    # This is planning only in v0.1. No copyrighted text is sent to third parties.

# Multi-column / series contracts. A v0.1 "project" is a Series, preserving legacy routes.
class ColumnCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=60, pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    default_visual_style: VisualStyle = VisualStyle.LIVE_ACTION


class AssetKind(StrEnum):
    ACTOR = "actor"
    SCENE = "scene"
    VOICE = "voice"
    PROP = "prop"


class ActorBible(BaseModel):
    name: str = Field(min_length=1)
    appearance: str = Field(min_length=1)
    identity_anchors: list[str] = Field(min_length=1)
    personality: str = ""
    costume_notes: str = ""
    voice_asset_id: str | None = None


class SceneBible(BaseModel):
    name: str = Field(min_length=1)
    location: str = Field(min_length=1)
    layout: str = Field(min_length=1)
    lighting: str = ""
    continuity_notes: str = ""


class VoiceBible(BaseModel):
    name: str = Field(min_length=1)
    voice_description: str = Field(min_length=1)
    source_consent_reference: str = ""


class PropBible(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class AssetCreate(BaseModel):
    kind: AssetKind
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    specification: dict

    @model_validator(mode="after")
    def validate_specification(self):
        schema = {AssetKind.ACTOR: ActorBible, AssetKind.SCENE: SceneBible,
                  AssetKind.VOICE: VoiceBible, AssetKind.PROP: PropBible}[self.kind]
        self.specification = schema.model_validate(self.specification).model_dump(mode="json")
        return self


class StoryBible(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    logline: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    canon: str = ""
    relationship_notes: str = ""