"""W1 end-to-end Fake receiver and real FFmpeg repair/postproduction tests."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import w1_single_shot_repair as w1
import assemble_gpt_video_three as assembly
sys.path.pop(0)

from drama_factory.pipeline.screenplay import Screenplay, ScreenplayShot, DialogueCue
from test_gpt_video_assembly import source


def _screenplay():
    shots = [ScreenplayShot(shot_id=s, duration_seconds=3,
        action="桌上只有一杯咖啡", camera="固定镜头",
        character_ids=["a-jie"], scene_id="cafe",
        dialogue=[DialogueCue(speaker_actor_id="a-jie", text="请再检查这杯咖啡",
                              start_second=0, end_second=2)],
        continuity_start="手在桌边", continuity_end="手在桌边") for s in w1.SHOT_IDS]
    return Screenplay(series_id="comparison-fixture",
        story_bible_id="comparison-bible", episode_number=1,
        episode_title="离线修镜", target_duration_seconds=36, shots=shots)


@pytest.fixture
def parent(source, tmp_path):
    folder = tmp_path / "original"
    folder.mkdir()
    details = assembly.probe(source / "s01.mp4")
    records = []
    for s in w1.SHOT_IDS:
        item = folder / (s + ".mp4")
        shutil.copyfile(source / "s01.mp4", item)
        records.append({"shot_id": s, "video_sha256": assembly.sha(item),
            "duration_seconds": str(details["duration_seconds"]),
            "provider_task_id": "old-real-task-receipt", "actual_fee_usd": None,
            "prompt_sha256": "b" * 64})
    (folder / "report.json").write_text(json.dumps({
        "status": "episode_clips_completed_pending_human_review",
        "generation_attempts": 9, "new_generation_attempts": 9,
        "source_response_sha256": "a" * 64,
        "reused_shot_ids": w1.FIRST,
        "run_id": "synthetic-original-no-provider", "shots": records,
        "publish_approved": False}), encoding="utf-8")
    delivery = tmp_path / "delivery"
    assembly.assemble(folder, delivery)
    return folder, delivery


@pytest.fixture
def alternate(tmp_path):
    dest = tmp_path / "one-replacement.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin",
        "-f", "lavfi", "-i", "color=c=red:s=360x640:r=24:d=3",
        "-f", "lavfi", "-i", "sine=frequency=560:sample_rate=48000:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "2", str(dest)], check=True, timeout=90)
    return dest


@pytest.fixture
def data(parent):
    original, delivery = parent
    prompt = "单镜测试：固定毛毡男子看着桌上的杯子"
    request = {"selected_shot_ids": ["s07"], "source_response_sha256": "a"*64,
        "shots": [{"shot_id": "s07", "prompt": prompt,
                   "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}]}
    review = {"shot_id": "s07", "decision": "needs_repair",
        "reason": "三格分屏，需要单镜修复", "reviewed_by": "human-operator",
        "source_video_sha256": assembly.sha(original / "s07.mp4")}
    screenplay = _screenplay()
    plan = w1.build_repair_plan(screenplay, request, original, delivery, review)
    return screenplay, request, review, plan


def test_w1_fake_closed_loop_preserves_eleven_and_parent(parent, alternate, data, tmp_path):
    original, delivery = parent
    screenplay, request, review, plan = data
    old_report_sha = assembly.sha(original / "report.json")
    old_delivery_sha = assembly.sha(delivery / "gpt-episode-preview.mp4")
    result = w1.complete_offline_fake(plan, screenplay, request, review,
        original, delivery, alternate, tmp_path / "new-version")
    assert result["status"] == "offline_fake_repaired"
    assert result["new_paid_model_calls"] == 0 and result["new_provider_task_id"] is None
    assert result["new_api_cost_usd"] == "0"
    assert result["technical_qa_passed"] is True
    assert result["publish_approved"] is False
    assert result["parent_episode_report_sha256"] == old_report_sha
    assert result["parent_delivery_sha256"] == old_delivery_sha
    assert result["prior_shot_receipt"]["provider_task_id"] == "old-real-task-receipt"
    assert assembly.sha(original / "report.json") == old_report_sha
    assert assembly.sha(delivery / "gpt-episode-preview.mp4") == old_delivery_sha
    repaired = tmp_path / "new-version" / "repair" / "episode"
    shots = json.loads((repaired / "report.json").read_text())["shots"]
    for rec in shots:
        old = plan["unchanged_shots_sha256"].get(rec["shot_id"])
        assert rec["video_sha256"] == (old if old else assembly.sha(alternate))
        assert assembly.sha(repaired / (rec["shot_id"]+".mp4")) == rec["video_sha256"]
    post = tmp_path / "new-version" / "post"
    assert (post / "gpt-episode-caption-draft.mp4").is_file()
    assert (post / "draft-captions.srt").is_file()
    qa = json.loads((post / "10_qa.json").read_text())
    assert qa["technical_decode_passed"] is True
    assert qa["dialogue_content_verified"] is False
    assert qa["subtitle_alignment_verified"] is False
    assert qa["new_model_calls"] == 0
    assert result["draft_postprocessed_mp4_sha256"] == qa["mp4_sha256"]


@pytest.mark.parametrize("fault", [
    "wrong_id", "no_failure_review", "stale_review", "wrong_prompt", "mutated_plan",
    "faked_paid_approval", "old_usd5", "tampered_source", "tampered_delivery",
    "bad_codec", "existing_output", "missing_replacement"])
def test_w1_rejects_unsafe_paths_and_claims_before_paid_calls(
        parent, alternate, data, tmp_path, fault):
    original, delivery = parent
    screenplay, request, review, plan = data
    plan = json.loads(json.dumps(plan))
    review = dict(review)
    request = json.loads(json.dumps(request))
    replacement = alternate
    out = tmp_path / "next"
    if fault == "wrong_id":
        review["shot_id"] = "s99"
    elif fault == "no_failure_review":
        review["decision"] = "usable"
    elif fault == "stale_review":
        review["source_video_sha256"] = "f"*64
    elif fault == "wrong_prompt":
        request["shots"][0]["prompt"] = "Changed without hash"
    elif fault == "mutated_plan":
        plan["request"]["prompt"] = "Different prompt"
    elif fault == "faked_paid_approval":
        plan["finance"]["paid_execution_authorized"] = True
    elif fault == "old_usd5":
        plan["finance"]["independent_paid_approval"] = "RUN_GPT_REMAINING9_ESTIMATE_USD5"
    elif fault == "tampered_source":
        (original / "s09.mp4").write_bytes(b"forged")
    elif fault == "tampered_delivery":
        (delivery / "gpt-episode-preview.mp4").write_bytes(b"forged")
    elif fault == "bad_codec":
        replacement = tmp_path / "nonvideo.mp4"
        replacement.write_bytes(b"invalid")
    elif fault == "existing_output":
        out.mkdir()
    else:
        replacement = tmp_path / "missing.mp4"
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        w1.complete_offline_fake(plan, screenplay, request, review,
                                 original, delivery, replacement, out)
    assert not out.exists() or fault == "existing_output"


def test_w1_plan_never_authorizes_old_fee(parent, data):
    _, _, _, plan = data
    assert plan["shot_id"] == "s07"
    assert len(plan["unchanged_shots_sha256"]) == 11
    assert plan["finance"]["independent_paid_approval"] is None
    assert plan["finance"]["prior_usd5_authorization_reusable"] is False
    assert plan["finance"]["supplier_hard_charge_cap_verified"] is False
    assert plan["new_paid_model_calls"] == 0
    assert plan["status"] == "awaiting_new_independent_paid_approval"
