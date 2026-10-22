"""G4 source-preserving s05 redaction QA, never infer commercial approval."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import citydiscount_s05_sign_redaction as cut


def test_exact_original_sha_and_redaction_region_only():
    assert cut.ORIGINAL_SHA=="4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56"
    assert cut.BANNER_INNER==(133,196,227,236)
    assert (cut.W,cut.H)==(360,640)
    assert cut.OUTPUT.endswith("REDACTED_5s_NOT_FINAL.mp4")


def test_only_banner_patch_has_visible_pixels(tmp_path):
    path=tmp_path/"sign.png"
    cut.blank_felt_patch(path)
    img=Image.open(path)
    assert img.size==(360,640)
    a=img.getchannel("A")
    assert a.getpixel((180,215))==255
    assert a.getpixel((180,330))==0  # original mascot is NEVER overwritten
    assert a.getpixel((180,60))==0
    assert a.getpixel((15,215))==0
    assert a.getpixel((240,215))==0
    assert 0<a.getpixel((133,196))<255


def test_source_sha_mismatch_and_symlink_fail_closed(tmp_path):
    bad=tmp_path/"source.mp4"
    bad.write_bytes(b"wrong original")
    with pytest.raises(ValueError,match="SHA"):
        cut.check_source(bad)
    linked=tmp_path/"linked.mp4"
    linked.symlink_to(bad)
    with pytest.raises(ValueError,match="SHA"):
        cut.check_source(linked)


def test_source_audio_and_brand_owner_constraints_remain_explicit():
    source=(ROOT/"scripts/citydiscount_s05_sign_redaction.py").read_text()
    workflow=(ROOT/".github/workflows/citydiscount-s05-real-sign-review.yml").read_text()
    for marker in [
        '"new_ai_model_calls":0',
        '"new_source_image_external_uploads":0',
        '"commercial_release_approved":False',
        '"coin_exact_official_design_approved":False',
        '"two_digs_owner_creative_review":"NOT_VERIFIED"',
        '"original_preserved_unchanged":True',
        '"audio_is_original_media":True',
        '"-map","0:a:0?"',
        '"-c:a","copy"',
    ]:
        assert marker in source
    for marker in [
        "39596195021",
        "CityDiscount-s05-REAL-original-small-sheep-run-1080x1440-NOT-FINAL",
        "DRAMA_ENABLE_PAID_GENERATION: 'NO'",
        "retention-days: 7",
        "s05_BEFORE_AFTER_2_75s.jpg"
    ]:
        assert marker in workflow
    assert "secrets." not in workflow
    assert "GEMINI_API_KEY" not in workflow
    assert "generate_video" not in workflow
