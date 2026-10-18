"""Real FFmpeg tests for the offline real-episode post-production bridge."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import postprocess_gpt_episode_offline as post
import assemble_gpt_video_three as assembly
sys.path.pop(0)

from drama_factory.pipeline.screenplay import Screenplay, ScreenplayShot, DialogueCue
from test_gpt_video_assembly import source


def script12(*, dialogue=True):
    shots = []
    for index, sid in enumerate(post.IDS, 1):
        shots.append(ScreenplayShot(
            shot_id=sid, duration_seconds=3,
            action="咖啡馆内一位人物看着杯子。", camera="固定中景",
            character_ids=["a-jie"], scene_id="cafe",
            continuity_start="手放在桌边", continuity_end="手仍在桌边",
            dialogue=[DialogueCue(speaker_actor_id="a-jie",
                                  text=f"测试台词{index}", start_second=0, end_second=2)]
                     if dialogue else [],
        ))
    return Screenplay(series_id="comparison-fixture",
                      story_bible_id="comparison-bible", episode_number=1,
                      episode_title="离线字幕回归", target_duration_seconds=36, shots=shots)


@pytest.fixture
def completed(source, tmp_path):
    episode = tmp_path / "original-episode"
    episode.mkdir()
    info = assembly.probe(source / "s01.mp4")
    shots = []
    for sid in post.IDS:
        path = episode / (sid + ".mp4")
        shutil.copyfile(source / "s01.mp4", path)
        shots.append({"shot_id": sid, "duration_seconds": str(info["duration_seconds"]),
                      "video_sha256": assembly.sha(path)})
    (episode / "report.json").write_text(json.dumps({
        "status": "episode_clips_completed_pending_human_review",
        "generation_attempts": 9,
        "source_response_sha256": "a" * 64,
        "run_id": "synthetic-12-only",
        "reused_shot_ids": post.IDS[:3],
        "shots": shots, "publish_approved": False,
    }), encoding="utf-8")
    delivery_dir = tmp_path / "original-delivery"
    result = assembly.assemble(episode, delivery_dir)
    assert result["all_script_shots_assembled"] is True
    return episode, delivery_dir


def test_real_subtitle_mux_preserves_native_audio_and_discloses_draft(completed, tmp_path):
    episode, delivery_dir = completed
    original_hash = assembly.sha(delivery_dir / "gpt-episode-preview.mp4")
    original_report = (episode / "report.json").read_bytes()
    result = post.render_draft_postprocess(
        script12(), "a" * 64, episode, delivery_dir, tmp_path / "post")
    assert result["technical_decode_passed"] is True
    assert result["subtitle_cues"] == 12
    assert result["new_model_calls"] == 0
    assert result["dialogue_content_verified"] is False
    assert result["subtitle_alignment_verified"] is False
    assert result["full_episode_complete"] is False
    assert result["publish_approved"] is False

    rendered = tmp_path / "post" / "gpt-episode-caption-draft.mp4"
    assert rendered.is_file()
    assert (episode / "report.json").read_bytes() == original_report
    assert assembly.sha(delivery_dir / "gpt-episode-preview.mp4") == original_hash
    details = json.loads((tmp_path / "post" / "07_subtitles.json").read_text())
    assert details["status"] == "screenplay_timed_draft_not_asr"
    assert details["actual_speech_alignment_verified"] is False
    music = json.loads((tmp_path / "post" / "08_music.json").read_text())
    assert music["separate_music_added"] is False
    srt = (tmp_path / "post" / "draft-captions.srt").read_text()
    assert "测试台词1" in srt and "测试台词12" in srt


@pytest.mark.parametrize("fault", ["wrong_hash", "bad_report", "tampered_clip",
                                      "bad_script", "no_dialogue", "existing_output"])
def test_rejects_mismatch_without_creating_new_video(completed, tmp_path, fault):
    episode, delivery_dir = completed
    source_hash = "a" * 64
    screenplay = script12()
    out = tmp_path / "post"
    if fault == "wrong_hash":
        source_hash = "b" * 64
    elif fault == "bad_report":
        report = json.loads((episode / "report.json").read_text())
        report["reused_shot_ids"] = ["s02", "s03", "s04"]
        (episode / "report.json").write_text(json.dumps(report))
    elif fault == "tampered_clip":
        (episode / "s10.mp4").write_bytes(b"tampered")
    elif fault == "bad_script":
        screenplay.shots[4].shot_id = "wrong-id"
    elif fault == "no_dialogue":
        screenplay = script12(dialogue=False)
    else:
        out.mkdir()
    with pytest.raises(ValueError):
        post.render_draft_postprocess(screenplay, source_hash, episode, delivery_dir, out)
    if fault != "existing_output":
        assert not out.exists()


def test_srt_slots_are_calculated_from_real_clip_lengths():
    raw = [{"shot_id": sid, "duration_seconds": "4.5"} for sid in post.IDS]
    text, count = post._draft_captions(script12(), raw)
    assert count == 12
    assert "00:00:00,000 --> 00:00:03,000" in text
    assert "00:00:49,500 --> 00:00:52,500" in text
