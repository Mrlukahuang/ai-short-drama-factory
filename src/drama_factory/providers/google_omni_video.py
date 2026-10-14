"""One-shot Gemini Omni video adapter. Disabled by default and never used by HTTP API."""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import time
from urllib.parse import urlsplit
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from drama_factory.pipeline.media_ingest import inspect_source
from drama_factory.providers.video_provider import VideoRequest, VideoResult

MODEL_ID = "gemini-omni-1.1-flash"


class VideoCallDisabled(RuntimeError):
    pass


class InvalidVideoResponse(RuntimeError):
    pass


_GOOGLE_FILES_HOST = "generativelanguage.googleapis.com"
_FILE_PATH = re.compile(
    r"(?:/v1beta/)?files/([A-Za-z0-9_-]{1,200})(?::download)?"
)


def parse_google_video_file_id(uri: str) -> str:
    """Parse Google's Files API download URLs without confusing ':download' for an ID.

    Accepts official HTTPS Files URLs and relative 'files/id' names only.
    Rejects other hosts, credentials, ports, fragments, path tricks and unknown routes.
    Never log/persist the original query string, which could be sensitive.
    """
    if not isinstance(uri, str):
        raise InvalidVideoResponse("Google video URI must be text")
    parsed = urlsplit(uri)
    if parsed.scheme or parsed.netloc:
        if (
            parsed.scheme != "https" or parsed.hostname != _GOOGLE_FILES_HOST
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.fragment
        ):
            raise InvalidVideoResponse("Untrusted Google video file URL")
    else:
        if parsed.fragment or uri.startswith("//"):
            raise InvalidVideoResponse("Invalid relative Google file name")
    match = _FILE_PATH.fullmatch(parsed.path)
    if not match:
        raise InvalidVideoResponse("Invalid Google video file URI")
    return match.group(1)


def google_video_download_uri(file_id: str) -> str:
    """Reconstruct a provider URL only from a previously validated bare file ID."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", file_id):
        raise InvalidVideoResponse("Invalid Google file ID")
    return (
        f"https://{_GOOGLE_FILES_HOST}/v1beta/files/{file_id}"
        ":download?alt=media"
    )


class OmniVideoSpec(BaseModel):
    model_id: Literal["gemini-omni-1.1-flash"] = MODEL_ID
    prompt: str = Field(min_length=1, max_length=9000)
    aspect_ratio: Literal["9:16"] = "9:16"
    resolution: Literal["360p", "720p"] = "360p"
    min_duration_seconds: int = Field(default=3, ge=3, le=10)
    maximum_acknowledged_spend_usd: Decimal = Field(gt=0)
    operator_approved: bool = False


def _omni_legacy_spec(request: VideoRequest) -> OmniVideoSpec:
    """Validate G1 common fields BEFORE any provider/network side effects.

    The current Google Interactions request is prompt-only and 9:16. It does
    not actually send reference images or an audio reference, nor can it
    guarantee an exact output duration: min_duration_seconds is a floor.
    """
    if request.reference_images:
        raise VideoCallDisabled("Omni reference image inputs not implemented")
    if request.audio_reference is not None:
        raise VideoCallDisabled("Omni does not support uploaded audio references")
    if request.aspect_ratio != "9:16":
        raise VideoCallDisabled("Omni adapter currently supports 9:16 only")
    if not 3 <= request.duration_seconds <= 10:
        raise VideoCallDisabled("Omni supports a requested duration floor of 3–10s")
    return OmniVideoSpec(
        prompt=request.prompt,
        aspect_ratio=request.aspect_ratio,
        min_duration_seconds=request.duration_seconds,
        maximum_acknowledged_spend_usd=request.maximum_acknowledged_spend_usd,
        operator_approved=request.operator_approved,
    )


class FakeOmniVideoProvider:
    def generate(self, spec: OmniVideoSpec, destination: Path) -> dict:
        return {
            "model": spec.model_id, "is_mock": True, "model_calls": 0,
            "media_path": None, "source_sha256": None,
        }

    def generate_video(self, request: VideoRequest, destination: Path) -> VideoResult:
        spec = _omni_legacy_spec(request)
        receipt = self.generate(spec, destination)
        return VideoResult(
            model_id=spec.model_id, mp4_path=None, task_id=None,
            actual_fee_usd=None, is_mock=True, model_calls=receipt["model_calls"],
        )


class GoogleOmniVideoProvider:
    """Exactly one generate request; bounded poll/download, never resubmit.

    maximum_acknowledged_spend_usd is an acknowledgement, NOT a provider billing cap.
    """

    def __init__(self, client=None, poll_interval: float = 5.0, max_polls: int = 60):
        self._client = client
        self.poll_interval = poll_interval
        self.max_polls = max_polls

    def _client_or_raise(self):
        if self._client is not None:
            return self._client
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise VideoCallDisabled("GEMINI_API_KEY missing")
        try:
            from google import genai
        except ImportError as exc:
            raise VideoCallDisabled("Install optional google-video dependency") from exc
        return genai.Client(api_key=key)

    def _download_file(
        self, client, file_id: str, download_uri: str,
        destination: Path, min_duration_seconds: int,
    ) -> dict:
        """Only poll and download an existing file. Never generate a new video."""
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise InvalidVideoResponse("Refusing to overwrite an existing video output")
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
        try:
            client.files.download(file=download_uri, destination=str(dest))
            media = inspect_source(dest, min_duration_seconds)
        except Exception:
            dest.unlink(missing_ok=True)
            raise
        return {
            "model": MODEL_ID, "is_mock": False, "model_calls": 0,
            "media_path": str(dest), "source_sha256": media["sha256"],
            "source_duration_seconds": media["duration"], "delivery": "uri",
        }

    def recover_existing(
        self, file_id: str, destination: Path, *,
        operator_approved: bool = False,
        min_duration_seconds: int = 2,
    ) -> dict:
        """Restore already-generated bytes, without a new model generation request."""
        if not operator_approved:
            raise VideoCallDisabled("Explicit operator approval required to recover media")
        download_uri = google_video_download_uri(file_id)
        client = self._client_or_raise()
        receipt = self._download_file(
            client, file_id, download_uri, Path(destination), min_duration_seconds,
        )
        receipt["recovered_existing"] = True
        return receipt

    def generate(self, spec: OmniVideoSpec, destination: Path) -> dict:
        if os.getenv("DRAMA_ENABLE_PAID_GENERATION") != "YES":
            raise VideoCallDisabled("Paid Google video generation disabled")
        if not spec.operator_approved:
            raise VideoCallDisabled("Operator must approve the individual paid request")
        client = self._client_or_raise()
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
        task_id = getattr(interaction, "id", None)
        if not isinstance(task_id, str) or not (1 <= len(task_id) <= 256):
            task_id = None  # Do not fabricate a provider task ID.
        video = getattr(interaction, "output_video", None)
        if video is None:
            raise InvalidVideoResponse("Omni returned no video object")
        delivery = "uri"
        try:
            uri = getattr(video, "uri", None)
            if uri:
                file_id = parse_google_video_file_id(str(uri))
                # Save only a validated ID for a download-only recovery later.
                # The full provider URL/query and user API key are never persisted.
                receipt_path = dest.with_suffix(".recovery.json")
                receipt_path.write_text(
                    json.dumps({
                        "version": 1, "model": spec.model_id,
                        "file_id": file_id, "generation_submitted": True,
                        "recovery_only": True,
                    }, sort_keys=True), encoding="utf-8",
                )
                info = self._download_file(
                    client, file_id, str(uri), dest, spec.min_duration_seconds,
                )
                info["model_calls"] = 1
                info["provider_task_id"] = task_id
                info["recovered_existing"] = False
                info["recovery_metadata_path"] = str(receipt_path)
                return info
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
                "recovered_existing": False,
                "provider_task_id": task_id,
            }
        except Exception:
            dest.unlink(missing_ok=True)
            raise


    def generate_video(self, request: VideoRequest, destination: Path) -> VideoResult:
        """G1 common protocol, delegating to the existing one-call Omni path.

        An SDK interaction ID is returned only if the SDK actually exposed it.
        No Omni receipt currently carries a verified invoice charge, so the
        actual fee remains None rather than using an assumed per-second price.
        """
        spec = _omni_legacy_spec(request)
        receipt = self.generate(spec, destination)
        if receipt["is_mock"] or receipt["model_calls"] != 1 or not receipt["media_path"]:
            raise InvalidVideoResponse("Real Omni provider returned no real video")
        return VideoResult(
            model_id=spec.model_id,
            mp4_path=Path(receipt["media_path"]),
            task_id=receipt.get("provider_task_id"),
            actual_fee_usd=None,
            is_mock=False, model_calls=receipt["model_calls"],
        )
