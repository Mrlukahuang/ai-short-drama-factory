"""Real FFmpeg local animated-reference shot, no Google billing or user assets."""
from __future__ import annotations

import ast
from pathlib import Path
import shutil

from PIL import Image, ImageDraw
import io
import pytest

from drama_factory.pipeline.local_asset_references import (
    stage_local_asset_reference,
)
from drama_factory.pipeline.local_reference_animatic import (
    LocalAnimaticError, stage_reference_motion_clip,
)
from drama_factory.pipeline.local_shot_media import get_staged_shot_clips
from drama_factory.pipeline.media_ingest import inspect_source
from drama_factory.pipeline.offline_render import (
    render_approved_preview, inspect_mp4,
)
from drama_factory.pipeline.offline_review import load_local_offline_review
from drama_factory.pipeline.local_story_workflow import make_storyboard_template
from test_screenplay import setup_series


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Real local video animation needs FFmpeg",
)


def _image() -> bytes:
    frame = Image.new("RGB", (600, 400))
    draw = ImageDraw.Draw(frame)
    for i in range(80):
        draw.rectangle((i * 5, i * 3, i * 5 + 10, i * 3 + 10),
                       fill=((i * 3) % 255, (100 + i) % 255, 80))
    out = io.BytesIO()
    frame.save(out, format="PNG")
    return out.getvalue()


def _approved(client, tmp_path, *, approve=True):
    series, bible, actor, scene = setup_series(client, "Synthetic motion drama")
    draft = make_storyboard_template(
        series, bible, [actor], scene, shot_count=2, seconds_per_shot=2,
    )
    created = client.post(f"/api/v1/series/{series}/screenplays/commit", json={
        "screenplay": draft, "reviewed_by_operator": True,
    })
    assert created.status_code == 201, created.text
    episode = created.json()["episode_id"]
    run = client.post(f"/api/v1/episodes/{episode}/productions")
    assert run.status_code == 201, run.text
    run_id = run.json()["production_id"]
    if approve:
        assert client.post(f"/api/v1/productions/{run_id}/approve-script").status_code == 200
        assert client.post(f"/api/v1/productions/{run_id}/approve-characters").status_code == 200
    db = client.app.state.db
    image_root = tmp_path / "local-asset-references"
    media_root = tmp_path / "local-shot-media"
    sha = stage_local_asset_reference(
        db, series, actor, image_root, filename="synthetic.png",
        content=_image(), operator_attests_rights=True,
    )["source_sha256"]
    return db, series, actor, scene, run_id, sha, image_root, media_root


def _stage(ctx, **kwargs):
    db, sid, actor, scene, run, sha, images, media = ctx
    return stage_reference_motion_clip(
        db, series_id=sid, production_id=run,
        shot_id="S001", asset_id=actor, reference_sha256=sha,
        image_root=images, media_root=media,
        operator_confirmed_local_derivative_use=True,
        **kwargs,
    )


@requires_ffmpeg
def test_static_reference_becomes_true_moving_watermarked_video_then_full_mp4(client, tmp_path):
    ctx = _approved(client, tmp_path)
    db, sid, actor, _, run, sha, images, media = ctx
    motion = _stage(ctx)
    assert motion["kind"] == "simulated_reference_motion"
    assert motion["genuine_ai_video"] is False
    assert motion["genuine_live_action"] is False
    assert motion["publish_approved"] is False
    assert motion["paid_api_calls"] == 0
    assert motion["source_reference_sha256"] == sha
    clips = get_staged_shot_clips(db, run, sid, media)
    assert set(clips) == {"S001"}
    inspected = inspect_source(clips["S001"], 2)
    assert inspected["duration"] == pytest.approx(2.0, abs=0.1)
    assert inspected["has_audio"] is False
    output = render_approved_preview(
        db, run, tmp_path / "offline-reviews", source_clips=clips,
    )
    assert output["supplied_local_clips"] == 1
    assert output["paid_api_calls"] == 0
    assert [x["media_source"] for x in output["shots"]] == [
        "provided_local_clip", "placeholder",
    ]
    assert inspect_mp4(Path(output["mp4_path"]), 4)["subtitle_codec"] == "mov_text"
    review = load_local_offline_review(
        db, run, tmp_path / "offline-reviews", series_id=sid,
    )
    assert review["technical_qa_passed"] is True
    assert review["publish_approved"] is False
    assert review["commercial_rights_verified"] is False


@requires_ffmpeg
def test_existing_manual_clip_must_be_explicitly_replaced(client, tmp_path):
    ctx = _approved(client, tmp_path)
    first = _stage(ctx)
    with pytest.raises(LocalAnimaticError, match="replacement"):
        _stage(ctx)
    second = _stage(ctx, replace_existing_video=True)
    assert first["sha256"] == second["sha256"]
    assert second["rights_independently_verified"] is False


@requires_ffmpeg
def test_invalid_scope_or_reference_never_generates_staged_video(client, tmp_path):
    ctx = _approved(client, tmp_path)
    db, sid, actor, scene, run, sha, imgs, media = ctx
    with pytest.raises(LocalAnimaticError, match="confirmation"):
        stage_reference_motion_clip(
            db, series_id=sid, production_id=run,
            shot_id="S001", asset_id=actor, reference_sha256=sha,
            image_root=imgs, media_root=media,
            operator_confirmed_local_derivative_use=False,
        )
    with pytest.raises(LocalAnimaticError, match="Unknown"):
        stage_reference_motion_clip(
            db, series_id=sid, production_id=run,
            shot_id="invalid", asset_id=actor, reference_sha256=sha,
            image_root=imgs, media_root=media,
            operator_confirmed_local_derivative_use=True,
        )
    with pytest.raises(LocalAnimaticError, match="not available"):
        stage_reference_motion_clip(
            db, series_id=sid, production_id=run,
            shot_id="S001", asset_id=actor, reference_sha256="0" * 64,
            image_root=imgs, media_root=media,
            operator_confirmed_local_derivative_use=True,
        )
    assert get_staged_shot_clips(db, run, sid, media) == {}


@requires_ffmpeg
def test_foreign_or_unapproved_shot_and_other_actor_rejected(client, tmp_path):
    ctx = _approved(client, tmp_path, approve=False)
    db, sid, actor, scene, run, sha, images, media = ctx
    with pytest.raises(LocalAnimaticError, match="approvals"):
        _stage(ctx)
    assert not media.exists()
    client.post(f"/api/v1/productions/{run}/approve-script")
    with pytest.raises(LocalAnimaticError, match="approvals"):
        _stage(ctx)
    client.post(f"/api/v1/productions/{run}/approve-characters")
    foreign_sid, _, foreign_actor, _ = setup_series(client, "Other originals")
    with pytest.raises(LocalAnimaticError, match="matching series"):
        stage_reference_motion_clip(
            db, series_id=foreign_sid, production_id=run,
            shot_id="S001", asset_id=actor, reference_sha256=sha,
            image_root=images, media_root=media,
            operator_confirmed_local_derivative_use=True,
        )
    with pytest.raises(LocalAnimaticError, match="on-shot"):
        stage_reference_motion_clip(
            db, series_id=sid, production_id=run,
            shot_id="S001", asset_id=foreign_actor, reference_sha256=sha,
            image_root=images, media_root=media,
            operator_confirmed_local_derivative_use=True,
        )
    assert get_staged_shot_clips(db, run, sid, media) == {}


@requires_ffmpeg
def test_tampered_local_image_denied_before_video_staging(client, tmp_path):
    ctx = _approved(client, tmp_path)
    db, sid, actor, _, run, sha, images, media = ctx
    png = images / sid / actor / (sha + ".png")
    png.write_bytes(b"wrong image bytes")
    with pytest.raises(LocalAnimaticError, match="verification"):
        _stage(ctx)
    assert get_staged_shot_clips(db, run, sid, media) == {}


def test_motion_ui_python_syntax_even_without_streamlit_install():
    app = Path(__file__).resolve().parents[1] / "frontend" / "app.py"
    ast.parse(app.read_text(encoding="utf-8"), filename=str(app))
