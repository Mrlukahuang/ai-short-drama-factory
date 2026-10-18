"""G4/R4.4: offline repair of one ALREADY-GENERATED real clip; no paid calls."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import repair_gpt_episode_offline as repair
import assemble_gpt_video_three as assembly
sys.path.pop(0)

from test_gpt_video_assembly import source


@pytest.fixture
def episode(source, tmp_path):
    folder = tmp_path / "full-original"
    folder.mkdir()
    ids = repair.SHOT_IDS
    for sid in ids:
        shutil.copyfile(source / "s01.mp4", folder / (sid + ".mp4"))
    clip = assembly.probe(folder / "s01.mp4")
    records = [{
        "shot_id": sid,
        "video_sha256": assembly.sha(folder / (sid + ".mp4")),
        "duration_seconds": str(clip["duration_seconds"]),
        "provider_task_id": "original-batch-id",
        "actual_fee_usd": None,
    } for sid in ids]
    report = {"status": "episode_clips_completed_pending_human_review",
        "generation_attempts": 9, "new_generation_attempts": 9,
        "reused_shot_ids": repair.FIRST, "source_response_sha256": "a" * 64,
        "run_id": "synthetic-offline", "shots": records,
        "all_script_shots_present": True, "publish_approved": False}
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return folder


@pytest.fixture
def other_clip(source, tmp_path):
    clip = tmp_path / "alternative.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin",
        "-f", "lavfi", "-i", "color=c=red:s=360x640:r=24:d=3",
        "-f", "lavfi", "-i", "sine=frequency=550:sample_rate=48000:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "2", str(clip)], check=True, timeout=90)
    return clip


def test_one_replacement_preserves_other_eleven_and_real_audio(episode, other_clip, tmp_path):
    original_report = (episode / "report.json").read_bytes()
    original_hashes = {sid: assembly.sha(episode / (sid + ".mp4"))
                       for sid in repair.SHOT_IDS}
    dest = tmp_path / "reassembled"
    result = repair.replace_completed_shot(episode, "s05", other_clip, dest)
    assert result["new_model_calls"] == 0
    assert result["replaced_shot_id"] == "s05"
    assert result["unchanged_shot_count"] == 11
    assert result["technical_decode_passed"] is True
    assert result["human_review_required"] is True
    assert result["publish_approved"] is False
    assert assembly.sha(episode / "s05.mp4") == original_hashes["s05"]
    assert (episode / "report.json").read_bytes() == original_report

    new_report = json.loads((dest / "episode" / "report.json").read_text())
    assert len(new_report["offline_replacements"]) == 1
    assert new_report["generation_attempts"] == 9
    assert new_report["offline_replacement_model_calls"] == 0
    assert new_report["shots"][4]["replacement_origin"].startswith("operator_supplied")
    assert "provider_task_id" not in new_report["shots"][4]
    assert new_report["shots"][4]["video_sha256"] == assembly.sha(other_clip)
    for sid in repair.SHOT_IDS:
        digest = assembly.sha(dest / "episode" / (sid + ".mp4"))
        assert digest == (assembly.sha(other_clip) if sid == "s05" else original_hashes[sid])
    delivery = json.loads((dest / "delivery" / "delivery.json").read_text())
    assert delivery["all_script_shots_assembled"] is True
    assert delivery["full_decode_passed"] is True
    assert delivery["dialogue_content_verified"] is False
    assert delivery["publish_approved"] is False
    assert delivery["new_model_calls"] == 0
    assert delivery["mp4_sha256"] == result["delivery_sha256"]
    assert not delivery["g4_duration_range_passed"]  # synthetic 12 x 3s


@pytest.mark.parametrize("failure", ["unknown_id", "same_bytes", "tampered_source",
                                      "bad_report", "bad_clip", "existing_output"])
def test_rejects_bad_input_without_paid_fallback(episode, other_clip, tmp_path, failure):
    destination = tmp_path / "new-delivery"
    shot = "s05"
    alternative = other_clip
    if failure == "unknown_id":
        shot = "s99"
    elif failure == "same_bytes":
        alternative = episode / "s05.mp4"
    elif failure == "tampered_source":
        (episode / "s04.mp4").write_bytes(b"corrupted")
    elif failure == "bad_report":
        raw = json.loads((episode / "report.json").read_text())
        raw["reused_shot_ids"] = ["s01", "s02", "s04"]
        (episode / "report.json").write_text(json.dumps(raw))
    elif failure == "bad_clip":
        alternative = tmp_path / "not-video.mp4"
        alternative.write_bytes(b"not an MP4")
    else:
        destination.mkdir()
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        repair.replace_completed_shot(episode, shot, alternative, destination)
    if failure != "existing_output":
        assert not destination.exists()


def test_symlinked_replacement_rejected(episode, other_clip, tmp_path):
    linked = tmp_path / "linked.mp4"
    linked.symlink_to(other_clip)
    with pytest.raises(ValueError):
        repair.replace_completed_shot(episode, "s02", linked, tmp_path / "out")
    assert not (tmp_path / "out").exists()
