"""G4/R4.4: content-agnostic REAL-existing-shot admission, 0 model calls.

Synthetic media/receipts exercise the contract. They do NOT certify a genuine
provider run, content quality or a CityDiscount-specific production.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from drama_factory.models import EpisodeDraft, ShotDraft
from drama_factory.pipeline.existing_real_shots import (
    RealShotHandoffError, admit_existing_real_shots,
)


def _episode(name="Unrelated fictional episode"):
    return EpisodeDraft(
        title=name, episode_number=1, target_duration_seconds=6,
        shots=[
            ShotDraft(shot_id="opening", duration_seconds=3,
                      visual_description="Scene begins; synthetic test"),
            ShotDraft(shot_id="next", duration_seconds=3,
                      visual_description="Scene continues; synthetic test"),
        ],
    )


def _create_synthetic_mp4(path: Path, *, tone=430) -> None:
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=144x256:r=15:d=3.08",
        "-f", "lavfi", "-i", f"sine=frequency={tone}:duration=3.08",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac", "-t", "3.08", str(path),
    ], capture_output=True, check=True, timeout=45)


def _candidate(tmp_path: Path, *, sid="opening",
               receipt_source="source_video_sha256") -> dict:
    tmp_path.mkdir(exist_ok=True)
    media = tmp_path / f"{sid}.mp4"
    _create_synthetic_mp4(media)
    digest = hashlib.sha256(media.read_bytes()).hexdigest()
    receipt = tmp_path / f"{sid}.json"
    receipt.write_text(json.dumps({
        "schema": "synthetic-ci-not-provider-proof",
        "shot_id": sid, "model": "gemini-omni-1.1-flash",
        "model_calls": 1,
        "output_media": "real_omni_video_downloaded",
        "source_video_real_model": True,  # injected test-only statement
        "provider_reference_applied": True,
        "reference_image_count": 1,
        "source_pngs_transmitted": 1,
        "provider_task_id": "synthetic-test",
        "actual_fee_usd": None,
        "publication_approved": False,
        receipt_source: digest,
    }), encoding="utf-8")
    return {
        "shot_id": sid,
        "media_path": media, "receipt_path": receipt,
        "expected_sha256": digest,
    }


requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Offline FFmpeg/FFprobe required for actual synthetic MP4 decoding",
)


@requires_ffmpeg
def test_two_unrelated_episode_titles_use_identical_generic_admission_and_preserve_media(
    tmp_path,
):
    one = _candidate(tmp_path)
    a, r1 = admit_existing_real_shots(_episode("Pilot A"), [one])
    b, r2 = admit_existing_real_shots(_episode("Pilot B"), [one])
    assert a == b == {"opening": one["media_path"]}
    assert r1["selected_real_shot_ids"] == ["opening"]
    assert r1["missing_real_shot_ids"] == ["next"]
    assert r1["all_episode_shots_present"] is False
    assert r1["source_real_video_count"] == 1
    assert r1["report_sha256"] == admit_existing_real_shots(
        _episode("Pilot A"), [one])[1]["report_sha256"]
    assert r1["episode_sha256"] != r2["episode_sha256"]
    assert r1["new_paid_provider_calls"] == 0
    assert r1["new_video_generated"] is False
    assert r1["content_quality_human_approved"] is False
    assert r1["source_provider_actual_fees_verified"] is False
    assert str(tmp_path) not in json.dumps(r1)
    assert one["expected_sha256"] == r1["source_shots"][0]["source_mp4_sha256"]


@requires_ffmpeg
def test_complete_two_shot_episode_order_independent_of_input_order(tmp_path):
    a = _candidate(tmp_path, sid="opening")
    b = _candidate(tmp_path, sid="next", receipt_source="source_mp4_sha256")
    clips, report = admit_existing_real_shots(
        _episode(), [b, a], require_full_episode=True,
    )
    assert list(clips) == ["opening", "next"]
    assert report["selected_real_shot_ids"] == ["opening", "next"]
    assert report["missing_real_shot_ids"] == []
    assert report["all_episode_shots_present"] is True
    assert report["new_paid_provider_calls"] == 0
    assert report["technical_episode_rendered"] is False
    assert report["publication_approved"] is False


@requires_ffmpeg
def test_no_fake_promotion_missing_required_real_shots_or_shot_swap(tmp_path):
    a = _candidate(tmp_path, sid="opening")
    with pytest.raises(RealShotHandoffError, match="complete"):
        admit_existing_real_shots(_episode(), [a], require_full_episode=True)
    with pytest.raises(RealShotHandoffError, match="Unknown"):
        admit_existing_real_shots(_episode(), [{**a, "shot_id": "foreign"}])
    with pytest.raises(RealShotHandoffError, match="duplicate"):
        admit_existing_real_shots(_episode(), [a, a])


@requires_ffmpeg
@pytest.mark.parametrize("field", [
    "model_calls", "source_video_real_model", "output_media",
    "publication_approved", "reference_image_count",
    "provider_reference_applied", "source_pngs_transmitted", "shot_id",
])
def test_fabricated_or_disabled_receipts_rejected(tmp_path, field):
    entry=_candidate(tmp_path)
    path=entry["receipt_path"]
    payload=json.loads(path.read_text("utf-8"))
    bad={
        "model_calls":0, "source_video_real_model":False,
        "output_media":"not_generated", "publication_approved":True,
        "reference_image_count":0,
        "provider_reference_applied":False,
        "source_pngs_transmitted":0,
        "shot_id":"foreign",
    }
    payload[field]=bad[field]
    path.write_text(json.dumps(payload),encoding="utf-8")
    with pytest.raises(RealShotHandoffError):
        admit_existing_real_shots(_episode(), [entry])


@requires_ffmpeg
def test_media_tamper_wrong_independent_pin_cross_project_and_symlink_fail_closed(tmp_path):
    entry=_candidate(tmp_path)
    with pytest.raises(RealShotHandoffError, match="SHA"):
        admit_existing_real_shots(_episode(), [{**entry, "expected_sha256":"0"*64}])
    entry["media_path"].write_bytes(entry["media_path"].read_bytes() + b"tamper")
    with pytest.raises(RealShotHandoffError, match="differ"):
        admit_existing_real_shots(_episode(), [entry])
    entry=_candidate(tmp_path)
    link=tmp_path/"indirect.mp4"
    link.symlink_to(entry["media_path"])
    with pytest.raises(RealShotHandoffError, match="Symlinked"):
        admit_existing_real_shots(_episode(), [{**entry,"media_path":link}])


@requires_ffmpeg
def test_existing_adapter_requires_bounded_receipt_and_single_sha(tmp_path):
    entry=_candidate(tmp_path)
    path=entry["receipt_path"]
    document=json.loads(path.read_text("utf-8"))
    document["video_sha256"]=entry["expected_sha256"]
    path.write_text(json.dumps(document),encoding="utf-8")
    with pytest.raises(RealShotHandoffError, match="Exactly one"):
        admit_existing_real_shots(_episode(), [entry])
    path.write_text("{"+"x"*40000, encoding="utf-8")
    with pytest.raises(RealShotHandoffError, match="size"):
        admit_existing_real_shots(_episode(), [entry])


def test_strict_typed_inputs_reject_unapproved_or_nonlocal_file_selection():
    episode = _episode()
    with pytest.raises(RealShotHandoffError):
        admit_existing_real_shots(episode, [])
    with pytest.raises(RealShotHandoffError):
        admit_existing_real_shots(episode, [{"shot_id":"opening"}])
    with pytest.raises(RealShotHandoffError):
        admit_existing_real_shots(episode, None)
    with pytest.raises(RealShotHandoffError):
        admit_existing_real_shots(episode, [{
            "shot_id":"opening","media_path":"https://user/secret.mp4",
            "receipt_path":Path("/not-a-file.json"),"expected_sha256":"0"*64,
        }])
