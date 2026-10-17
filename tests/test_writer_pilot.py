"""All provider/claim responses synthetic; real sockets forbidden."""
from datetime import date, datetime
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import run_writer_pilot as pilot
finally:
    sys.path.pop(0)

fixture_spec = importlib.util.spec_from_file_location("pilot_wire_fixture", ROOT / "tests/test_writer_execution_prep.py")
wire = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(wire)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import socket
    def fail(*args, **kwargs):
        raise AssertionError("Real network forbidden in pilot tests")
    monkeypatch.setattr(socket, "socket", fail)
    class FixedClock:
        @staticmethod
        def now(tz):
            return datetime(2026, 10, 18, tzinfo=tz)
    monkeypatch.setattr(pilot, "datetime", FixedClock)


def env():
    return {"GITHUB_REPOSITORY": pilot.REPO, "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": "refs/heads/main", "GITHUB_ACTOR": "Mrlukahuang",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "123",
            "WRITER_PILOT_CONFIRM": pilot.CONFIRM,
            "OPENAI_API_KEY": "synthetic-openai", "GEMINI_API_KEY": "synthetic-google",
            "GITHUB_TOKEN": "synthetic-github"}


def fake_transport(calls, *, bad=None, claimed=False):
    def post(url, key, body, **kwargs):
        calls.append(url)
        if url == pilot.COUNT_URL:
            return {"object": "response.input_tokens", "input_tokens": 5000}
        if url.startswith(pilot.COMMENTS):
            if body is None:
                return [{"body": pilot.MARKER}] if claimed else []
            return {"id": 1}
        if bad == "timeout":
            raise TimeoutError("synthetic timeout")
        result = wire.response(body["model"])
        if bad == "truncate": result["status"] = "incomplete"
        if bad == "usage": del result["usage"]
        if bad == "overbound":
            result["usage"]["output_tokens"] = 13000
        return result
    return post


def test_default_never_reads_credentials_or_posts(capsys):
    assert pilot.main([]) == 0
    assert json.loads(capsys.readouterr().out)["generation_attempts"] == 0


def test_full_pilot_claims_before_exactly_three_generations(tmp_path):
    calls = []
    out = tmp_path / "pilot"
    report = pilot.run_live(out, "0", env=env(), post=fake_transport(calls))
    assert report["generation_attempts"] == 3
    assert report["status"] == "first3_completed_pending_human_review"
    assert len(calls) == 7  # 2 count + 1 history + 1 claim + 3 generations
    assert calls[2].startswith(pilot.COMMENTS) and calls[3] == pilot.COMMENTS
    assert Decimal(report["budget"]["reserved_usd"]) < 2
    assert all(row["approval_granted"] is False for row in report["results"])
    assert not any("synthetic-openai" in p.read_text() for p in out.glob("*.json"))
    assert len(list(out.glob("*.screenplay.json"))) == 3


@pytest.mark.parametrize("bad", ["timeout", "truncate", "usage", "overbound"])
def test_failure_stops_after_first_attempt_and_preserves_claim(tmp_path, bad):
    calls = []
    out = tmp_path / bad
    with pytest.raises(RuntimeError, match="halted"):
        pilot.run_live(out, "0", env=env(), post=fake_transport(calls, bad=bad))
    report = json.loads((out / "report.json").read_text())
    assert report["status"] == "halted_no_retry"
    assert report["paid_reservation_claimed"] and report["generation_attempts"] == 1
    assert len(calls) == 5


def test_existing_claim_blocks_all_generation(tmp_path):
    calls = []
    with pytest.raises(RuntimeError):
        pilot.run_live(tmp_path / "prior", "0", env=env(),
                       post=fake_transport(calls, claimed=True))
    assert len(calls) == 3


@pytest.mark.parametrize("key,value", [("GITHUB_RUN_ATTEMPT", "2"),
    ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_ACTOR", "other"),
    ("GITHUB_REF", "refs/heads/unreviewed"), ("WRITER_PILOT_CONFIRM", ""),
    ("OPENAI_API_KEY", "")])
def test_context_or_missing_secret_denies_before_network(tmp_path, key, value):
    values = env(); values[key] = value
    calls = []
    with pytest.raises(RuntimeError):
        pilot.run_live(tmp_path / "denied", "0", env=values, post=fake_transport(calls))
    assert calls == []


def test_budget_uses_google_entire_input_ceiling_and_rejects_bad_counts():
    counts = {pilot.MODELS[0]: 5000, pilot.MODELS[1]: 5000}
    budget = pilot.pilot_budget(counts, "0", date(2026, 10, 18))
    assert budget["reservations"][pilot.MODELS[2]]["input_upper"] == 1048576
    for wrong in (None, True, 217601, -1):
        with pytest.raises(ValueError):
            pilot.pilot_budget({**counts, pilot.MODELS[0]: wrong}, "0", date(2026, 10, 18))
    with pytest.raises(ValueError):
        pilot.pilot_budget(counts, "4.99", date(2026, 10, 18))
    with pytest.raises(ValueError):
        pilot.pilot_budget(counts, "0", date(2026, 11, 1))
