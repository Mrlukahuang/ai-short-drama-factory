"""G4/R4.1 pure wire adapters and offline budget preflight; NO transport.

No SDK, credentials, environment lookup, database, retries or approval mutation.
This is not an implementation of the legacy outline-returning TextProvider.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json

from .screenplay import Screenplay
from .text import ScriptContext, ScriptPlanRequest, build_drama_writer_prompt

MODELS = ("gpt-6.1-sol", "gpt-6-luna", "gemini-3.8-flash")
# Standard, uncached USD / million. No discount assumptions; no tools permitted.
RATES = {MODELS[0]: ("2", "10"), MODELS[1]: ("0.10", "0.50"),
         MODELS[2]: ("0.75", "3.75")}
RATE_START, RATE_EXPIRY = date(2026, 10, 17), date(2026, 10, 31)
TOTAL_LIMIT = Decimal("2.00")


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _hash(value) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _integer(value, minimum=0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError("Expected nonnegative integer token count")
    return value


def _rates(model: str, on: date) -> tuple[Decimal, Decimal]:
    if model not in MODELS or not RATE_START <= on <= RATE_EXPIRY:
        raise ValueError("Unsupported model or stale price snapshot; reverify pricing")
    return tuple(Decimal(v) for v in RATES[model])


def strict_screenplay_schema() -> dict:
    """Common semantic schema; nullable optionals become required nullable fields.

    Defaults/titles are removed, objects closed. Constraints and refs preserved.
    Provider acceptance remains unverified until separately authorized API test.
    """
    def visit(value):
        if isinstance(value, list):
            return [visit(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {k: visit(v) for k, v in value.items() if k not in ("default", "title")}
        if result.get("type") == "object":
            result["additionalProperties"] = False
            result["required"] = list(result.get("properties", {}))
        return result
    return visit(Screenplay.model_json_schema())


@dataclass(frozen=True)
class PreparedWriterRequest:
    model: str
    endpoint: str
    payload_json: str
    request_json: str
    context_json: str
    max_output_tokens: int

    @property
    def fingerprint(self) -> str:
        return _hash(self.__dict__)


def prepare_request(model: str, request: ScriptPlanRequest, context: ScriptContext,
                    max_output_tokens: int = 12000) -> PreparedWriterRequest:
    if model not in MODELS:
        raise ValueError("Model is not a comparison candidate")
    _integer(max_output_tokens, 1)
    if max_output_tokens > 32000:
        raise ValueError("Comparison output cap exceeds 32000")
    prompt = build_drama_writer_prompt(request, context)["prompt"]
    schema = strict_screenplay_schema()
    common = {"model": model, "store": False, "stream": False}
    if model.startswith("gpt-"):
        endpoint = "https://api.openai.com/v1/responses"
        body = {**common, "service_tier": "default",
                "input": [{"role": "user", "content": prompt}],
                "reasoning": {"effort": "medium"}, "max_output_tokens": max_output_tokens,
                "text": {"format": {"type": "json_schema", "name": "screenplay_zh_v1",
                                    "strict": True, "schema": schema}}}
    else:
        endpoint = "https://generativelanguage.googleapis.com/v1beta/interactions"
        body = {**common, "service_tier": "standard", "input": prompt,
                "generation_config": {"thinking_level": "medium",
                                      "max_output_tokens": max_output_tokens},
                "response_format": {"type": "text", "mime_type": "application/json",
                                    "schema": schema}}
    return PreparedWriterRequest(model, endpoint, _json(body), request.model_dump_json(),
                                 context.model_dump_json(), max_output_tokens)


def _closed_shape(value, schema: dict, root: dict) -> None:
    if "$ref" in schema:
        schema = root["$defs"][schema["$ref"].split("/")[-1]]
    if "anyOf" in schema:
        branches = schema["anyOf"]
        if value is None and any(b.get("type") == "null" for b in branches):
            return
        schema = next(b for b in branches if b.get("type") != "null")
    if schema.get("type") == "object":
        props = schema["properties"]
        if not isinstance(value, dict) or set(value) != set(props):
            raise ValueError("Missing or extra screenplay fields")
        for key, child in props.items():
            _closed_shape(value[key], child, root)
    elif schema.get("type") == "array":
        if not isinstance(value, list):
            raise ValueError("Expected screenplay array")
        for item in value:
            _closed_shape(item, schema["items"], root)


def _screenplay(text: str, prepared: PreparedWriterRequest) -> Screenplay:
    raw = json.loads(text)
    schema = strict_screenplay_schema()
    _closed_shape(raw, schema, schema)
    result = Screenplay.model_validate_json(text, strict=True)
    request = ScriptPlanRequest.model_validate_json(prepared.request_json)
    context = ScriptContext.model_validate_json(prepared.context_json)
    expected = {"series_id": context.series_id, "story_bible_id": context.story_bible_id,
                "episode_number": request.episode_number,
                "target_duration_seconds": request.target_duration_seconds}
    if any(getattr(result, k) != v for k, v in expected.items()):
        raise ValueError("Screenplay scope mismatch")
    if not result.hook.strip() or not result.ending_cliffhanger.strip():
        raise ValueError("Blank hook or cliffhanger")
    visible = set()
    for shot in result.shots:
        visible.update(shot.character_ids)
        if (not set(shot.character_ids).issubset(set(request.actor_asset_ids))
                or shot.scene_id != request.scene_asset_id
                or not 3 <= shot.duration_seconds <= 10
                or not shot.continuity_start.strip() or not shot.continuity_end.strip()):
            raise ValueError("Shot scope, duration or continuity field mismatch")
    if visible != set(request.actor_asset_ids):
        raise ValueError("Both selected leads must appear")
    return result


@dataclass(frozen=True)
class UsageReceipt:
    input_tokens: int
    output_tokens: int  # visible only
    thinking_tokens: int
    billable_output_tokens: int
    estimated_usd: str  # list-price estimate, NOT invoice / actual charge


def usage_receipt(model: str, usage: dict, on: date) -> UsageReceipt:
    input_rate, output_rate = _rates(model, on)
    if model.startswith("gpt-"):
        inp = _integer(usage["input_tokens"])
        billed = _integer(usage["output_tokens"])
        thought = _integer(usage["output_tokens_details"]["reasoning_tokens"])
        if thought > billed:
            raise ValueError("Thinking subset exceeds total output")
        visible = billed - thought
    else:
        inp = _integer(usage["total_input_tokens"])
        visible = _integer(usage["total_output_tokens"])
        thought = _integer(usage["total_thought_tokens"])
        billed = visible + thought
        if usage.get("total_tool_use_tokens", 0) != 0:
            raise ValueError("Tool usage outside text-only price assumptions")
    if inp > 272000:
        raise ValueError("Long-context pricing outside this snapshot")
    cost = (inp * input_rate + billed * output_rate) / Decimal(1000000)
    return UsageReceipt(inp, visible, thought, billed, str(cost))


@dataclass(frozen=True)
class WriterResult:
    status: str
    screenplay: Screenplay | None
    usage: UsageReceipt | None
    usage_status: str
    response_id: str | None
    request_sha256: str
    response_sha256: str
    simulated: bool
    approval_granted: bool = False


def parse_response(prepared: PreparedWriterRequest, response: dict, *, on: date,
                   simulated: bool = True) -> WriterResult:
    """Normalize supplied JSON only; never repairs, continues or resends.

    Errors expose categories, not provider messages / fiction text. Missing usage
    remains unknown (not free), even when refused or truncated.
    """
    if not isinstance(response, dict):
        raise ValueError("Response must be one JSON object")
    receipt = None
    try:
        allowed_tiers = (None, "default") if prepared.model.startswith("gpt-") else (None, "standard")
        if response.get("model") != prepared.model or response.get("service_tier") not in allowed_tiers:
            raise ValueError("Unverified response model or pricing tier")
        receipt = usage_receipt(prepared.model, response["usage"], on)
    except (KeyError, TypeError, ValueError):
        pass
    status, text = "malformed_response", ""
    try:
        if response.get("model") != prepared.model:
            raise ValueError("Response model mismatch")
        state = response.get("status")
        if state == "incomplete":
            status = "truncated"
        elif state != "completed" or response.get("error") or response.get("errors"):
            status = "provider_failed"
        elif prepared.model.startswith("gpt-"):
            pieces, refused = [], False
            for item in response["output"]:
                if item["type"] == "reasoning":
                    continue
                if item["type"] != "message" or item.get("status") != "completed":
                    raise ValueError("Unexpected output item")
                for part in item["content"]:
                    if part["type"] == "refusal":
                        refused = True
                    elif part["type"] == "output_text":
                        pieces.append(part["text"])
                    else:
                        raise ValueError("Unexpected content")
            status, text = ("refused" if refused else "candidate"), "".join(pieces)
        else:
            # Current Interactions wire shape: steps/model_output/content.
            # A schema change must fail closed, not scrape arbitrary text fields.
            pieces = []
            for step in response["steps"]:
                if step["type"] in ("thought", "user_input"):
                    continue
                if step["type"] != "model_output":
                    raise ValueError("Unexpected interaction step")
                for part in step["content"]:
                    if part["type"] != "text":
                        raise ValueError("Unexpected output modality")
                    pieces.append(part["text"])
            status, text = "candidate", "".join(pieces)
    except (KeyError, TypeError, ValueError):
        status = "malformed_response"
    screenplay = None
    if status == "candidate":
        try:
            screenplay = _screenplay(text, prepared)
            status = "validated_draft"
        except (KeyError, TypeError, ValueError, StopIteration):
            status = "invalid_screenplay"
    return WriterResult(status, screenplay, receipt,
                        "reported" if receipt is not None else "unknown",
                        response.get("id"), prepared.fingerprint, _hash(response), simulated)


@dataclass(frozen=True)
class TokenUpperBound:
    request_sha256: str
    input_tokens: int
    billable_output_tokens: int
    evidence: str  # source / counting method; not a credential
    verified: bool = False


def preflight_batch(jobs: list[tuple[str, PreparedWriterRequest, TokenUpperBound]], *,
                    on: date, already_spent_usd: str = "0") -> dict:
    """All-or-nothing <=$2 arithmetic gate for exactly 18 identified tasks.

    Bounds must cover serialized schema/system overhead AND thinking. No token
    heuristic is promoted to verified evidence. This function cannot authorize
    or send requests; a future transport must enforce these reservations.
    """
    spent = Decimal(already_spent_usd)
    if not spent.is_finite() or spent < 0:
        raise ValueError("Invalid spend")
    if len(jobs) != 18 or len({j[0] for j in jobs}) != 18:
        raise ValueError("Expected 18 unique task IDs")
    expected = {(case, model, repeat) for case in (
        "misunderstanding", "reversal", "prop_continuity")
                for model in MODELS for repeat in (1, 2)}
    actual, reserves, case_sources, repeats = set(), [], {}, {}
    for job_id, prepared, bound in jobs:
        case, model, repeat = job_id.split("/")
        actual.add((case, model, int(repeat)))
        if model != prepared.model or bound.request_sha256 != prepared.fingerprint:
            raise ValueError("Budget evidence/request mismatch")
        canonical = prepare_request(model,
            ScriptPlanRequest.model_validate_json(prepared.request_json),
            ScriptContext.model_validate_json(prepared.context_json), prepared.max_output_tokens)
        if canonical != prepared:
            raise ValueError("Prepared payload mutated outside the wire adapter")
        source = _hash([json.loads(prepared.request_json), json.loads(prepared.context_json)])
        if case in case_sources and case_sources[case] != source:
            raise ValueError("Models must receive identical semantic case inputs")
        case_sources[case] = source
        key = case, model
        if key in repeats and repeats[key] != prepared.fingerprint:
            raise ValueError("Replicates must use identical requests")
        repeats[key] = prepared.fingerprint
        if bound.verified is not True or not bound.evidence.strip():
            raise ValueError("Verified input + thinking-inclusive output bounds required")
        inp, out = _integer(bound.input_tokens, 1), _integer(bound.billable_output_tokens, 1)
        if inp > 272000:
            raise ValueError("Input upper bound requires long-context price verification")
        if out < prepared.max_output_tokens:
            raise ValueError("Output bound below request cap")
        ri, ro = _rates(model, on)
        reserves.append((inp * ri + out * ro) / Decimal(1000000))
    if actual != expected:
        raise ValueError("Batch differs from fixed 3x3x2 comparison")
    if len(set(case_sources.values())) != 3:
        raise ValueError("Three distinct test cases required")
    total = spent + sum(reserves, Decimal(0))
    if total > TOTAL_LIMIT:
        raise ValueError("18-task worst-case total exceeds USD2 hard preflight limit")
    return {"budget_preflight_pass": True, "reserved_usd": str(total),
            "limit_usd": str(TOTAL_LIMIT), "execution_authorized": False,
            "transport_available": False, "price_snapshot_expires": str(RATE_EXPIRY)}


def reconcile_usage(prepared: PreparedWriterRequest, bound: TokenUpperBound,
                    result: WriterResult) -> dict:
    """Offline receipt check. Unknown charge retains the full reservation.

    No automatic refund, retry or next-call permission is derived from failure.
    This is an audit record, not a persistent production spending ledger.
    """
    if bound.request_sha256 != prepared.fingerprint or result.request_sha256 != prepared.fingerprint:
        raise ValueError("Receipt and reservation must match the exact request")
    usage = result.usage
    breach = usage is not None and (
        usage.input_tokens > bound.input_tokens
        or usage.billable_output_tokens > bound.billable_output_tokens)
    return {"request_sha256": prepared.fingerprint, "response_sha256": result.response_sha256,
            "simulated": result.simulated, "result_status": result.status,
            "usage_status": result.usage_status,
            "list_price_estimate_usd": usage.estimated_usd if usage else None,
            "retain_full_reservation": usage is None or breach,
            "bound_breached": breach, "halt_required": usage is None or breach,
            "retry_authorized": False, "actual_invoice_verified": False}


def execute_paid(*args, **kwargs):
    raise RuntimeError("Paid transport absent; this module is OFFLINE ONLY")
