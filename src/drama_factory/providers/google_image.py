"""Guarded Google Nano Banana 2.1 image adapter. Never invoked by HTTP API."""
from __future__ import annotations

import base64
import binascii
import hashlib
import os
from io import BytesIO
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

MODEL_ID = "gemini-nano-banana-2.1"
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
JPEG_SIGNATURE = b"\xff\xd8\xff"
JPEG_EOI = b"\xff\xd9"


class ImageCallDisabled(RuntimeError):
    pass


class InvalidImageResponse(RuntimeError):
    pass


class GoogleImageSpec(BaseModel):
    series_id: str = Field(min_length=1)
    actor_asset_id: str = Field(min_length=1)
    model_id: Literal["gemini-nano-banana-2.1"] = MODEL_ID
    prompt_version: Literal["actor-portrait.zh.v1"] = "actor-portrait.zh.v1"
    prompt: str = Field(min_length=1, max_length=10000)
    aspect_ratio: Literal["1:1", "9:16", "16:9"] = "9:16"
    image_size: Literal["1K", "2K"] = "1K"
    # Explicitly an operator acknowledgement, NOT a hard API billing limit.
    maximum_acknowledged_spend_usd: Decimal = Field(gt=0)
    operator_approved: bool = False
    reference_id: str | None = None


@dataclass(frozen=True)
class GeneratedImage:
    model_id: str
    sha256: str | None
    jpeg_bytes: bytes | None
    is_mock: bool
    paid_model_calls: int


def require_actor(db, spec: GoogleImageSpec):
    row = db.one(
        "SELECT id FROM series_assets WHERE id=? AND series_id=? AND kind='actor'",
        (spec.actor_asset_id, spec.series_id),
    )
    if row is None:
        raise ValueError("Actor must belong to the selected series")
    if spec.reference_id is not None:
        # PR-07 registers reference metadata, not the referenced bytes.
        raise ValueError("Image-to-image needs approved binary storage; not implemented yet")


class FakeGoogleImageProvider:
    def generate(self, db, spec: GoogleImageSpec) -> GeneratedImage:
        require_actor(db, spec)
        return GeneratedImage(spec.model_id, None, None, True, 0)


class GoogleImageProvider:
    """Requires operator acknowledgement AND an opt-in environment gate.

    Real billing can exceed local estimates: this version has no supplier-side
    hard cap or retries, and should only be manually invoked for one test image.
    """

    def __init__(self, client=None):
        self._client = client

    def generate(self, db, spec: GoogleImageSpec) -> GeneratedImage:
        require_actor(db, spec)
        if os.getenv("DRAMA_ENABLE_PAID_GENERATION") != "YES":
            raise ImageCallDisabled("Paid model disabled; use FakeGoogleImageProvider")
        if not spec.operator_approved:
            raise ImageCallDisabled("Explicit operator approval is required")
        client = self._client
        if client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ImageCallDisabled("GEMINI_API_KEY is missing")
            try:
                from google import genai
            except ImportError as exc:
                raise ImageCallDisabled(
                    "Install the optional google-image dependency first"
                ) from exc
            client = genai.Client(api_key=api_key)
        # This is the documented Gemini Interactions API, not legacy Imagen.
        interaction = client.interactions.create(
            model=spec.model_id,
            input=spec.prompt,
            response_format={
                "type": "image",
                "mime_type": "image/jpeg",
                "aspect_ratio": spec.aspect_ratio,
                "image_size": spec.image_size,
            },
        )
        output = getattr(interaction, "output_image", None)
        if output is None or not getattr(output, "data", None):
            raise InvalidImageResponse("Gemini returned no image; do not save a fake result")
        try:
            encoded = output.data
            if not isinstance(encoded, str):
                raise InvalidImageResponse("Image data must be base64 text")
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise InvalidImageResponse("Malformed base64 image") from exc
        if (
            len(raw) > MAX_OUTPUT_BYTES or not raw.startswith(JPEG_SIGNATURE)
            or not raw.endswith(JPEG_EOI)
        ):
            raise InvalidImageResponse("Image is too large or not a complete JPEG")
        # Only declare a paid result successful after actually decoding the image.
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(BytesIO(raw)) as picture:
                if picture.format != "JPEG":
                    raise InvalidImageResponse("Expected JPEG image from Gemini")
                picture.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise InvalidImageResponse("Gemini returned an undecodable JPEG") from exc
        return GeneratedImage(
            model_id=spec.model_id, sha256=hashlib.sha256(raw).hexdigest(),
            jpeg_bytes=raw, is_mock=False, paid_model_calls=1,
        )
