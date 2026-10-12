"""One-shot Gemini Omni video adapter. Disabled by default and never used by HTTP API."""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
import time
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from drama_factory.pipeline.media_ingest import inspect_source

MODEL_ID = "gemini-omni-1.1-flash"


class VideoCallDisabled(RuntimeError):
    pass


class InvalidVideoResponse(RuntimeError):
    pass


class OmniVideoSpec(BaseModel):
    model_id: Literal["gemini-omni-1.1-flash"] = MODEL_ID
    prompt: str = Field(min_length=1, max_length=9000)
    aspect_ratio: Literal["9:16"] = "9:16"
    resolution: Literal["360p", "720p"] = "360p"
    min_duration_seconds: int = Field(default=3, ge=3, le=10)
    maximum_acknowledged_spend_usd: Decimal = Field(gt=0)
    operator_approved: bool = False


class FakeOmniVideoProvider:
    def generate(self, spec: OmniVideoSpec, destination: Path) -> dict:
        return {
            "model": spec.model_id, "is_mock": True, "model_calls": 0,
            "media_path": None, "source_sha256": None,
        }


class GoogleOmniVideoProvider:
    """Exactly one generate request; bounded poll/download, never resubmit.

    maximum_acknowledged_spend_usd is an acknowledgement, NOT a provider billing cap.
    """

    def __init__(self, client=None, poll_interval: float = 5.0, max_polls: int = 60):
        self._client = client
        self.poll_interval = poll_interval
        self.max_polls = max_polls

    def generate(self, spec: OmniVideoSpec, destination: Path) -> dict:
        if os.getenv("DRAMA_ENABLE_PAID_GENERATION") != "YES":
            raise VideoCallDisabled("Paid Google video generation disabled")
        if not spec.operator_approved:
            raise VideoCallDisabled("Operator must approve the individual paid request")
        client = self._client
        if client is None:
            key = os.getenv("GEMINI_API_KEY")
            if not key:
                raise VideoCallDisabled("GEMINI_API_KEY missing")
            try:
                from google import genai
            except ImportError as exc:
                raise VideoCallDisabled("Install optional google-image dependency") from exc
            client = genai.Client(api_key=key)
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise InvalidVideoResponse("Refusing to overwrite an existing video output")
        # The official Interactions video URI mode avoids the ~4MB inline limit.
        interaction = client.interactions.create(
            model=spec.model_id,
            input=spec.prompt,
            response_format={
                "type": "video", "aspect_ratio": spec.aspect_ratio,
                "resolution": spec.resolution, "delivery": "uri",
            },
        )
        video = getattr(interaction, "output_video", None)
        if video is None:
            raise InvalidVideoResponse("Omni returned no video object")
        delivery = "uri"
        try:
            uri = getattr(video, "uri", None)
            if uri:
                file_id = str(uri).split("?")[0].rsplit("/", 1)[-1]
                if not re.fullmatch(r"[a-zA-Z0-9_-]+", file_id):
                    raise InvalidVideoResponse("Invalid Google video file URI")
                for _ in range(self.max_polls):
                    file_info = client.files.get(name=f"files/{file_id}")
                    state = getattr(file_info, "state", None)
                    state_name = getattr(state, "name", str(state)).upper()
                    if state_name == "ACTIVE":
                        break
                    if state_name == "FAILED":
                        raise InvalidVideoResponse("Google video file failed processing")
                    if self.poll_interval:
                        time.sleep(self.poll_interval)
                else:
                    raise InvalidVideoResponse("Google video processing poll timed out")
                client.files.download(file=uri, destination=str(dest))
            else:
                delivery = "inline"
                data = getattr(video, "data", None)
                if not isinstance(data, str):
                    raise InvalidVideoResponse("Omni response has neither URI nor inline video")
                try:
                    raw = base64.b64decode(data, validate=True)
                except binascii.Error as exc:
                    raise InvalidVideoResponse("Invalid inline Base64 video") from exc
                if len(raw) > 200 * 1024 * 1024:
                    raise InvalidVideoResponse("Oversized inline video")
                dest.write_bytes(raw)
            media = inspect_source(dest, spec.min_duration_seconds)
            return {
                "model": spec.model_id, "is_mock": False, "model_calls": 1,
                "media_path": str(dest), "source_sha256": media["sha256"],
                "source_duration_seconds": media["duration"], "delivery": delivery,
            }
        except Exception:
            dest.unlink(missing_ok=True)
            raise
