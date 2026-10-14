"""G1/R1.6 offline-only Chinese transcript CER and ffprobe QA tests."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/g1_qa.py"
SHOTS = ROOT / "benchmarks/g1/shots.json"
spec = importlib.util.spec_from_file_location("g1_offline_qa", SCRIPT)
qa = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(qa)


def _shots():
    return json.loads(SHOTS.read_text(encoding="utf-8"))


def test_exactly_nine_pending_rows_never_claim_real_benchmark():
    result = qa.build_results(_shots())
    assert result["schema"] == "g1.qa-results.v1"
    assert result["real_benchmark_completed"] is False
    assert result["transcription_api_calls"] == 0
    assert result["video_generation_calls"] == 0
    assert result["paid_api_cost_usd"] == "0"
    assert len(result["results"]) == 9
    assert len({(r["shot_id"], r["provider_model"]) for r in result["results"]}) == 9
    assert all(r["technical_qa"] is None and r["chinese_character_metrics"] is None
               and r["transcription_model_verified"] is None
               and r["real_video_origin_verified"] is False
               and r["real_benchmark_evaluation_verified"] is False
               and r["status"] == "pending_real_media"
               for r in result["results"])


def test_cer_chinese_punctuation_spaces_and_unicode_normalization():
    result = qa.character_accuracy("你确定要走吗？我会回来。", "你确定要走吗 我会回来")
    assert result["edit_distance"] == 0
    assert result["character_error_rate"] == 0
    assert result["character_accuracy"] == 1
    assert qa.character_accuracy("ＡＢＣ", "ABC")["character_accuracy"] == 1


def test_cer_insert_delete_replace_and_bounded_accuracy():
    assert qa.character_accuracy("你好", "你")["edit_distance"] == 1
    assert qa.character_accuracy("你好", "你吗")["character_error_rate"] == 0.5
    assert qa.character_accuracy("你好", "你好吗")["edit_distance"] == 1
    assert qa.character_accuracy("你", "你好世界")["character_error_rate"] == 3
    assert qa.character_accuracy("你", "你好世界")["character_accuracy"] == 0


@pytest.mark.parametrize("reference,hypothesis", [("", "你好"), ("， 。", "你好"), ("你好", None)])
def test_cer_rejects_missing_reference_or_non_text(reference, hypothesis):
    with pytest.raises(ValueError):
        qa.character_accuracy(reference, hypothesis)


def test_operator_transcript_does_not_imply_gemini_transcription_or_real_video():
    result = qa.build_results(_shots(), [{
        "shot_id": "G1-S1",
        "provider_model": "gemini-omni-1.1-flash",
        "transcript": "你确定要走吗？我会回来。",
    }])
    row = result["results"][0]
    assert row["chinese_character_metrics"]["character_accuracy"] == 1
    assert row["transcript_source"] == "operator_supplied_unverified"
    assert row["transcription_model_verified"] is None
    assert row["real_video_origin_verified"] is False
    assert row["real_benchmark_evaluation_verified"] is False
    assert row["status"] == "offline_observation_unverified"
    assert result["transcription_api_calls"] == 0


def test_silent_shot_never_fabricates_speech_score():
    result = qa.build_results(_shots(), [{
        "shot_id": "G1-S3", "provider_model": "kling-v3-omni", "transcript": "",
    }])
    assert result["results"][-1]["chinese_character_metrics"] is None


@pytest.mark.parametrize("observation", [
    {"shot_id": "wrong", "provider_model": "kling-v3-omni"},
    {"shot_id": "G1-S1", "provider_model": "unknown"},
    {"shot_id": "G1-S1", "provider_model": "kling-v3-omni", "transcript": None},
    {"shot_id": "G1-S1", "provider_model": "kling-v3-omni", "unexpected": True},
    {"shot_id": "G1-S1", "provider_model": "kling-v3-omni", "media_path": ""},
])
def test_observations_fail_closed(observation):
    with pytest.raises(ValueError):
        qa.build_results(_shots(), [observation])


def test_duplicate_observations_fail_closed():
    item = {"shot_id": "G1-S2", "provider_model": "kling-v3-omni"}
    with pytest.raises(ValueError, match="duplicate"):
        qa.build_results(_shots(), [item, item])


def test_fixed_shot_contract_cannot_be_reordered_or_extended():
    for mutate in (
        lambda x: x["shots"].reverse(),
        lambda x: x["shots"].pop(),
        lambda x: x["shots"][0].update(duration_seconds=30),
        lambda x: x.update(schema="other"),
    ):
        data = deepcopy(_shots())
        mutate(data)
        with pytest.raises(ValueError):
            qa.build_results(data)


def test_ffprobe_rejects_missing_file_and_symlink(tmp_path):
    with pytest.raises(ValueError):
        qa.probe_media(tmp_path / "missing.mp4")
    target = tmp_path / "target.mp4"
    target.write_bytes(b"not video")
    link = tmp_path / "link.mp4"
    link.symlink_to(target)
    with pytest.raises(ValueError):
        qa.probe_media(link)


def test_ffprobe_invalid_mp4_fails_closed(tmp_path):
    target = tmp_path / "invalid.mp4"
    target.write_bytes(b"not an mp4")
    with pytest.raises(ValueError):
        qa.probe_media(target)


def test_cli_creates_no_fake_real_results(tmp_path):
    out = tmp_path / "results.json"
    result = subprocess.run([sys.executable, str(SCRIPT), "--out", str(out)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(out.read_text("utf-8"))
    assert payload["real_benchmark_completed"] is False
    assert payload["transcription_api_calls"] == 0
    assert len(payload["results"]) == 9
    assert list(tmp_path.iterdir()) == [out]


def test_cli_rejects_non_json_output(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT),
                             "--out", str(tmp_path / "result.mp4")],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                    reason="ffmpeg/ffprobe not installed (offline-video job installs pinned binaries)")
def test_actual_ffprobe_technical_qa_of_synthetic_local_clip(tmp_path):
    clip = tmp_path / "synthetic.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
        "-i", "color=c=black:s=144x256:r=5:d=5",
        "-c:v", "mpeg4", "-pix_fmt", "yuv420p", "-y", str(clip),
    ], check=True, timeout=30)
    result = qa.probe_media(clip, requires_audio=False)
    assert result["passed"] is True
    assert result["width"] == 144 and result["height"] == 256
    assert len(result["sha256"]) == 64
    assert result["has_audio"] is False
    assert qa.probe_media(clip, requires_audio=True)["issues"] == [
        "missing_dialogue_audio_stream"
    ]
