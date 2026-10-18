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
import repair_gpt_episode_offline as repair
sys.path.pop(0)

from drama_factory.pipeline.screenplay import Screenplay, ScreenplayShot, DialogueCue
from test_gpt_video_assembly import source
from test_gpt_w1_single_shot_closed_loop import parent as w1_parent, alternate as w1_alternate


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


def test_w3_measured_timeline_and_immutable_render_receipt(completed, tmp_path):
    episode, delivery = completed
    target = tmp_path / "w3-original"
    result = post.render_draft_postprocess(script12(), "a"*64, episode, delivery, target)
    render_file = target / "09_render.json"
    receipt = json.loads(render_file.read_text("utf-8"))
    qa = json.loads((target / "10_qa.json").read_text("utf-8"))
    assert receipt["contract"] == "g4-w3-render-provenance.v1"
    assert receipt["shot_order"] == post.IDS
    assert len(receipt["shots"]) == 12
    assert receipt["shots"][0]["start_ms"] == 0
    assert receipt["shots"][-1]["end_ms"] == receipt["measured_shot_total_ms"]
    assert all(a["end_ms"] == b["start_ms"]
               for a,b in zip(receipt["shots"], receipt["shots"][1:]))
    assert all(item["clip_sha256"] == assembly.sha(episode / (item["shot_id"] + ".mp4"))
               for item in receipt["shots"])
    assert receipt["original_source_report_sha256"] == assembly.sha(episode / "report.json")
    assert receipt["original_delivery_manifest_sha256"] == assembly.sha(delivery / "delivery.json")
    assert receipt["srt_sha256"] == assembly.sha(target / "draft-captions.srt")
    assert receipt["mp4_sha256"] == assembly.sha(target / "gpt-episode-caption-draft.mp4")
    assert qa["render_receipt_sha256"] == assembly.sha(render_file)
    assert qa["production_assets_verified"] is False
    assert qa["asset_manifest_sha256"] is None
    assert receipt["subtitle_mode"] == "screenplay_timed_draft_not_asr"
    assert receipt["audio_stream_copy"] is True and receipt["audio_reencoded"] is False
    assert receipt["repair"]["replacement_mode"] == "original_completed_episode"
    assert receipt["repair"]["parent_source_crosschecked"] is False
    assert result["publish_approved"] is False


def test_w3_read_only_w1_parent_chain_is_crosschecked(
        w1_parent, w1_alternate, tmp_path):
    parent_episode, parent_delivery = w1_parent
    repaired_root = tmp_path / "repaired"
    repair.replace_completed_shot(parent_episode, "s07", w1_alternate, repaired_root)
    before = assembly.sha(parent_episode / "report.json")
    child_episode = repaired_root / "episode"
    child_delivery = repaired_root / "delivery"
    output = tmp_path / "w3-repaired"
    result = post.render_draft_postprocess(
        script12(), "a"*64, child_episode, child_delivery, output,
        parent_episode_dir=parent_episode, parent_delivery_dir=parent_delivery)
    receipt = json.loads((output / "09_render.json").read_text("utf-8"))
    lineage = receipt["repair"]
    assert result["technical_decode_passed"] is True
    assert lineage["parent_source_crosschecked"] is True
    assert lineage["parent_episode_report_sha256"] == before
    assert lineage["parent_preview_sha256"] == assembly.sha(
        parent_delivery / "gpt-episode-preview.mp4")
    assert lineage["replacement_mode"] == "operator_existing_media_offline_simulation"
    assert lineage["replacements"][0]["shot_id"] == "s07"
    assert lineage["replacements"][0]["new_sha256"] == assembly.sha(w1_alternate)
    assert sum(rec["clip_sha256"] != assembly.sha(parent_episode / (rec["shot_id"]+".mp4"))
               for rec in receipt["shots"]) == 1
    assert assembly.sha(parent_episode / "report.json") == before
    assert receipt["production_assets_verified"] is False
    assert receipt["asset_manifest_sha256"] is None


@pytest.mark.parametrize("fault", ["missing_pair", "wrong_parent_hash", "wrong_parent_video"])
def test_w3_rejects_false_parent_before_output(w1_parent, w1_alternate, tmp_path, fault):
    parent_episode, parent_delivery = w1_parent
    repaired_root = tmp_path / "repaired"
    repair.replace_completed_shot(parent_episode, "s07", w1_alternate, repaired_root)
    opts = {"parent_episode_dir": parent_episode, "parent_delivery_dir": parent_delivery}
    if fault == "missing_pair":
        opts.pop("parent_delivery_dir")
    elif fault == "wrong_parent_hash":
        report = json.loads((parent_episode / "report.json").read_text("utf-8"))
        report["run_id"] = "tampered-after-repair"
        (parent_episode / "report.json").write_text(json.dumps(report), encoding="utf-8")
    else:
        (parent_delivery / "gpt-episode-preview.mp4").write_bytes(b"invalid-parent")
    output = tmp_path / "no-version"
    with pytest.raises(ValueError):
        post.render_draft_postprocess(script12(), "a"*64,
            repaired_root / "episode", repaired_root / "delivery", output, **opts)
    assert not output.exists()
