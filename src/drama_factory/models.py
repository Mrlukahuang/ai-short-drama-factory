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
