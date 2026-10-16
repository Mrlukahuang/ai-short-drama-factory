"""P6 end-to-end offline CLI test; all media generated from synthetic text/tones."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

import importlib.util

# scripts/ is an entrypoint directory, not an installed Python package.
SPEC = importlib.util.spec_from_file_location(
    "fake_episode_script",
    Path(__file__).resolve().parents[1] / "scripts" / "fake_episode.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
FakePipelineError = MODULE.FakePipelineError
STEPS = MODULE.STEPS
run_fake_episode = MODULE.run_fake_episode

needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="real local FFmpeg needed for Fake E2E",
)


def _input(tmp_path):
    synopsis = tmp_path / "original.txt"
    synopsis.write_text(
        "两位虚构朋友在一间空白的纸板车站里共同寻找一枚虚构的蓝色钥匙。"
        "故事、人物及全部视觉场景均为原创测试占位。",
        encoding="utf-8",
    )
    return synopsis


def test_explicit_fake_only_operator_acknowledgement_required(tmp_path):
    with pytest.raises(FakePipelineError, match="confirmation"):
        run_fake_episode(_input(tmp_path), tmp_path / "out")


@needs_ffmpeg
def test_one_cli_source_to_fully_traceable_fake_mp4_then_reopen_and_rerun(tmp_path):
    synopsis = _input(tmp_path)
    root = tmp_path / "out"
    result = run_fake_episode(
        synopsis, root, acknowledge_fake_approvals=True,
    )
    mp4 = Path(result["mp4_path"])
    assert mp4.exists()
    assert mp4.read_bytes()[:4]
    assert result["paid_provider_calls"] == 0
    assert result["real_ai_video_verified"] is False
    assert result["publish_approved"] is False
    run = Path(result["run_dir"])
    files = sorted(x.stem for x in run.glob("*.json"))
    assert files == sorted(STEPS)
    for key in STEPS:
        doc = json.loads((run / f"{key}.json").read_text(encoding="utf-8"))
        assert doc["schema_version"] == "fake-pipeline-stage.v1"
        assert doc["step"] == key and doc["fake_only"] is True
        assert len(doc["input_sha256"]) == 64
        assert hashlib.sha256(
            (json.dumps(doc["payload"], sort_keys=True, ensure_ascii=False,
                        separators=(",", ":")) + "\n").encode("utf-8")
        ).hexdigest() == doc["payload_sha256"]
    digest = hashlib.sha256(mp4.read_bytes()).hexdigest()
    cached = run_fake_episode(synopsis, root, acknowledge_fake_approvals=True)
    assert cached["mp4_sha256"] == digest
    assert cached["run_dir"] == result["run_dir"]
    # For P6, rerun one stage and its dependents only, no new provider task.
    replay = run_fake_episode(
        synopsis, root, acknowledge_fake_approvals=True,
        rerun_from="06_dialogue",
    )
    assert replay["mp4_sha256"] == digest
    assert replay["full_decode_passed"] is True


@needs_ffmpeg
def test_tampered_stage_source_media_is_not_silently_reused(tmp_path):
    source = _input(tmp_path)
    root = tmp_path / "out"
    first = run_fake_episode(source, root, acknowledge_fake_approvals=True)
    folder = Path(first["run_dir"])
    stage = folder / "05_shots.json"
    doc = json.loads(stage.read_text("utf-8"))
    doc["payload"]["paid_provider_calls"] = 1
    stage.write_text(json.dumps(doc), encoding="utf-8")
    restored = run_fake_episode(
        source, root, acknowledge_fake_approvals=True,
    )
    assert restored["full_decode_passed"] is True
    assert json.loads(stage.read_text("utf-8"))["payload"]["paid_provider_calls"] == 0
