"""G1 video-provider request/receipt contract (no network or billing behavior).

A receipt's actual_cost_usd is None until verified from a provider invoice.
A mock result never claims an MP4, task ID, or measured spend.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class VideoRequest(BaseModel):
    """Provider-neutral intent; provider adapters must reject unsupported inputs."""

    prompt: str = Field(min_length=1, max_length=9000)
    reference_images: tuple[str, ...] = ()
    audio_reference: str | None = None
    duration_seconds: int = Field(ge=3, le=30)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    operator_approved: bool = False
    maximum_acknowledged_spend_usd: Decimal | None = Field(default=None, gt=0)


class VideoReceipt(BaseModel):
    """No inferred cost or fabricated provider task identifier."""

    model_id: str = Field(min_length=1)
    mp4_path: str | None = None
    provider_task_id: str | None = None
    actual_cost_usd: Decimal | None = Field(default=None, ge=0)
    is_mock: bool


@runtime_checkable
class VideoProvider(Protocol):
    def generate_video(self, request: VideoRequest, destination: Path) -> VideoReceipt:
        """Return a typed receipt; real adapters retain their independent paid gates."""
        ...
