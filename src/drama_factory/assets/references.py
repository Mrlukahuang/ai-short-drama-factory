"""Immutable reference media metadata for series-bound actors, sets and voices."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

MEDIA_TO_ASSET_KIND = {
    "face_reference": "actor",
    "wardrobe_reference": "actor",
    "scene_reference": "scene",
    "style_frame": "scene",
    "voice_sample": "voice",
    "prop_reference": "prop",
}


class ReferenceCreate(BaseModel):
    media_kind: Literal[
        "face_reference", "wardrobe_reference", "scene_reference",
        "style_frame", "voice_sample", "prop_reference",
    ]
    storage_key: str = Field(min_length=5, max_length=500, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    provenance: Literal["synthetic", "user_owned", "licensed_person"]
    rights_reference: str = Field(min_length=2, max_length=500)
    consent_reference: str = Field(default="", max_length=500)
    model_id: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def safety_invariants(self):
        if self.storage_key.startswith("/") or any(
            segment in ("", ".", "..") for segment in self.storage_key.split("/")
        ):
            raise ValueError("storage_key must be a relative, normalized object key")
        if self.provenance == "licensed_person" and not self.consent_reference.strip():
            raise ValueError("Reference to a real person's likeness or voice requires consent")
        if self.provenance == "synthetic" and not self.model_id.strip():
            raise ValueError("Synthetic media must record the model ID")
        return self


class ApproveReference(BaseModel):
    reviewed_by_operator: Literal[True]
    reviewer_label: str = Field(min_length=2, max_length=120)
