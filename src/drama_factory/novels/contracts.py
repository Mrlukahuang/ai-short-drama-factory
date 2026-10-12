"""Novel-to-season planning contracts. Pure validation; no third-party AI processing."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

NOVEL_SCHEMA_VERSION = "novel-blueprint.zh.v1"


class NovelSource(BaseModel):
    source_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chapter_count: int = Field(ge=1)
    # Rights records live in the database, not in an editable blueprint.


class SourceSpan(BaseModel):
    source_id: str = Field(min_length=1)
    chapter_ordinal: int = Field(ge=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    # No original text/long quotation is duplicated into planning metadata.

    @model_validator(mode="after")
    def check_range(self):
        if self.end_offset <= self.start_offset:
            raise ValueError("SourceSpan end_offset must exceed start_offset")
        return self


class CharacterMention(BaseModel):
    mention_id: str = Field(min_length=1)
    name_in_source: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1500)
    source_spans: list[SourceSpan] = Field(min_length=1)


class PlotEvent(BaseModel):
    event_id: str = Field(min_length=1)
    order: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=5000)
    character_mention_ids: list[str] = Field(default_factory=list)
    source_spans: list[SourceSpan] = Field(min_length=1)
    caused_by_event_ids: list[str] = Field(default_factory=list)
    story_time: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    dramatic_function: Literal["setup", "escalation", "reversal", "payoff", "resolution"] = "setup"


class SeasonEpisodePlan(BaseModel):
    episode_number: int = Field(ge=1)
    working_title: str = Field(min_length=1)
    target_seconds: int = Field(ge=30, le=1800)
    plot_event_ids: list[str] = Field(min_length=1)
    hook: str = Field(min_length=1)
    cliffhanger: str = Field(min_length=1)

    @model_validator(mode="after")
    def unique_events(self):
        if len(self.plot_event_ids) != len(set(self.plot_event_ids)):
            raise ValueError("An event may not appear twice in one planned episode")
        return self


class SeasonPlan(BaseModel):
    target_episode_count: int = Field(ge=1, le=300)
    episodes: list[SeasonEpisodePlan] = Field(min_length=1)


class NovelAdaptationBlueprint(BaseModel):
    schema_version: Literal["novel-blueprint.zh.v1"] = NOVEL_SCHEMA_VERSION
    source: NovelSource
    characters: list[CharacterMention] = Field(default_factory=list)
    events: list[PlotEvent] = Field(min_length=1)
    season: SeasonPlan
    adaptation_principles: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent_references(self):
        source_id = self.source.source_id
        mentions = [c.mention_id for c in self.characters]
        event_ids = [e.event_id for e in self.events]
        if len(mentions) != len(set(mentions)):
            raise ValueError("Duplicate character mention IDs")
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("Duplicate event IDs")
        if [e.order for e in self.events] != list(range(1, len(self.events) + 1)):
            raise ValueError("Plot events must be in contiguous ordinal order")
        known_characters = set(mentions)
        known_prior_events = set()
        for event in self.events:
            if not set(event.character_mention_ids).issubset(known_characters):
                raise ValueError("Event references unknown character mention")
            if not set(event.caused_by_event_ids).issubset(known_prior_events):
                raise ValueError("Causal predecessors must be earlier events")
            known_prior_events.add(event.event_id)
        if self.season.target_episode_count != len(self.season.episodes):
            raise ValueError("Season plan count must match number of episodes")
        if [e.episode_number for e in self.season.episodes] != list(
            range(1, len(self.season.episodes) + 1)
        ):
            raise ValueError("Season episodes must be in contiguous order")
        if any(
            not set(episode.plot_event_ids).issubset(set(event_ids))
            for episode in self.season.episodes
        ):
            raise ValueError("Episode references unknown PlotEvent")
        for item in [*self.characters, *self.events]:
            for span in item.source_spans:
                if span.source_id != source_id:
                    raise ValueError("Span references another novel source")
                if span.chapter_ordinal > self.source.chapter_count:
                    raise ValueError("Span chapter exceeds declared chapter count")
        return self


class NovelIndexMismatch(ValueError):
    pass


def validate_blueprint_against_index(db, blueprint: NovelAdaptationBlueprint) -> None:
    """Check actual uploaded source hash and absolute character offsets against chapter index."""
    novel = db.one(
        "SELECT id,sha256,chapter_count FROM novel_sources WHERE id=?",
        (blueprint.source.source_id,),
    )
    if novel is None:
        raise NovelIndexMismatch("Unknown novel")
    if (
        novel["sha256"] != blueprint.source.source_sha256
        or novel["chapter_count"] != blueprint.source.chapter_count
    ):
        raise NovelIndexMismatch("Source hash or chapter count changed")
    chapters = db.many(
        "SELECT ordinal,start_offset,end_offset FROM novel_chapters WHERE source_id=?",
        (blueprint.source.source_id,),
    )
    index = {ch["ordinal"]: ch for ch in chapters}
    for item in [*blueprint.characters, *blueprint.events]:
        for span in item.source_spans:
            chapter = index.get(span.chapter_ordinal)
            if chapter is None:
                raise NovelIndexMismatch("Unknown chapter ordinal")
            if (
                span.start_offset < chapter["start_offset"]
                or span.end_offset > chapter["end_offset"]
            ):
                raise NovelIndexMismatch("SourceSpan lies outside indexed chapter boundaries")
