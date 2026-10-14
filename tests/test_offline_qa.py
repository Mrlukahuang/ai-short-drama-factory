"""PR-14a: real FFmpeg local technical QA, no remote generation or approval."""
from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest

from drama_factory.pipeline.offline_qa import (
    OfflineQAError, _validate_srt, inspect_offline_delivery,
)
from drama_factory.pipeline.offline_render import render_approved_preview
from test_offline_render import make_production

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg/FFprobe required; mandated in offline-video CI job",
)


def _preview(client, tmp_path):
    _, production_id = make_production(client)
    assert client.post(
        f"/api/v1/productions/{production_id}/approve-script"
    ).status_code == 200
    assert client.post(
        f"/api/v1/productions/{production_id}/approve-characters"
    ).status_code == 200
    manifest = render_approved_preview(client.app.state.db, production_id,
                                       tmp_path / "out")
    return manifest, Path(manifest["mp4_path"])


@requires_ffmpeg
def test_qa_uses_real_full_mp4_decode_hash_and_caption_timing_but_never_approves(client, tmp_path):
    manifest, media = _preview(client, tmp_path)
    preview_bytes = media.read_bytes()
    subtitle_bytes = (media.parent / "captions.srt").read_bytes()
    result = inspect_offline_delivery(manifest, media)
    assert result["technical_decode_passed"] is True
    assert result["subtitle_sidecar_timing_passed"] is True
    assert result["muxed_subtitle_track_present"] is True
    assert result["shots_checked"] == 2 and result["duration_seconds"] == 2
    assert result["placeholder_visuals"] is True
    assert result["genuine_ai_video_verified"] is False
    assert result["visual_continuity_verified"] is False
    assert result["copyright_scope_verified"] is False
    assert result["operator_review_required"] is True
    assert result["publish_approved"] is False
    assert result["production_ready"] is False
    assert result["paid_provider_calls"] == result["external_write_calls"] == 0
    assert "mp4_path" not in result and "mp4_sha256" not in result
    assert media.read_bytes() == preview_bytes
    assert (media.parent / "captions.srt").read_bytes() == subtitle_bytes
    with pytest.raises(OfflineQAError, match="Human-authenticated"):
        inspect_offline_delivery(manifest, media, require_real_footage=True)


@requires_ffmpeg
def test_tampered_media_fails_hash_before_decode_or_marking_as_deliverable(client, tmp_path):
    manifest, media = _preview(client, tmp_path)
    with media.open("ab") as stream:
        stream.write(b"TAMPERED_SYNTHETIC_TRAILER")
    with pytest.raises(OfflineQAError, match="hash mismatch"):
        inspect_offline_delivery(manifest, media)
    assert manifest["paid_api_calls"] == 0


@requires_ffmpeg
def test_tampered_caption_gap_or_missing_sidecar_blocks_delivery(client, tmp_path):
    manifest, media = _preview(client, tmp_path)
    sidecar = media.parent / "captions.srt"
    original = sidecar.read_text("utf-8")
    sidecar.write_text(original.replace("00:00:01,000", "00:00:02,000", 1),
                       encoding="utf-8")
    with pytest.raises(OfflineQAError, match="gaps, overlaps"):
        inspect_offline_delivery(manifest, media)
    sidecar.unlink()
    with pytest.raises(OfflineQAError, match="subtitle sidecar"):
        inspect_offline_delivery(manifest, media)


@requires_ffmpeg
@pytest.mark.parametrize("problem", [
    "wrong_hash", "wrong_duration", "duplicate_shot",
    "wrong_placeholder", "false_paid_calls", "wrong_audio_claim",
    "wrong_media_path", "wrong_subtitle_disclosure",
])
def test_malformed_manifest_can_never_promote_preview_to_production(client, tmp_path, problem):
    manifest, media = _preview(client, tmp_path)
    tampered = copy.deepcopy(manifest)
    if problem == "wrong_hash":
        tampered["mp4_sha256"] = "0" * 64
    elif problem == "wrong_duration":
        tampered["shots"][0]["duration_seconds"] = 3
    elif problem == "duplicate_shot":
        tampered["shots"][1]["shot_id"] = tampered["shots"][0]["shot_id"]
    elif problem == "wrong_placeholder":
        tampered["placeholder_visuals"] = False
    elif problem == "false_paid_calls":
        tampered["paid_api_calls"] = 1
    elif problem == "wrong_audio_claim":
        tampered["spoken_dialogue_generated"] = True
    elif problem == "wrong_media_path":
        tampered["mp4_path"] = str(tmp_path / "not-the-right-media.mp4")
    else:
        tampered["has_subtitle_track"] = False
    with pytest.raises(OfflineQAError):
        inspect_offline_delivery(tampered, media)


def test_subtitle_sidecar_parser_enforces_monotonic_times_and_no_dialogue_leaks(tmp_path):
    captions = tmp_path / "captions.srt"
    captions.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nPrivate script content\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nSecond line\n\n",
        encoding="utf-8",
    )
    _validate_srt(captions, [1, 1])
    captions.write_text(captions.read_text().replace("00:00:01,000 --> 00:00:02,000",
                                                     "00:00:01,100 --> 00:00:02,000"),
                        encoding="utf-8")
    with pytest.raises(OfflineQAError) as exc:
        _validate_srt(captions, [1, 1])
    assert "Private script content" not in str(exc.value)
    with pytest.raises(OfflineQAError):
        _validate_srt(captions, [1])


def test_missing_fake_manifest_is_rejected_without_any_external_calls(tmp_path):
    fake = tmp_path / "missing.mp4"
    with pytest.raises(OfflineQAError):
        inspect_offline_delivery({}, fake)
