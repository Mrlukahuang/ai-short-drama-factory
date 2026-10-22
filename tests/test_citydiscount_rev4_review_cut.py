"""G4/R4.4 rev4 real-existing-media 60s technical cut; never a new-model pass."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_citydiscount_rev4_review_cut as cut


def test_rev4_exactly_twelve_five_second_3_4_shots_and_false_permissions():
    script = cut.boards.source()
    cut.assert_story(script)
    assert script["format"]["total_duration_seconds"] == 60
    assert [x["shot_id"] for x in script["shots"]] == [
        f"s{i:02d}" for i in range(1, 13)
    ]
    assert cut.LIVE_SOURCE_SHOTS == {"s02", "s05"}
    assert cut.ENVIRONMENT_ONLY == {"s03"}
    assert len(set(f"s{i:02d}" for i in range(1, 13))
               - cut.LIVE_SOURCE_SHOTS) == 10


@pytest.mark.parametrize("shot,field", [
    ("s02", "source_video_sha256"), ("s05", "source_mp4_sha256")
])
def test_real_history_requires_both_original_bytes_and_original_receipt(
        tmp_path, shot, field):
    video = tmp_path / (shot + ".mp4")
    video.write_bytes(b"synthetic-not-real-media")
    receipt = tmp_path / (shot + ".json")
    doc = {"shot_id": shot, "model_calls": 1,
           "output_media": "real_omni_video_downloaded",
           "source_video_real_model": True, "publication_approved": False,
           "actual_fee_usd": None,
           field: hashlib.sha256(video.read_bytes()).hexdigest()}
    receipt.write_text(json.dumps(doc), encoding="utf-8")
    result = cut.check_live_source(shot, video, receipt)
    assert result["provider_invoice_verified"] is False
    assert result["creative_review_approved"] is False
    assert result["source_run"] == cut.SOURCE_IDS[shot][0]
    video.write_bytes(b"changed")
    with pytest.raises(ValueError, match="mismatch"):
        cut.check_live_source(shot, video, receipt)


def test_fake_receipt_not_accepted_as_real(tmp_path):
    video = tmp_path / "s02.mp4"
    video.write_bytes(b"placeholder")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({
        "shot_id": "s02", "model_calls": 0, "source_video_real_model": False,
        "source_video_sha256": cut.digest(video),
        "output_media": "not_generated", "publication_approved": False,
        "actual_fee_usd": None,
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch"):
        cut.check_live_source("s02", video, receipt)


def test_historical_city_plate_is_not_the_new_rev4_character_shot(tmp_path):
    media = tmp_path / "city.mp4"
    media.write_bytes(b"wrong historic city bytes")
    with pytest.raises(ValueError, match="SHA"):
        cut.check_city_source(media)


def test_workflow_is_immutable_reuse_with_no_paid_provider_call():
    workflow = (ROOT / ".github/workflows/citydiscount-rev4-60s-review-cut.yml").read_text("utf-8")
    script = (ROOT / "scripts/build_citydiscount_rev4_review_cut.py").read_text("utf-8")
    for token in ("39583047905", "39596195021", "39441034483",
                  "s02_raw_omni_9x16.mp4", "s05_raw_omni_9x16.mp4",
                  "DRAMA_ENABLE_PAID_GENERATION: 'NO'",
                  "actions: read", "CityDiscount_rev4_60s_3x4_TECHNICAL_NOT_FINAL.mp4",
                  "existing_real_rev4_character_motion_shots"):
        assert token in workflow
    assert "GEMINI_API_KEY" not in workflow
    assert "secrets." not in workflow
    assert "generate_approved_reference_envelope" not in script
    assert "release_status" in script and "blocked" in script
    assert "all_real_12_shot_episode" in script
    assert "historical_google_invoice_usd" in script
    assert '"g4_exited": False' in script
    assert 'silent AAC TECHNICAL placeholder' in script
