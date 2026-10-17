"""Offline GPT response → pending human review; no transport or persistence."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .text import ScriptContext, ScriptPlanRequest
from .writer_execution_prep import parse_response, prepare_request


class GPTScreenplayImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Development baseline only, not a formal provider-selection change.
    model: Literal["gpt-6.1-sol", "gpt-6-luna"] = "gpt-6.1-sol"
    request: ScriptPlanRequest
    response: dict
    response_date: date


def prepare_gpt_review(body: GPTScreenplayImport, context: ScriptContext) -> dict:
    """Validate supplied output against current context, never assert provenance.

    Reconstructed request hashes describe the current validation input. They do
    not establish what a provider actually received. Supplied JSON is untrusted.
    """
    prepared = prepare_request(body.model, body.request, context)
    parsed = parse_response(prepared, body.response, on=body.response_date, simulated=False)
    if parsed.status != "validated_draft" or parsed.screenplay is None:
        raise ValueError(f"GPT response rejected: {parsed.status}")
    screenplay = parsed.screenplay
    usage = None
    if parsed.usage:
        # The old parser estimate does not account for cache writes. Do not
        # propagate it as a complete cost estimate or an actual invoice.
        usage = {k: getattr(parsed.usage, k) for k in (
            "input_tokens", "output_tokens", "thinking_tokens", "billable_output_tokens")}
    return {
        "status": "pending_human_review", "model": body.model,
        "source": "operator_supplied_openai_response",
        "response_authenticity_verified": False,
        "original_request_binding_verified": False,
        "reconstructed_request_sha256": parsed.request_sha256,
        "response_sha256": parsed.response_sha256, "response_id": parsed.response_id,
        "screenplay": screenplay.model_dump(mode="json"),
        "episode_draft": screenplay.to_episode_draft().model_dump(mode="json"),
        "usage_tokens": usage, "usage_status": parsed.usage_status,
        "estimated_usd": None, "actual_invoice_verified": False,
        "cost_status": "pending_cache_aware_pricing",
        "review_required": True, "approval_granted": False,
        "episodes_created": 0, "production_created": False, "paid_api_calls": 0,
    }
