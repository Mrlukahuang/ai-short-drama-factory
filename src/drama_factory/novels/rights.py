"""Versioned human rights review metadata. This is not legal advice or authenticated authorization."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RightsReviewCreate(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer_label: str = Field(min_length=2, max_length=120)
    rights_holder: str = Field(min_length=2, max_length=200)
    evidence_reference: str = Field(min_length=2, max_length=500)
    valid_from: date
    valid_until: date
    territories: list[str] = Field(min_length=1, max_length=50)
    languages: list[str] = Field(min_length=1, max_length=30)
    media_types: list[Literal["short_drama", "animation", "film", "series"]] = Field(min_length=1)
    allow_external_ai: bool = False
    notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def check_review_window(self):
        if self.valid_until < self.valid_from:
            raise ValueError("Rights end date precedes start date")
        for field_name in ("territories", "languages", "media_types"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate values in {field_name}")
        if any(not x or len(x) > 30 for x in self.territories + self.languages):
            raise ValueError("Territory and language codes must have 1..30 characters")
        return self


class RightsEligibility(BaseModel):
    eligible: bool
    reason: str
    active_review_version: int | None = None
    external_model_calls_enabled: bool = False  # Always false in current offline factory


def evaluate_eligibility(
    source: dict,
    latest_review: dict | None,
    territory: str,
    language: str,
    media_type: str,
    external_ai: bool,
    as_of: date | None = None,
) -> RightsEligibility:
    """Only an explicit, unexpired and in-scope latest approved review can pass."""
    if source["rights_status"] == "pending":
        return RightsEligibility(eligible=False, reason="Rights status is pending")
    if "screen_adaptation" not in [x.strip() for x in source["rights_scope"].split(",")]:
        return RightsEligibility(eligible=False, reason="Missing screen_adaptation grant")
    if source["rights_status"] == "licensed" and not source["rights_reference"].strip():
        return RightsEligibility(eligible=False, reason="Missing license evidence")
    if latest_review is None:
        return RightsEligibility(eligible=False, reason="No human rights review")
    version = latest_review["version"]
    data = RightsReviewCreate.model_validate_json(latest_review["review_json"])
    if data.decision != "approved":
        return RightsEligibility(
            eligible=False, reason="Latest review rejected the rights",
            active_review_version=version,
        )
    today = as_of or date.today()
    if not data.valid_from <= today <= data.valid_until:
        return RightsEligibility(
            eligible=False, reason="Rights review is outside validity dates",
            active_review_version=version,
        )
    if (
        territory not in data.territories
        or language not in data.languages
        or media_type not in data.media_types
    ):
        return RightsEligibility(
            eligible=False, reason="Requested territory, language or medium not granted",
            active_review_version=version,
        )
    if external_ai and not data.allow_external_ai:
        return RightsEligibility(
            eligible=False, reason="Third-party AI processing not granted",
            active_review_version=version,
        )
    # Pure assessment result. A future model worker must additionally check app operator
    # authentication, provider-specific transfer restrictions, a budget gate and an allow flag.
    return RightsEligibility(
        eligible=True, reason="Reviewed scope matches; no model call was made",
        active_review_version=version, external_model_calls_enabled=False,
    )
