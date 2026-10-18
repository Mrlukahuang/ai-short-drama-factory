"""Synthetic remaining-nine control flow, real local media reuse tests."""
from datetime import date
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import complete_gpt_episode as completion
import run_gpt_video_three as runner
sys.path.pop(0)
from test_gpt_video_three import dependencies, env as three_env, offline
from test_gpt_video_assembly import source


def nine_plan():
    return {"source_response_sha256": runner.SOURCE_HASH, "selected_shot_ids": completion.REST,
        "shots": [{"shot_id": s, "prompt": "合成", "prompt_sha256": "a" * 64} for s in completion.REST]}


def test_nine_budget_requires_new_five_dollar_exception():
    result = runner.estimate_budget(nine_plan(), "0", date(2026, 10, 19), completion=True)
    assert result["estimated_total_usd"] == "4.27173825"
    assert result["acknowledged_usd"] == "5"
    assert result["budget_upper_bound_verified"] is False
    for spend in (".01", "nan", "-1"):
        with pytest.raises(ValueError): runner.estimate_budget(nine_plan(), spend, date(2026, 10, 19), completion=True)
    with pytest.raises(ValueError): runner.estimate_budget(nine_plan(), "0", date(2026, 10, 19))


def test_old_confirmation_cannot_authorize_new_batch(tmp_path):
    calls = []
    with pytest.raises(RuntimeError):
        runner.run_live(nine_plan(), tmp_path / "bad", "0", env=three_env(), completion=True, **dependencies(calls))
    assert not calls


def test_remaining_nine_never_generates_first_three(tmp_path):
    calls = []; values = three_env(); values["VIDEO_CONFIRM"] = runner.FULL_CONFIRM
    captured = []
    deps = dependencies(calls)
    original = deps["post"]
    def post(url, key, body, **kwargs):
        if body is not None: captured.append(body["body"])
        return original(url, key, body, **kwargs)
    deps["post"] = post
    result = runner.run_live(nine_plan(), tmp_path / "nine", "0", env=values, completion=True, **deps)
    assert result["generation_attempts"] == 9
    assert [s["shot_id"] for s in result["shots"]] == completion.REST
    assert calls.count("generate") == 9
    assert runner.FULL_MARKER in captured[0] and "USD5 acknowledged" in captured[0]
    assert runner.MARKER not in captured[0]


def test_stage_and_assemble_twelve_synthetic_clips(source, tmp_path, monkeypatch):
    prior_report = json.loads((source / "report.json").read_text())
    prior_report["source_response_sha256"] = runner.SOURCE_HASH
    (source / "report.json").write_text(json.dumps(prior_report))
    monkeypatch.setattr(completion, "OLD_REPORT_SHA", completion.sha(source / "report.json"))
    generated = tmp_path / "nine"; generated.mkdir()
    records = []
    for sid in completion.REST:
        path = generated / (sid + ".mp4"); path.write_bytes((source / "s01.mp4").read_bytes())
        records.append({"shot_id": sid, "duration_seconds": prior_report["shots"][0]["duration_seconds"],
                        "video_sha256": completion.sha(path)})
    (generated / "report.json").write_text(json.dumps({"status": "nine_clips_completed_pending_human_review",
        "generation_attempts": 9, "source_response_sha256": runner.SOURCE_HASH,
        "run_id": "synthetic-nine", "shots": records}))
    staged = tmp_path / "episode"
    result = completion.stage_episode(source, generated, staged)
    assert result["reused_shot_ids"] == completion.FIRST and len(result["shots"]) == 12
    assert result["new_generation_attempts"] == 9
    delivery = completion.assemble(staged, tmp_path / "delivery")
    assert delivery["all_script_shots_assembled"] is True
    assert delivery["g4_duration_range_passed"] is False  # synthetic3s x12 is not60s
    assert delivery["full_episode_complete"] is False and delivery["publish_approved"] is False
    assert abs(delivery["duration_seconds"] - 36) < .5


def test_modified_prior_report_denied_before_generation(source, tmp_path):
    with pytest.raises(ValueError, match="original"):
        completion.verify_batch(source, completion.FIRST, "three_clips_completed_pending_human_review", 3, original=True)



def test_new_workflow_invokes_completion_not_old_three_shot_runner():
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/gpt-episode-completion.yml"
    text = workflow.read_text()
    assert "scripts/run_gpt_video_three.py" not in text
    assert "scripts/complete_gpt_episode.py --writer-dir artifacts/source-writer --prior-dir artifacts/prior-video3 --paid" in text
    assert runner.FULL_CONFIRM in text
    assert "39047208593" in text and "accept_estimate_not_cap" in text
