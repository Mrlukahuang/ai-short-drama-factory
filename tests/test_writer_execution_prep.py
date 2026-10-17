"""Synthetic wire fixtures; no credentials, SDKs or paid calls."""
from dataclasses import replace
from datetime import date
from decimal import Decimal
import importlib.util
import json
from pathlib import Path

import pytest

from drama_factory.pipeline.writer_execution_prep import (
    MODELS, TokenUpperBound, execute_paid, parse_response, preflight_batch,
    prepare_request, reconcile_usage, strict_screenplay_schema, usage_receipt,
)

spec = importlib.util.spec_from_file_location(
    "comparison_fixture", Path(__file__).resolve().parents[1]
    / "scripts/prepare_writer_comparison.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
TODAY = date(2026, 10, 17)


def prepared(model=MODELS[0], case="misunderstanding"):
    return prepare_request(model, *fixture.case_inputs(case))


def screenplay():
    return {
        "schema_version": "screenplay.zh.v1", "series_id": "comparison-fixture",
        "story_bible_id": "comparison-bible", "episode_number": 1,
        "episode_title": "合成测试，不是编剧实测", "target_duration_seconds": 60,
        "hook": "占位钩子", "ending_cliffhanger": "占位悬念",
        "shots": [{"shot_id": str(i), "duration_seconds": 10,
                   "action": "结构占位", "camera": "固定",
                   "character_ids": ["a-jie", "xiao-yu"], "scene_id": "cafe",
                   "dialogue": [{"speaker_actor_id": "a-jie", "text": "你好",
                                 "start_second": None, "end_second": None}],
                   "continuity_start": "占位", "continuity_end": "占位"}
                  for i in range(6)]}


def response(model=MODELS[0]):
    base = {"id": "synthetic-response", "model": model, "status": "completed"}
    text = json.dumps(screenplay(), ensure_ascii=False)
    if model.startswith("gpt-"):
        return {**base, "usage": {"input_tokens": 1000, "output_tokens": 600,
                                  "output_tokens_details": {"reasoning_tokens": 100}},
                "output": [{"type": "message", "status": "completed",
                            "content": [{"type": "output_text", "text": text}]}]}
    return {**base, "usage": {"total_input_tokens": 1000, "total_output_tokens": 500,
                              "total_thought_tokens": 100},
            "steps": [{"type": "thought", "summary": []},
                      {"type": "model_output", "content": [{"type": "text", "text": text}]}]}


@pytest.mark.parametrize("model", MODELS)
def test_request_response_contract_without_network(model, monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden")
    monkeypatch.setattr(socket, "socket", forbidden)
    req = prepared(model)
    body = json.loads(req.payload_json)
    assert body["model"] == model
    assert body["store"] is body["stream"] is False
    assert "tools" not in body
    schema = (body["text"]["format"]["schema"] if model.startswith("gpt-")
              else body["response_format"]["schema"])
    assert schema == strict_screenplay_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    result = parse_response(req, response(model), on=TODAY)
    assert result.status == "validated_draft"
    assert result.screenplay.to_episode_draft().target_duration_seconds == 60
    assert result.usage.billable_output_tokens == 600
    assert result.usage.output_tokens == 500
    assert result.simulated is True and result.approval_granted is False
    with pytest.raises(RuntimeError, match="OFFLINE ONLY"):
        execute_paid(req, authorized=True)


def test_usage_math_does_not_double_count_openai_thinking():
    sol = usage_receipt(MODELS[0], response()["usage"], TODAY)
    flash = usage_receipt(MODELS[2], response(MODELS[2])["usage"], TODAY)
    assert sol.estimated_usd == "0.008"
    assert flash.estimated_usd == "0.003"


@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("state,expected", [("incomplete", "truncated"),
    ("failed", "provider_failed"), ("in_progress", "provider_failed")])
def test_noncompleted_never_accepts_even_valid_json(model, state, expected):
    raw = response(model)
    raw["status"] = state
    result = parse_response(prepared(model), raw, on=TODAY)
    assert result.status == expected and result.screenplay is None
    assert result.usage is not None  # Failure is not assumed free.


def test_refusal_and_missing_usage_are_not_approved_or_free():
    raw = response()
    raw["output"][0]["content"] = [{"type": "refusal", "refusal": "synthetic refusal"}]
    del raw["usage"]
    result = parse_response(prepared(), raw, on=TODAY)
    assert result.status == "refused"
    assert result.usage is None and result.usage_status == "unknown"
    assert result.screenplay is None and result.approval_granted is False


@pytest.mark.parametrize("mutate", ["extra", "missing", "scope", "duration", "speaker", "string_int"])
def test_rejects_schema_and_semantic_scope_errors(mutate):
    script = screenplay()
    if mutate == "extra": script["shots"][0]["unapproved"] = True
    if mutate == "missing": del script["hook"]
    if mutate == "scope": script["series_id"] = "other"
    if mutate == "duration": script["shots"][0]["duration_seconds"] = 9
    if mutate == "speaker": script["shots"][0]["dialogue"][0]["speaker_actor_id"] = "other"
    if mutate == "string_int": script["episode_number"] = "1"
    raw = response()
    raw["output"][0]["content"][0]["text"] = json.dumps(script)
    result = parse_response(prepared(), raw, on=TODAY)
    assert result.status == "invalid_screenplay" and result.screenplay is None


@pytest.mark.parametrize("kind", ["json", "wrong_model", "tool", "missing_steps"])
def test_google_unrecognized_or_refusal_text_fails_closed(kind):
    raw = response(MODELS[2])
    if kind == "json": raw["steps"][1]["content"][0]["text"] = "I cannot comply"
    if kind == "wrong_model": raw["model"] = "unverified-model"
    if kind == "tool": raw["steps"].append({"type": "google_search_call"})
    if kind == "missing_steps": del raw["steps"]
    result = parse_response(prepared(MODELS[2]), raw, on=TODAY)
    assert result.status in ("invalid_screenplay", "malformed_response")
    assert result.screenplay is None


def jobs():
    result = []
    for case, _ in fixture.CASES:
        for model in MODELS:
            req = prepared(model, case)
            for repeat in (1, 2):
                bound = TokenUpperBound(req.fingerprint, 10000, 12000,
                                        "SIMULATED bound for offline arithmetic", True)
                result.append((f"{case}/{model}/{repeat}", req, bound))
    return result


def test_batch_exact_boundary_and_no_execution_authority():
    result = preflight_batch(jobs(), on=TODAY, already_spent_usd="0.803")
    assert Decimal(result["reserved_usd"]) == Decimal("2")
    assert result["execution_authorized"] is result["transport_available"] is False
    with pytest.raises(ValueError, match="exceeds"):
        preflight_batch(jobs(), on=TODAY, already_spent_usd="0.803001")


@pytest.mark.parametrize("kind", ["missing", "duplicate", "unverified", "stale_hash",
    "negative", "bool", "small_output", "expensive", "wrong_model", "long_input"])
def test_budget_gate_rejects_unbounded_or_mismatched_plan(kind):
    batch = jobs()
    job, req, bound = batch[0]
    if kind == "missing": batch.pop()
    if kind == "duplicate": batch[1] = batch[0]
    if kind == "unverified": bound = replace(bound, verified=False)
    if kind == "stale_hash": bound = replace(bound, request_sha256="0" * 64)
    if kind == "negative": bound = replace(bound, input_tokens=-1)
    if kind == "bool": bound = replace(bound, input_tokens=True)
    if kind == "small_output": bound = replace(bound, billable_output_tokens=11999)
    if kind == "expensive": bound = replace(bound, billable_output_tokens=500000)
    if kind == "wrong_model": job = job.replace(MODELS[0], MODELS[1])
    if kind == "long_input": bound = replace(bound, input_tokens=272001)
    if kind not in ("missing", "duplicate"): batch[0] = job, req, bound
    with pytest.raises(ValueError):
        preflight_batch(batch, on=TODAY)


def test_stale_rates_and_missing_thought_usage_remain_unknown():
    with pytest.raises(ValueError, match="stale"):
        preflight_batch(jobs(), on=date(2026, 11, 1))
    raw = response(MODELS[2])
    del raw["usage"]["total_thought_tokens"]
    result = parse_response(prepared(MODELS[2]), raw, on=TODAY)
    assert result.usage_status == "unknown" and result.usage is None


def test_unknown_and_breached_receipts_preserve_reservation_and_halt():
    req = prepared()
    bound = TokenUpperBound(req.fingerprint, 100, 100, "synthetic", True)
    result = parse_response(req, response(), on=TODAY)
    audit = reconcile_usage(req, bound, result)
    assert audit["bound_breached"] and audit["halt_required"]
    raw = response()
    del raw["usage"]
    audit = reconcile_usage(req, bound, parse_response(req, raw, on=TODAY))
    assert audit["retain_full_reservation"] and audit["halt_required"]
    assert audit["list_price_estimate_usd"] is None
    assert audit["retry_authorized"] is False


def test_preflight_rejects_mutated_wire_and_unfair_inputs():
    batch = jobs()
    job, req, bound = batch[0]
    body = json.loads(req.payload_json)
    body["tools"] = [{"type": "web_search"}]
    changed = replace(req, payload_json=json.dumps(body))
    batch[0] = job, changed, replace(bound, request_sha256=changed.fingerprint)
    with pytest.raises(ValueError, match="mutated"):
        preflight_batch(batch, on=TODAY)
    batch = jobs()
    job, req, bound = batch[2]
    changed = prepared(MODELS[1], "reversal")
    batch[2] = job, changed, replace(bound, request_sha256=changed.fingerprint)
    with pytest.raises(ValueError, match="identical semantic"):
        preflight_batch(batch, on=TODAY)


def test_wire_cli_exports_18_pending_payloads_without_transport(tmp_path, monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline CLI must not open sockets")
    monkeypatch.setattr(socket, "socket", forbidden)
    out = tmp_path / "wire.json"
    assert fixture.main(["--out", str(out), "--wire-requests"]) == 0
    result = json.loads(out.read_text())
    assert len(result["wire_requests"]) == 18
    assert result["execution_authorized"] is result["transport_available"] is False
    assert result["model_calls"] == 0
    assert all(row["budget_bound_status"] == "missing_verified_evidence"
               for row in result["wire_requests"])


def test_unverified_response_model_or_service_tier_cannot_claim_known_cost():
    for field, value in (("model", "other"), ("service_tier", "ultrafast")):
        raw = response()
        raw[field] = value
        result = parse_response(prepared(), raw, on=TODAY)
        assert result.usage is None and result.usage_status == "unknown"
