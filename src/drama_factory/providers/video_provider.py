"""G1/R1.3 shared, offline-testable interface for video providers.

Only Google Omni has an implementation in this requirement. Seedance/Kling
implementations belong to R1.1/R1.2. A missing provider task ID or unverified
actual charge MUST stay None; never substitute an estimate for a real bill.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class VideoRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=9000)
    reference_images: tuple[Path, ...] = ()
    audio_reference: Path | None = None
    duration_seconds: int = Field(ge=3, le=30)
    aspect_ratio: Literal["9:16", "16:9"] = "9:16"
    # Acknowledgement is NOT an API-side hard spending limit.
    maximum_acknowledged_spend_usd: Decimal = Field(gt=0)
    operator_approved: bool = False


class VideoResult(BaseModel):
    model_id: str
    mp4_path: Path | None = None
    task_id: str | None = None
    # Null means the actual provider charge has NOT been independently verified.
    actual_fee_usd: Decimal | None = Field(default=None, ge=0)
    is_mock: bool
    model_calls: int = Field(ge=0)


@runtime_checkable
class VideoProvider(Protocol):
    def generate_video(self, request: VideoRequest, destination: Path) -> VideoResult:
        """Generate one clip (or Fake result) with no implicit retry."""
        ...
