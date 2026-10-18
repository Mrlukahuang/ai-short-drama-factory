"""Real FFmpeg assembly using synthetic color/audio clips, no paid calls."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

spec = importlib.util.spec_from_file_location("gpt_assembly", Path(__file__).resolve().parents[1] / "scripts/assemble_gpt_video_three.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def source(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe required for real media contract")
    folder = tmp_path / "source"; folder.mkdir()
    clip = folder / "s01.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-f", "lavfi", "-i",
        "color=c=blue:s=360x640:r=24:d=3", "-f", "lavfi", "-i",
        "sine=frequency=440:sample_rate=48000:duration=3", "-c:v", "libx264",
        "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", str(clip)], check=True)
    for sid in ("s02", "s03"): shutil.copyfile(clip, folder / f"{sid}.mp4")
    duration = str(module.probe(clip)["duration_seconds"])
    report = {"status": "three_clips_completed_pending_human_review", "generation_attempts": 3,
        "run_id": "synthetic-not-ai", "shots": [{"shot_id": sid, "duration_seconds": duration,
        "video_sha256": module.sha(folder / f"{sid}.mp4")} for sid in module.IDS]}
    (folder / "report.json").write_text(json.dumps(report))
    return folder


def test_real_ffmpeg_assembly_preserves_sources_and_requires_review(source, tmp_path):
    hashes = [module.sha(source / f"{sid}.mp4") for sid in module.IDS]
    result = module.assemble(source, tmp_path / "delivery")
    assert result["full_decode_passed"] is True
    assert result["native_audio_preserved"] is True and result["stream_copy"] is True
    assert abs(result["duration_seconds"] - 9) < .25
    assert result["new_model_calls"] == 0 and result["publish_approved"] is False
    assert result["full_episode_complete"] is False
    assert hashes == [module.sha(source / f"{sid}.mp4") for sid in module.IDS]
    with pytest.raises(FileExistsError): module.assemble(source, tmp_path / "delivery")


@pytest.mark.parametrize("fault", ["incomplete", "order", "modified", "missing"])
def test_bad_source_denied_without_creating_delivery(source, tmp_path, fault):
    report = json.loads((source / "report.json").read_text())
    if fault == "incomplete": report["status"] = "halted_no_retry"
    elif fault == "order": report["shots"].reverse()
    elif fault == "modified": (source / "s01.mp4").write_bytes(b"tampered")
    else: (source / "s03.mp4").unlink()
    (source / "report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError): module.assemble(source, tmp_path / "delivery")
    assert not (tmp_path / "delivery").exists()
