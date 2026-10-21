"""G4/R4.4: actual existing local MP4→trusted SHA gate→existing W3 render.

ALL provider/receipt/media inputs in these tests are synthetic, deliberately
not claiming Google output. The tests use real FFmpeg and existing API/SQLite
approval transitions. No new model call, TTS, production DB or UI.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import pytest

from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.existing_real_shots import (
    RealShotHandoffError, admit_existing_real_shots,
)
from drama_factory.pipeline.offline_render import (
    PreviewError, inspect_mp4, render_approved_preview,
)
from test_offline_render import make_production
from test_g4_existing_real_shot_handoff import _candidate

requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Actual FFmpeg/FFprobe binaries required for G4 integration",
)


def _saved_draft(db, run):
    row = db.one(
        """SELECT e.body_json FROM productions p
           JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
        (run,),
    )
    return EpisodeDraft.model_validate_json(row["body_json"])


@requires_ffmpeg
def test_one_existing_video_goes_through_REAL_w3_ffmpeg_and_w4_technical_qa_only_after_approvals(
    client, tmp_path,
):
    # This is *the existing production state machine and renderer*, not a
    # parallel fake database/orchestration invented to make the test pass.
    _, run = make_production(client)
    db = client.app.state.db
    episode = _saved_draft(db, run)
    source = _candidate(tmp_path, sid="shot-1")
    original_sha = hashlib.sha256(source["media_path"].read_bytes()).hexdigest()

    clips, handoff = admit_existing_real_shots(episode, [source])
    assert list(clips) == ["shot-1"]
    assert handoff["missing_real_shot_ids"] == ["shot-2"]
    assert handoff["new_paid_provider_calls"] == 0

    root = tmp_path / "general-w3-ffmpeg"
    with pytest.raises(PreviewError, match="approvals"):
        render_approved_preview(db, run, root, source_clips=clips)
    assert not root.exists()

    assert client.post(f"/api/v1/productions/{run}/approve-script").status_code == 200
    with pytest.raises(PreviewError, match="approvals"):
        render_approved_preview(db, run, root, source_clips=clips)
    assert not root.exists()

    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code == 200
    delivery = render_approved_preview(db, run, root, source_clips=clips)
    assert [s["media_source"] for s in delivery["shots"]] == [
        "provided_local_clip", "placeholder",
    ]
    assert delivery["supplied_local_clips"] == 1
    assert delivery["placeholder_visuals"] is True
    assert delivery["paid_api_calls"] == 0
    assert delivery["technical_qa"]["technical_decode_passed"] is True
    assert delivery["technical_qa"]["publish_approved"] is False
    assert delivery["technical_qa"]["genuine_ai_video_verified"] is False
    assert delivery["technical_qa"]["operator_review_required"] is True
    assert inspect_mp4(Path(delivery["mp4_path"]), 2)["subtitle_codec"] == "mov_text"
    assert hashlib.sha256(source["media_path"].read_bytes()).hexdigest() == original_sha

    # Same existing-media sources: replay original W3 cache, NOT the SDK.
    again = render_approved_preview(db, run, root, source_clips=clips)
    assert [s["cached"] for s in again["shots"]] == [True, True]
    assert again["mp4_sha256"] == delivery["mp4_sha256"]
    assert again["paid_api_calls"] == 0


@requires_ffmpeg
def test_all_existing_video_shots_can_render_without_placeholder_while_still_blocking_release(
    client, tmp_path,
):
    _, run = make_production(client)
    db = client.app.state.db
    episode = _saved_draft(db, run)
    first = _candidate(tmp_path, sid="shot-1")
    second = _candidate(tmp_path, sid="shot-2", receipt_source="source_mp4_sha256")
    clips, report = admit_existing_real_shots(
        episode, [second, first], require_full_episode=True,
    )
    assert list(clips) == ["shot-1", "shot-2"]
    assert report["all_episode_shots_present"] is True
    assert report["content_quality_human_approved"] is False
    assert report["publication_approved"] is False
    for route in ("approve-script", "approve-characters"):
        assert client.post(f"/api/v1/productions/{run}/{route}").status_code == 200

    rendered = render_approved_preview(
        db, run, tmp_path / "fully-provided-existing-video", source_clips=clips,
    )
    assert rendered["supplied_local_clips"] == 2
    assert rendered["placeholder_visuals"] is False
    assert all(s["media_source"] == "provided_local_clip" for s in rendered["shots"])
    assert rendered["technical_qa"]["technical_decode_passed"] is True
    assert rendered["technical_qa"]["publish_approved"] is False
    assert rendered["technical_qa"]["genuine_ai_video_verified"] is False
    assert rendered["paid_api_calls"] == 0
    assert Path(rendered["mp4_path"]).is_file()
    assert inspect_mp4(Path(rendered["mp4_path"]), 2)["video_codec"] == "h264"


@requires_ffmpeg
def test_tampered_receipt_rejected_before_creating_any_output_or_making_api_call(
    client, tmp_path,
):
    _, run = make_production(client)
    db = client.app.state.db
    episode = _saved_draft(db, run)
    entry = _candidate(tmp_path, sid="shot-1")
    doc = json.loads(entry["receipt_path"].read_text("utf-8"))
    doc["model_calls"] = 0
    entry["receipt_path"].write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(RealShotHandoffError, match="receipt"):
        admit_existing_real_shots(episode, [entry])
    assert not (tmp_path / "must-not-create").exists()
    assert db.one("SELECT status FROM productions WHERE id=?", (run,))["status"] == (
        "script_review_pending"
    )
