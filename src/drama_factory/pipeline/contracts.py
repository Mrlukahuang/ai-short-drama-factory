"""Provider-neutral shot generation contracts. No actual model is called here."""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator


class ShotJobState(StrEnum):
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AssetVersionRef(BaseModel):
    asset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class ShotGenerationSpec(BaseModel):
    project_id: str = Field(min_length=1)
    episode_id: str = Field(min_length=1)
    shot_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    duration_seconds: int = Field(ge=1, le=30)
    ratio: Literal["9:16", "16:9"] = "9:16"
    asset_refs: list[AssetVersionRef] = Field(default_factory=list)
    resolution: Literal["360p", "720p", "1080p", "4k"] = "720p"
    seed: int | None = None
    # Scheduling/billing policy, deliberately excluded from the content cache fingerprint.
    budget_usd: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def unique_asset_versions(self):
        ids = [a.asset_id for a in self.asset_refs]
        if len(ids) != len(set(ids)):
            raise ValueError("Each asset_id may appear at most once per shot")
        return self

    def idempotency_key(self) -> str:
        """Stable fingerprint of user-approved inputs, not of mutable output states."""
        normalized = self.model_dump(mode="json", exclude={"budget_usd"})
        normalized["asset_refs"] = sorted(normalized["asset_refs"], key=lambda x: x["asset_id"])
        blob = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class GenerationReceipt(BaseModel):
    idempotency_key: str
    provider: str
    model_id: str
    provider_task_id: str | None = None
    state: ShotJobState
    media_uri: str | None = None
    actual_cost_usd: Decimal | None = Field(default=None, ge=0)
    error: str | None = None


class VideoProvider(Protocol):
    """Real providers will implement submit, poll, and fetch as separate steps."""
    def submit(self, request: ShotGenerationSpec) -> GenerationReceipt: ...
    def poll(self, task_id: str) -> GenerationReceipt: ...
    def fetch(self, receipt: GenerationReceipt) -> bytes: ...
