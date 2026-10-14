"""Real local FFmpeg smoke tests; never call external model providers."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from drama_factory.pipeline.offline_demo import build_offline_demo
from drama_factory.pipeline.offline_render import (
    PreviewError, inspect_mp4, render_approved_preview,
)


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe required for media integration",
)


def make_production(client, *, valid_duration=True):
    series = client.post("/api/v1/projects", json={
        "title": "End-to-end test series", "premise": "Test safe local preview",
    }).json()["series_id"]
    episode = client.post(f"/api/v1/projects/{series}/episodes", json={
        "title": "Episode one", "episode_number": 1,
        "target_duration_seconds": 2 if valid_duration else 3,
        "shots": [
            {"shot_id": "shot-1", "duration_seconds": 1,
             "visual_description": "Lead hears a knock", "dialogue": ["Who is there?"]},
            {"shot_id": "shot-2", "duration_seconds": 1,
             "visual_description": "Door opens", "dialogue": ["Hello"]},
        ],
    })
    assert episode.status_code == 201
    production = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
    ).json()["production_id"]
    return series, production


@requires_ffmpeg
def test_offline_preview_requires_existing_approval_gates(client, tmp_path):
    _, run = make_production(client)
    with pytest.raises(PreviewError, match="approvals"):
        render_approved_preview(client.app.state.db, run, tmp_path / "outputs")
    assert not (tmp_path / "outputs").exists()
    client.post(f"/api/v1/productions/{run}/approve-script")
    with pytest.raises(PreviewError, match="approvals"):
        render_approved_preview(client.app.state.db, run, tmp_path / "outputs")
    client.post(f"/api/v1/productions/{run}/approve-characters")
    manifest = render_approved_preview(client.app.state.db, run, tmp_path / "outputs")
    assert manifest["paid_api_calls"] == 0
    assert manifest["placeholder_visuals"] is True
    assert manifest["spoken_dialogue_generated"] is False
    assert manifest["has_subtitle_track"] is True
    assert manifest["media"]["subtitle_codec"] == "mov_text"
    assert all(not shot["cached"] for shot in manifest["shots"])
    assert Path(manifest["mp4_path"]).is_file()
    assert inspect_mp4(Path(manifest["mp4_path"]), 2)["audio_codec"] == "aac"
    record = client.app.state.db.one("SELECT status FROM productions WHERE id=?", (run,))
    assert record["status"] == "offline_preview_finished"


@requires_ffmpeg
def test_shot_level_reuse_and_targeted_corruption_repair(client, tmp_path):
    _, run = make_production(client)
    client.post(f"/api/v1/productions/{run}/approve-script")
    client.post(f"/api/v1/productions/{run}/approve-characters")
    folder = tmp_path / "deliver"
    initial = render_approved_preview(client.app.state.db, run, folder)
    again = render_approved_preview(client.app.state.db, run, folder)
    assert [x["cached"] for x in again["shots"]] == [True, True]
    assert initial["mp4_sha256"] == again["mp4_sha256"]
    working = Path(initial["mp4_path"]).parent
    first_clip = working / "clips" / initial["shots"][0]["clip_name"]
    first_clip.write_bytes(b"corrupt")
    repaired = render_approved_preview(client.app.state.db, run, folder)
    assert [x["cached"] for x in repaired["shots"]] == [False, True]
    assert repaired["mp4_sha256"] == initial["mp4_sha256"]
    assert json.loads((working / "manifest.json").read_text())["paid_api_calls"] == 0


@requires_ffmpeg
def test_timeline_mismatch_fails_without_claiming_render_success(client, tmp_path):
    _, run = make_production(client, valid_duration=False)
    client.post(f"/api/v1/productions/{run}/approve-script")
    client.post(f"/api/v1/productions/{run}/approve-characters")
    with pytest.raises(PreviewError, match="Shot durations"):
        render_approved_preview(client.app.state.db, run, tmp_path / "out")
    db_row = client.app.state.db.one("SELECT status,result_json FROM productions WHERE id=?", (run,))
    assert db_row["status"] == "ready_for_video_generation"
    assert db_row["result_json"] is None


@requires_ffmpeg
def test_entire_real_api_to_mp4_demo(tmp_path):
    report = build_offline_demo(tmp_path / "demo")
    out = tmp_path / "demo"
    assert (out / "demo.mp4").is_file()
    assert (out / "manifest.json").is_file()
    assert report["media"]["subtitle_codec"] == "mov_text"
    assert report["media"]["width"] == 360 and report["media"]["height"] == 640
    assert len(report["shots"]) == 3
    assert report["paid_api_calls"] == 0
    assert report["media"]["duration_seconds"] == pytest.approx(6, abs=0.6)


@requires_ffmpeg
def test_preview_state_records_independent_qa_before_marking_preview_complete(client, tmp_path):
    _, production = make_production(client)
    client.post(f"/api/v1/productions/{production}/approve-script")
    client.post(f"/api/v1/productions/{production}/approve-characters")
    manifest = render_approved_preview(client.app.state.db, production, tmp_path / "render")
    qa = manifest["technical_qa"]
    assert qa["technical_decode_passed"] is True
    assert qa["subtitle_sidecar_timing_passed"] is True
    assert qa["video_sha256_matches_manifest"] is True
    assert qa["shots_checked"] == 2
    assert qa["paid_provider_calls"] == 0
    assert qa["genuine_ai_video_verified"] is False
    assert qa["operator_review_required"] is True
    assert qa["publish_approved"] is False
    assert qa["production_ready"] is False
    record = client.app.state.db.one(
        "SELECT status,result_json FROM productions WHERE id=?", (production,)
    )
    assert record["status"] == "offline_preview_finished"
    assert json.loads(record["result_json"])["technical_qa"] == qa
    saved = json.loads((Path(manifest["mp4_path"]).parent / "manifest.json").read_text())
    assert saved["technical_qa"] == qa


@requires_ffmpeg
def test_preview_qa_failure_quarantines_unverified_mp4_before_db_commit(client, tmp_path, monkeypatch):
    from drama_factory.pipeline import offline_qa
    _, production = make_production(client)
    client.post(f"/api/v1/productions/{production}/approve-script")
    client.post(f"/api/v1/productions/{production}/approve-characters")

    real_inspector = offline_qa.inspect_offline_delivery
    def force_qa_failure(*_args, **_kwargs):
        raise offline_qa.OfflineQAError("Synthetic QA failure (test only)")

    monkeypatch.setattr(offline_qa, "inspect_offline_delivery", force_qa_failure)
    working = tmp_path / "render"
    with pytest.raises(PreviewError, match="failed technical QA"):
        render_approved_preview(client.app.state.db, production, working)
    row = client.app.state.db.one(
        "SELECT status,result_json FROM productions WHERE id=?", (production,)
    )
    assert row["status"] == "ready_for_video_generation"
    assert row["result_json"] is None
    assert not list(working.rglob("manifest.json"))

    # After independent QA is restored, locally cached clips can be used
    # without another paid generation or externally submitted provider task.
    monkeypatch.setattr(offline_qa, "inspect_offline_delivery", real_inspector)
    recovered = render_approved_preview(client.app.state.db, production, working)
    assert recovered["technical_qa"]["technical_decode_passed"] is True
    assert all(shot["cached"] for shot in recovered["shots"])
    assert recovered["paid_api_calls"] == 0


@requires_ffmpeg
def test_valid_but_wrong_mp4_cache_is_rebuilt_from_original_shot(client, tmp_path):
    _, production = make_production(client)
    client.post(f"/api/v1/productions/{production}/approve-script")
    client.post(f"/api/v1/productions/{production}/approve-characters")
    root = tmp_path / "cache-reuse"
    initial = render_approved_preview(client.app.state.db, production, root)
    clips_dir = Path(initial["mp4_path"]).parent / "clips"
    clip_a = clips_dir / initial["shots"][0]["clip_name"]
    clip_b = clips_dir / initial["shots"][1]["clip_name"]
    hash_before = initial["shots"][0]["clip_sha256"]
    assert hash_before != initial["shots"][1]["clip_sha256"]
    assert (clips_dir / (clip_a.name + ".sha256")).read_text().strip() == hash_before
    # Replace A with another VALID, same-length MP4. Probing codec/duration
    # would miss this. Content hash must reject that cache entry.
    shutil.copyfile(clip_b, clip_a)
    assert inspect_mp4(clip_a, 1)["video_codec"] == "h264"
    rebuilt = render_approved_preview(client.app.state.db, production, root)
    assert [shot["cached"] for shot in rebuilt["shots"]] == [False, True]
    assert rebuilt["shots"][0]["clip_sha256"] == hash_before
    assert rebuilt["mp4_sha256"] == initial["mp4_sha256"]
    assert rebuilt["technical_qa"]["video_sha256_matches_manifest"] is True
    assert rebuilt["paid_api_calls"] == 0


@requires_ffmpeg
def test_missing_cache_digest_is_never_reused_even_when_mp4_decodes(client, tmp_path):
    _, production = make_production(client)
    client.post(f"/api/v1/productions/{production}/approve-script")
    client.post(f"/api/v1/productions/{production}/approve-characters")
    root = tmp_path / "cache-missing-digest"
    original = render_approved_preview(client.app.state.db, production, root)
    clip_dir = Path(original["mp4_path"]).parent / "clips"
    path = clip_dir / original["shots"][0]["clip_name"]
    marker = clip_dir / (path.name + ".sha256")
    marker.unlink()
    assert inspect_mp4(path, 1)["video_codec"] == "h264"
    checked = render_approved_preview(client.app.state.db, production, root)
    assert [x["cached"] for x in checked["shots"]] == [False, True]
    assert marker.is_file()
    assert marker.read_text("ascii").strip() == checked["shots"][0]["clip_sha256"]


@requires_ffmpeg
def test_delivery_qa_rejects_modified_valid_shot_clip_after_manifest(client, tmp_path):
    from drama_factory.pipeline.offline_qa import OfflineQAError, inspect_offline_delivery
    _, production = make_production(client)
    client.post(f"/api/v1/productions/{production}/approve-script")
    client.post(f"/api/v1/productions/{production}/approve-characters")
    result = render_approved_preview(client.app.state.db, production, tmp_path / "out")
    path = Path(result["mp4_path"])
    clip_dir = path.parent / "clips"
    source = clip_dir / result["shots"][1]["clip_name"]
    victim = clip_dir / result["shots"][0]["clip_name"]
    shutil.copyfile(source, victim)  # correct codec/length, wrong visual content
    assert inspect_mp4(victim, 1)["audio_codec"] == "aac"
    with pytest.raises(OfflineQAError, match="clip no longer matches"):
        inspect_offline_delivery(result, path)


@pytest.mark.parametrize("invalid", [0, 2, 30, 59, 61, True, "60"])
def test_offline_demo_rejects_unsupported_duration_before_any_side_effect(tmp_path, invalid):
    root = tmp_path / "never-created"
    with pytest.raises(ValueError, match="supports only 6s or 60s"):
        build_offline_demo(root, duration_seconds=invalid)
    assert not root.exists()


@requires_ffmpeg
def test_synthetic_timing_tones_generate_actual_mixed_mp4_without_fake_voice_claims(tmp_path):
    root = tmp_path / "two-stem-offline-test"
    doc = build_offline_demo(
        root, duration_seconds=6, with_synthetic_audio_mix=True,
    )
    assert (root / "demo.mp4").is_file()
    assert (root / "manifest.json").is_file()
    assert doc["synthetic_test_tone_stems"] is True
    assert doc["local_dialogue_audio_supplied"] is True
    assert doc["local_music_audio_supplied"] is True
    assert doc["voice_license_independently_verified"] is False
    assert doc["spoken_dialogue_generated"] is False
    assert doc["paid_api_calls"] == 0
    assert doc["offline_audio_mix"]["real_tts_generated"] is False
    assert doc["offline_audio_mix"]["locally_supplied_dialogue"] is True
    assert doc["offline_audio_mix"]["locally_supplied_music"] is True
    assert doc["technical_qa"]["technical_decode_passed"] is True
    assert doc["technical_qa"]["publish_approved"] is False
    assert doc["technical_qa"]["production_ready"] is False
    assert inspect_mp4(root / "demo.mp4", 6)["subtitle_codec"] == "mov_text"
    assert json.loads((root / "manifest.json").read_text("utf-8"))["synthetic_test_tone_stems"] is True


@pytest.mark.parametrize("bad", ["true", None, 1, 0, []])
def test_synthetic_audio_demo_flag_must_be_explicit_boolean_before_io(tmp_path, bad):
    root = tmp_path / "never-created-by-flag"
    with pytest.raises(ValueError, match="audio mix flag"):
        build_offline_demo(root, with_synthetic_audio_mix=bad)
    assert not root.exists()
