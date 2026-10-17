"""Synthetic providers only. Real network forbidden, no media claims."""
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_gpt_video_three as runner
sys.path.pop(0)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("Network forbidden"))
    class Clock:
        @staticmethod
        def now(tz): return datetime(2026, 10, 18, tzinfo=tz)
        @staticmethod
        def __new__(cls, *args): return datetime(*args)
    monkeypatch.setattr(runner, "datetime", Clock)


def plan():
    return {"source_response_sha256": runner.SOURCE_HASH,
        "selected_shot_ids": ["s01", "s02", "s03"],
        "shots": [{"shot_id": f"s0{i}", "prompt": "合成测试台词", "prompt_sha256": "a" * 64}
                  for i in range(1, 4)]}


def env():
    return {"GITHUB_REPOSITORY": runner.REPO, "GITHUB_ACTOR": "Mrlukahuang",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "123", "GITHUB_SHA": "synthetic",
        "VIDEO_CONFIRM": runner.CONFIRM, "ACK_ESTIMATE_NOT_CAP": "YES",
        "DRAMA_ENABLE_PAID_GENERATION": "YES", "GEMINI_API_KEY": "private-synthetic",
        "GITHUB_TOKEN": "private-synthetic"}


def dependencies(calls, *, failure=None, claimed=False):
    def post(url, key, body, **kwargs):
        calls.append("claim_read" if body is None else "claim_write")
        return ([{"body": runner.MARKER}] if claimed else []) if body is None else {"id": 1}
    class Provider:
        def generate(self, spec, path):
            calls.append("generate")
            if failure == "timeout": raise TimeoutError("private")
            path.write_bytes(b"SYNTHETIC_NOT_VIDEO")
            return {"is_mock": failure == "fake", "model_calls": 1, "provider_task_id": "synthetic"}
    media = SimpleNamespace(probe=lambda p: {"duration": 11 if failure == "duration" else 5,
        "has_audio": failure != "audio"}, is_portrait=lambda p: failure != "landscape")
    return dict(post=post, make_provider=lambda key: Provider(), get_media=lambda: media)


def test_exactly_three_attempts_claimed_first_and_no_invoice_claim(tmp_path):
    calls = []
    report = runner.run_live(plan(), tmp_path / "ok", "0", env=env(), **dependencies(calls))
    assert calls == ["claim_read", "claim_write", "generate", "generate", "generate"]
    assert report["status"] == "three_clips_completed_pending_human_review"
    assert report["generation_attempts"] == 3 and report["claim_recorded"]
    assert report["budget"]["budget_upper_bound_verified"] is False
    assert report["actual_fee_usd"] is None and report["publish_approved"] is False


@pytest.mark.parametrize("failure", ["timeout", "fake", "duration", "audio", "landscape"])
def test_failure_halts_after_one_attempt_without_releasing_claim(tmp_path, failure):
    calls = []
    with pytest.raises(RuntimeError):
        runner.run_live(plan(), tmp_path / failure, "0", env=env(), **dependencies(calls, failure=failure))
    report = json.loads((tmp_path / failure / "report.json").read_text())
    assert calls.count("generate") == 1
    assert report["claim_recorded"] and report["status"] == "halted_no_retry"
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize("field,value", [("ACK_ESTIMATE_NOT_CAP", ""), ("GITHUB_RUN_ATTEMPT", "2"),
    ("GITHUB_ACTOR", "other"), ("GITHUB_REF", "refs/heads/other"), ("GEMINI_API_KEY", "")])
def test_guard_denies_before_claim_or_generation(tmp_path, field, value):
    calls = []
    values = env(); values[field] = value
    with pytest.raises(RuntimeError):
        runner.run_live(plan(), tmp_path / "deny", "0", env=values, **dependencies(calls))
    assert not calls


def test_claim_is_not_reused_or_reset(tmp_path):
    calls = []
    with pytest.raises(RuntimeError):
        runner.run_live(plan(), tmp_path / "claimed", "0", env=env(), **dependencies(calls, claimed=True))
    assert calls == ["claim_read"]


@pytest.mark.parametrize("spend", ["nan", "-1", "3.01", "4"])
def test_daily_spend_denied(spend):
    with pytest.raises(ValueError): runner.estimate_budget(plan(), spend, date(2026, 10, 18))


def test_budget_is_explicit_estimate_not_hard_limit():
    budget = runner.estimate_budget(plan(), "3", date(2026, 10, 18))
    assert Decimal(budget["estimated_total_usd"]) < 2
    assert budget["provider_billing_cap"] is budget["budget_upper_bound_verified"] is False
    with pytest.raises(ValueError): runner.estimate_budget(plan(), "0", date(2026, 11, 1))


def test_modified_source_denied_before_any_paid_request(tmp_path):
    (tmp_path / "gpt-6.1-sol.response.json").write_text('{}')
    with pytest.raises(ValueError, match="approved source"):
        runner.load_plan(tmp_path)


def test_sdk_generation_retries_are_disabled(monkeypatch):
    import drama_factory.providers.google_omni_video as provider_module
    calls = []
    class FakeClient:
        def __init__(self, **kwargs): calls.append(kwargs)
    monkeypatch.setitem(sys.modules, "google", SimpleNamespace(genai=SimpleNamespace(Client=FakeClient)))
    monkeypatch.setattr(provider_module, "GoogleOmniVideoProvider", lambda client: client)
    runner.provider_factory("synthetic")
    assert calls == [{"api_key": "synthetic", "http_options": {"retry_options": {"attempts": 1}}}]


def test_default_cli_is_offline(monkeypatch, capsys):
    monkeypatch.setattr(runner, "load_plan", lambda path: plan())
    monkeypatch.setattr(runner, "run_live", lambda *a, **k: pytest.fail("Paid runner forbidden"))
    assert runner.main(["--source-dir", "synthetic"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["paid_api_calls"] == 0 and result["paid_execution_authorized"] is False
