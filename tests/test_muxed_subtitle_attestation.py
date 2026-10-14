"""PR-15e: real MP4 mov_text must equal the reviewed SRT it claims to use."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

from drama_factory.pipeline.offline_demo import build_offline_demo
from drama_factory.pipeline.offline_qa import (
    OfflineQAError, _subtitle_items, _verify_muxed_subtitles,
    inspect_offline_delivery,
)
from drama_factory.pipeline.offline_render import inspect_mp4


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Dedicated offline-video CI requires actual FFmpeg",
)


def _repackage_with_forged_mov_text(original: Path, forged_srt: Path, dest: Path):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror",
         "-nostdin", "-y", "-i", str(original), "-i", str(forged_srt),
         "-map", "0:v:0", "-map", "0:a:0", "-map", "1:s:0",
         "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
         "-movflags", "+faststart", str(dest)],
        capture_output=True, check=True, timeout=60,
    )
    return dest


@requires_ffmpeg
def test_actual_two_actor_mp4_embedded_text_and_times_match_reviewed_srt(tmp_path):
    report = build_offline_demo(
        tmp_path / "approved-mux", duration_seconds=6,
        with_fake_cast_timeline=True,
    )
    media = Path(report["mp4_path"])
    assert report["technical_qa"]["muxed_subtitle_content_verified"] is True
    assert report["technical_qa"]["muxed_subtitle_cues_checked"] == 4
    assert report["technical_qa"]["subtitle_cues_checked"] == 4
    assert _verify_muxed_subtitles(media, media.parent / "captions.srt") == 4
    assert report["technical_qa"]["publish_approved"] is False
    assert report["paid_api_calls"] == 0


@requires_ffmpeg
@pytest.mark.parametrize("forgery", ["text", "timing"])
def test_replaced_embedded_track_is_rejected_even_if_mp4_hash_is_resigned(tmp_path, forgery):
    report = build_offline_demo(
        tmp_path / "malicious-remux", duration_seconds=6,
        with_fake_cast_timeline=True,
    )
    original = Path(report["mp4_path"])
    reviewed_srt = original.parent / "captions.srt"
    genuine = reviewed_srt.read_text("utf-8")
    if forgery == "text":
        assert "You found me." in genuine
        malicious = genuine.replace("You found me.", "Unreviewed voice transcript")
    else:
        malicious = genuine.replace(
            "00:00:01,000 --> 00:00:02,000",
            "00:00:01,000 --> 00:00:03,000",
        )
        assert malicious != genuine
    forged_srt = original.parent / "forged-embedded-only.srt"
    forged_srt.write_text(malicious, encoding="utf-8")
    forged_mp4 = _repackage_with_forged_mov_text(
        original, forged_srt, original.parent / "forged-caption.mp4",
    )
    doctored = deepcopy(report)
    doctored["mp4_path"] = str(forged_mp4)
    doctored["mp4_sha256"] = hashlib.sha256(forged_mp4.read_bytes()).hexdigest()
    doctored["media"] = inspect_mp4(forged_mp4, 6)
    # Checks for the external SRT and media fingerprint BOTH still pass.
    # Only independent actual mov_text extraction detects the mismatch.
    with pytest.raises(OfflineQAError, match="Embedded MP4 subtitles differ"):
        inspect_offline_delivery(doctored, forged_mp4)
    assert _verify_muxed_subtitles(original, reviewed_srt) == 4


@requires_ffmpeg
def test_six_second_legacy_preview_also_decodes_embedded_subtitles(tmp_path):
    report = build_offline_demo(tmp_path / "legacy-mp4", duration_seconds=6)
    assert report["technical_qa"]["muxed_subtitle_content_verified"] is True
    assert report["technical_qa"]["muxed_subtitle_cues_checked"] == 3
    assert report["technical_qa"]["approved_subtitle_schedule_verified"] is True


def test_decoded_subtitle_parser_rejects_private_untrusted_payload_without_leaking():
    for wrong in (
        "",
        "1\n00:00:01,000 --> 00:00:01,000\nPrivate words",
        "1\n00:00:00,000 --> 00:00:01,000\nPrivate words\n\n"
        "2\n00:00:00,000 --> 00:00:02,000\nPrivate words",
        "1\n00:00:00,000 --> 00:00:01,000\n",
    ):
        with pytest.raises(OfflineQAError) as exc:
            _subtitle_items(wrong)
        assert "Private" not in str(exc.value)
