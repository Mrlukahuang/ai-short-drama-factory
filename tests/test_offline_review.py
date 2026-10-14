"""PR-07b1: local Streamlit playback requires owner + full reinspection.

Only original, synthetic offline-test content is rendered in these tests.
No network provider, credentials or real production assets are used.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from drama_factory.pipeline.offline_render import render_approved_preview
from drama_factory.pipeline.offline_review import (
    LocalReviewDenied, load_local_offline_review,
)
from test_offline_render import make_production


needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="local FFmpeg is required",
)


def _finished(client, tmp_path):
    series, run = make_production(client)
    assert client.post(f"/api/v1/productions/{run}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{run}/approve-characters").status_code == 200
    root = tmp_path / "review-artifacts"
    manifest = render_approved_preview(client.app.state.db, run, root)
    return series, run, root, manifest


@needs_ffmpeg
def test_review_can_play_only_persisted_qa_passed_original_local_mp4(client, tmp_path):
    series, run, root, manifest = _finished(client, tmp_path)
    before = client.app.state.db.one(
        "SELECT status,result_json,updated_at FROM productions WHERE id=?", (run,),
    )
    report = load_local_offline_review(
        client.app.state.db, run, root, series_id=series,
    )
    assert report["technical_qa_passed"] is True
    assert report["verified_sha256"] == manifest["mp4_sha256"]
    assert Path(report["preview_path"]).is_file()
    assert [s["shot_id"] for s in report["shots"]] == ["shot-1", "shot-2"]
    assert all(s["source_kind"] == "placeholder" for s in report["shots"])
    assert report["placeholder_visuals"] is True
    assert report["actual_local_media_clips"] == 0
    assert report["paid_model_requests_by_review"] == 0
    assert report["real_ai_footage_verified"] is False
    assert report["commercial_rights_verified"] is False
    assert report["publish_approved"] is False
    assert "Who is there?" not in str(report)
    assert "Hello" not in str(report)
    assert client.app.state.db.one(
        "SELECT status,result_json,updated_at FROM productions WHERE id=?", (run,),
    ) == before


@needs_ffmpeg
def test_unapproved_preview_and_wrong_series_never_play(client, tmp_path):
    series, run = make_production(client)
    with pytest.raises(LocalReviewDenied, match="Finished"):
        load_local_offline_review(
            client.app.state.db, run, tmp_path / "none", series_id=series,
        )
    series, run, root, _ = _finished(client, tmp_path)
    other, _ = make_production(client)
    with pytest.raises(LocalReviewDenied, match="selected series"):
        load_local_offline_review(client.app.state.db, run, root, series_id=other)
    with pytest.raises(LocalReviewDenied):
        load_local_offline_review(
            client.app.state.db, "../" + run, root, series_id=series,
        )


@needs_ffmpeg
def test_different_render_root_and_manifest_mismatch_never_play(client, tmp_path):
    series, run, root, doc = _finished(client, tmp_path)
    with pytest.raises(LocalReviewDenied):
        load_local_offline_review(
            client.app.state.db, run, tmp_path / "unrelated", series_id=series,
        )
    path = Path(doc["mp4_path"]).parent / "manifest.json"
    original = path.read_bytes()
    try:
        payload = json.loads(original)
        payload["paid_api_calls"] = 1
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(LocalReviewDenied):
            load_local_offline_review(client.app.state.db, run, root, series_id=series)
    finally:
        path.write_bytes(original)
    assert load_local_offline_review(
        client.app.state.db, run, root, series_id=series,
    )["technical_qa_passed"]


@needs_ffmpeg
def test_sha_changed_after_review_rejected_even_if_mp4_looks_valid(client, tmp_path):
    series, run, root, doc = _finished(client, tmp_path)
    final = Path(doc["mp4_path"])
    # Corrupt file AFTER a prior green QA: it is never trusted on its own.
    with final.open("ab") as out:
        out.write(b"offline-test-tail")
    with pytest.raises(LocalReviewDenied, match="QA"):
        load_local_offline_review(client.app.state.db, run, root, series_id=series)


@needs_ffmpeg
def test_symlinked_manifest_and_workdir_not_followed(client, tmp_path):
    series, run, root, doc = _finished(client, tmp_path)
    saved = Path(doc["mp4_path"]).parent / "manifest.json"
    backup = saved.with_suffix(".original")
    saved.rename(backup)
    try:
        saved.symlink_to(backup)
        with pytest.raises(LocalReviewDenied, match="linked"):
            load_local_offline_review(client.app.state.db, run, root, series_id=series)
    finally:
        saved.unlink()
        backup.rename(saved)
    assert load_local_offline_review(
        client.app.state.db, run, root, series_id=series,
    )["technical_qa_passed"]


@needs_ffmpeg
def test_db_saved_review_receipt_tampered_blocks_playback(client, tmp_path):
    series, run, root, doc = _finished(client, tmp_path)
    original = client.app.state.db.one(
        "SELECT result_json FROM productions WHERE id=?", (run,),
    )["result_json"]
    try:
        tampered = json.loads(original)
        tampered["production_id"] = "run_" + "0"*14
        client.app.state.db.exec(
            "UPDATE productions SET result_json=? WHERE id=?",
            (json.dumps(tampered), run),
        )
        with pytest.raises(LocalReviewDenied):
            load_local_offline_review(client.app.state.db, run, root, series_id=series)
    finally:
        client.app.state.db.exec(
            "UPDATE productions SET result_json=? WHERE id=?", (original, run),
        )
