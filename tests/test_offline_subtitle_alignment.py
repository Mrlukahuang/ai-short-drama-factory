"""PR-15d: SRT follows approved speaker timings, not full-shot text."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from drama_factory.pipeline.offline_demo import build_offline_demo
from drama_factory.pipeline.offline_qa import (
    OfflineQAError, inspect_offline_delivery,
    _validate_approved_subtitle_schedule,
)

ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Mandatory offline-video CI includes real FFmpeg",
)


@ffmpeg_required
def test_cast_subtitles_follow_reviewed_speaker_slots_not_full_shot(tmp_path):
    report = build_offline_demo(
        tmp_path / "approved-cues", duration_seconds=6,
        with_fake_cast_timeline=True,
    )
    expected = [(0,1),(1,2),(2,3),(4,6)]
    schedule = report["subtitle_schedule"]
    assert [(x["start_second"],x["end_second"]) for x in schedule] == expected
    assert len(schedule) == 4
    assert report["technical_qa"]["approved_subtitle_schedule_verified"] is True
    assert report["technical_qa"]["subtitle_cues_checked"] == 4
    srt = (Path(report["mp4_path"]).parent / "captions.srt").read_text("utf-8")
    assert "00:00:00,000 --> 00:00:01,000" in srt
    assert "00:00:01,000 --> 00:00:02,000" in srt
    assert "00:00:02,000 --> 00:00:03,000" in srt
    assert "00:00:04,000 --> 00:00:06,000" in srt
    assert "00:00:03,000 --> 00:00:04,000" not in srt
    assert "You found me." in srt
    assert report["technical_qa"]["publish_approved"] is False
    assert report["real_tts_generated"] is False
    assert report["paid_api_calls"] == 0


@ffmpeg_required
def test_modified_but_valid_srt_text_is_rejected_by_hash_qa(tmp_path):
    report = build_offline_demo(
        tmp_path / "text-tamper", duration_seconds=6,
        with_fake_cast_timeline=True,
    )
    src = Path(report["mp4_path"]).parent / "captions.srt"
    original = src.read_text("utf-8")
    assert "You found me." in original
    src.write_text(original.replace("You found me.", "Forged dialogue"),
                   encoding="utf-8")
    with pytest.raises(OfflineQAError, match="text hash mismatch"):
        inspect_offline_delivery(report, Path(report["mp4_path"]))


@ffmpeg_required
def test_manifest_time_edit_and_srt_gap_edit_both_fail_closed(tmp_path):
    report = build_offline_demo(
        tmp_path / "time-tamper", duration_seconds=6,
        with_fake_cast_timeline=True,
    )
    path = Path(report["mp4_path"])
    forged = deepcopy(report)
    forged["subtitle_schedule"][1]["start_second"] = 0
    with pytest.raises(OfflineQAError, match="gaps, overlaps"):
        inspect_offline_delivery(forged, path)
    sidecar = path.parent / "captions.srt"
    original = sidecar.read_text("utf-8")
    sidecar.write_text(
        original.replace("00:00:01,000 --> 00:00:02,000",
                         "00:00:00,000 --> 00:00:02,000"),
        encoding="utf-8",
    )
    with pytest.raises(OfflineQAError, match="gaps, overlaps"):
        inspect_offline_delivery(report, path)


def test_srt_schedule_rejects_invalid_metadata_without_private_text(tmp_path):
    path = tmp_path / "valid-format.srt"
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nPrivate approved dialogue\n\n",
        encoding="utf-8",
    )
    cases = [
        [],
        [{"start_second": True, "end_second": 1, "text_sha256": "0"*64}],
        [{"start_second": 0, "end_second": 8, "text_sha256": "0"*64}],
        [{"start_second": 0, "end_second": 1, "text_sha256": "bad"}],
    ]
    for schedule in cases:
        with pytest.raises(OfflineQAError) as exc:
            _validate_approved_subtitle_schedule(path, schedule, 2)
        assert "Private approved dialogue" not in str(exc.value)
