"""G4: genuine existing Omni s05 brand coin is only local review, never new AI."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import citydiscount_s05_coin_logo_review as coin


def test_exact_historical_originals_and_local_only_brand_review():
    assert coin.CLEAN_SHA=="7a4a7e5f261a641dd7035698a5aad3a9a331bf51a70c5ccd7565677a2694a652"
    assert coin.END_SHA=="273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1"
    assert coin.OUTPUT.endswith("LOCAL_REVIEW_NOT_FINAL.mp4")


def test_coin_glyph_starts_only_after_coin_appears_and_follows_shot():
    assert coin.coin_position(2.6)==(0.,0.,0.)
    assert coin.coin_position(3.10)[2]==0
    assert coin.coin_position(3.75)[1]>520
    assert coin.coin_position(4.75)[1]<465
    assert max(p[3] for p in coin.COIN_KEYS)<=1.
    assert len(coin.COIN_KEYS)>=10


def test_tampered_or_symlink_source_rejected(tmp_path):
    original=tmp_path/"s05.mp4"
    original.write_bytes(b"wrong movie bytes")
    with pytest.raises(ValueError,match="SHA"):
        coin.canonical(original,coin.CLEAN_SHA)
    symlink=tmp_path/"link.mp4"
    symlink.symlink_to(original)
    with pytest.raises(ValueError,match="SHA"):
        coin.canonical(symlink,coin.END_SHA)


def test_real_footage_and_creative_release_gates_are_never_promoted():
    src=(ROOT/"scripts/citydiscount_s05_coin_logo_review.py").read_text()
    for token in ('"new_model_calls":0','"new_image_external_transfers":0',
                  '"coin_final_owner_brand_qa_pass":False',
                  '"human_2_digs_qa_pass":False',
                  '"publish_approved":False',
                  '"full_60s_film_uses_this_new_coin_version":False',
                  '"new_real_scene_generated":False'):
        assert token in src
    assert "model_submission_allowed=True" not in src
    assert "GEMINI_API_KEY" not in src
    assert "extracted dark-green CD glyph from original official VIDEO endcard" in src


def test_actions_actual_old_media_only_and_distinct_review_artifact():
    wf=(ROOT/".github/workflows/citydiscount-s05-coin-logo-local-review.yml").read_text()
    for token in ("39747140543","39709324093",
                  "CityDiscount-s05-REAL-OMNI-SIGN-REDACTED-5s-REVIEW-NOT-FINAL",
                  "CityDiscount-rev5-owner-globe-to-official-logo-5s-ENDCARD-NOT-FINAL",
                  "DRAMA_ENABLE_PAID_GENERATION: 'NO'",
                  "CityDiscount_s05_REAL_OMNI_CLEAN_SIGN_CD_COIN_LOCAL_REVIEW_NOT_FINAL.mp4",
                  "s05_real_coins_5_frames_review.png",
                  "retention-days: 7"):
        assert token in wf
    assert "secrets." not in wf
