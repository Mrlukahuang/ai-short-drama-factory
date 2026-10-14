"""Human-reviewed screenplay contract and deterministic EpisodeDraft conversion."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..models import EpisodeDraft, ShotDraft, ApprovedDialogueCue

SCRIPT_SCHEMA_VERSION = "screenplay.zh.v1"


class DialogueCue(BaseModel):
    speaker_actor_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=500)


class ScreenplayShot(BaseModel):
    shot_id: str = Field(min_length=1, max_length=80)
    duration_seconds: int = Field(ge=1, le=30)
    action: str = Field(min_length=1, max_length=4000)
    camera: str = Field(min_length=1, max_length=500)
    character_ids: list[str] = Field(default_factory=list, max_length=8)
    scene_id: str | None = None
    dialogue: list[DialogueCue] = Field(default_factory=list)
    continuity_start: str = Field(min_length=1, max_length=2000)
    continuity_end: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def dialogue_matches_visible_cast(self):
        if len(self.character_ids) != len(set(self.character_ids)):
            raise ValueError("Duplicate actor in a shot")
        if any(line.speaker_actor_id not in self.character_ids for line in self.dialogue):
            raise ValueError("All dialogue speakers must be listed in shot character_ids")
        return self


class Screenplay(BaseModel):
    schema_version: Literal["screenplay.zh.v1"] = SCRIPT_SCHEMA_VERSION
    series_id: str = Field(min_length=1)
    story_bible_id: str = Field(min_length=1)
    episode_number: int = Field(ge=1)
    episode_title: str = Field(min_length=1, max_length=200)
    target_duration_seconds: int = Field(ge=1, le=3600)
    shots: list[ScreenplayShot] = Field(min_length=1, max_length=500)
    hook: str = Field(default="", max_length=2000)
    ending_cliffhanger: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_edit_timeline(self):
        ids = [shot.shot_id for shot in self.shots]
        if len(ids) != len(set(ids)):
            raise ValueError("shot_id must be unique")
        actual = sum(shot.duration_seconds for shot in self.shots)
        if actual != self.target_duration_seconds:
            raise ValueError(
                f"Timeline duration mismatch: shots total {actual}s, "
                f"target {self.target_duration_seconds}s"
            )
        return self

    def to_episode_draft(self) -> EpisodeDraft:
        return EpisodeDraft(
            title=self.episode_title,
            episode_number=self.episode_number,
            target_duration_seconds=self.target_duration_seconds,
            shots=[
                ShotDraft(
                    shot_id=shot.shot_id,
                    duration_seconds=shot.duration_seconds,
                    visual_description=f"[摄影: {shot.camera}] {shot.action}",
                    character_ids=shot.character_ids,
                    scene_id=shot.scene_id,
                    dialogue=[f"{line.speaker_actor_id}: {line.text}" for line in shot.dialogue],
                    dialogue_cues=[
                        ApprovedDialogueCue(
                            speaker_actor_id=line.speaker_actor_id,
                            text=line.text,
                        ) for line in shot.dialogue
                    ],
                    audio_mode="locked_voice" if shot.dialogue else "silent",
                )
                for shot in self.shots
            ],
        )


class ReviewedScreenplay(BaseModel):
    screenplay: Screenplay
    reviewed_by_operator: Literal[True]
    # This is explicit manual acceptance of reviewed JSON, not automatic model approval.


class ScreenplayReferenceError(ValueError):
    pass


def check_screenplay_scope(db, screenplay: Screenplay) -> None:
    """Fail closed when Bible, actors or scenes belong to another series."""
    if db.one("SELECT id FROM projects WHERE id=?", (screenplay.series_id,)) is None:
        raise ScreenplayReferenceError("Unknown series")
    bible = db.one(
        "SELECT id FROM story_bibles WHERE id=? AND series_id=?",
        (screenplay.story_bible_id, screenplay.series_id),
    )
    if bible is None:
        raise ScreenplayReferenceError("Story Bible belongs to another series or does not exist")
    checked = set()
    for shot in screenplay.shots:
        refs = [(actor, "actor") for actor in shot.character_ids]
        if shot.scene_id:
            refs.append((shot.scene_id, "scene"))
        for asset_id, kind in refs:
            if (asset_id, kind) in checked:
                continue
            row = db.one(
                "SELECT id FROM series_assets WHERE id=? AND series_id=? AND kind=?",
                (asset_id, screenplay.series_id, kind),
            )
            if row is None:
                raise ScreenplayReferenceError(f"Invalid {kind} reference: {asset_id}")
            checked.add((asset_id, kind))
