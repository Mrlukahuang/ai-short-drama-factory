"""G1/R1.6 metric plumbing; only fake transcript strings and synthetic local MP4."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from drama_factory.pipeline.g1_benchmark_metrics import (
    G1MetricError, build_pending_results, character_error_rate,
    ffprobe_local_video, score_stub_transcript,
)

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "benchmarks/g1/shots.json"
RESULTS = ROOT / "benchmarks/g1/results.json"
spec = importlib.util.spec_from_file_location("g1_ab_plan_metrics", ROOT / "scripts/ab_benchmark.py")
plan_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(plan_module)


def _inputs():
    shots = json.loads(SHOTS.read_text(encoding="utf-8"))
    plan = plan_module.build_plan(
        shots, confirmation="G1-PLAN-ONLY", budget_usd="30.00"
    )
    return plan, shots


def test_pending_nine_trials_are_distinct_and_never_fake_real_metrics():
    plan, shots = _inputs()
    untouched = deepcopy((plan, shots))
    result = build_pending_results(plan, shots)
    assert (plan, shots) == untouched
    assert result == json.loads(RESULTS.read_text(encoding="utf-8"))
    assert result["schema"] == "g1.benchmark-results.v1"
    assert result["execution_mode"] == "offline_contract_only"
    assert result["real_model_benchmark_complete"] is False
    assert result["real_provider_calls"] == 0
    assert result["real_transcription_calls"] == 0
    assert result["paid_provider_spend_usd"] == "0"
    assert result["total_trials"] == 9
    assert result["transcriber_model"] == "gemini-3.5-transcribe"
    assert [r["speech"]["expected_characters"] for r in result["results"]] == [
        10, 10, 10, 9, 9, 9, 0, 0, 0,
    ]
    assert all(r["speech"]["character_error_rate"] is None
               and r["speech"]["character_accuracy"] is None
               and r["technical_qa"]["status"] == "not_run"
               and r["actual_fee_usd"] is None
               and r["video_sha256"] is None
               and r["real_video_status"] == "not_generated"
               and r["human_approved"] is False
               for r in result["results"])


@pytest.mark.parametrize(("expected", "supplied", "cer"), [
    ("你确定要走吗？", "你确定要走吗", 0),
    ("我会回来。", "我会回去", 0.25),
    ("你好", "你好吗", 0.5),
    ("你好", "您好", 0.5),
    ("你好", "你你你你好", 1.5),
    ("A B C！", "abc", 0),
])
def test_character_error_rate_chinese_alignment(expected, supplied, cer):
    assert character_error_rate(expected, supplied) == cer


def test_silent_shot_never_scores_false_one_hundred_percent_accuracy():
    with pytest.raises(G1MetricError, match="silent"):
        character_error_rate("", "")
    mocked = score_stub_transcript("我会回来。", "我会回去")
    assert mocked["mode"] == "offline_stub_only"
    assert mocked["diagnostic_character_error_rate"] == 0.25
    assert mocked["transcriber_model"] is None
    assert mocked["real_character_error_rate"] is None
    assert mocked["real_character_accuracy"] is None
    assert mocked["measured_real_video"] is False


def test_modified_or_post_execution_plan_rejected_not_fabricated():
    plan, shots = _inputs()
    broken = deepcopy(plan)
    broken["tasks"][0]["model_calls"] = 1
    with pytest.raises(G1MetricError, match="Refusing"):
        build_pending_results(broken, shots)
    broken = deepcopy(plan)
    broken["tasks"].reverse()
    with pytest.raises(G1MetricError, match="nine"):
        build_pending_results(broken, shots)
    broken = deepcopy(shots)
    broken["shots"][0]["shot_id"] = "someone-else"
    with pytest.raises(G1MetricError, match="fixed-shot"):
        build_pending_results(plan, broken)


def test_cli_offline_only_and_canonical_result(tmp_path):
    output = tmp_path / "results.json"
    process = subprocess.run([
        sys.executable, str(ROOT / "scripts/g1_metrics.py"),
        "--shots", str(SHOTS), "--out", str(output),
    ], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert "no real videos" in process.stdout
    assert json.loads(output.read_text("utf-8")) == json.loads(RESULTS.read_text("utf-8"))
    assert list(tmp_path.iterdir()) == [output]
    invalid = subprocess.run([
        sys.executable, str(ROOT / "scripts/g1_metrics.py"),
        "--execute", "--out", str(tmp_path / "live.json"),
    ], capture_output=True, text=True)
    assert invalid.returncode != 0
    assert not (tmp_path / "live.json").exists()


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="local synthetic ffmpeg/ffprobe required")
def test_local_synthetic_mp4_probe_is_not_mistaken_for_real_ai(tmp_path):
    movie = tmp_path / "synthetic.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=500:sample_rate=48000",
        "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(movie),
    ], check=True, capture_output=True, timeout=90)
    result = ffprobe_local_video(movie, 3)
    assert result["status"] == "offline_technical_probe_only"
    assert result["video_codec"] == "h264"
    assert result["audio_codec"] == "aac"
    assert result["width"] == 360 and result["height"] == 640
    assert result["has_audio"] is True
    assert len(result["video_sha256"]) == 64
    assert result["proves_real_ai_generation"] is False


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
                    reason="local synthetic ffmpeg/ffprobe required")
def test_landscape_synthetic_clip_refused_by_g1_probe(tmp_path):
    movie = tmp_path / "landscape.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15",
        "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(movie),
    ], check=True, capture_output=True, timeout=90)
    with pytest.raises(G1MetricError, match="9:16"):
        ffprobe_local_video(movie, 3)


def test_g1_probe_rejects_foreign_path_without_running_ffprobe(tmp_path):
    with pytest.raises(G1MetricError, match="local MP4"):
        ffprobe_local_video(tmp_path / "none.mp4", 5)
    with pytest.raises(G1MetricError, match="local MP4"):
        ffprobe_local_video(tmp_path / "https://example.test/secret.mp4", 5)
