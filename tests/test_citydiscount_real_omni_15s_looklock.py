"""A quality benchmark is only genuine old media, never new paid/generated shots."""
from __future__ import annotations
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import build_citydiscount_real_omni_15s_looklock as film


def test_sources_historical_real_video_and_exact_owner_logo_are_pinned():
    assert film.EXPECTED=={
        "s02":"a8a25ba43e5e8659d9c5528d685c69e8e0f991b990a48bf77c5c2be4fcfef80c",
        "s05":"4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56",
        "s12":"273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1",
    }
    assert film.OUTPUT=="CityDiscount_REAL_OMNI_LAMB_LOOK_LOCK_15s_NOT_FINAL.mp4"


def test_wrong_or_tampered_source_is_rejected_fail_closed(tmp_path):
    f=tmp_path/"old_movie.mp4"
    f.write_bytes(b"Not a genuine source")
    with pytest.raises(ValueError,match="SHA"):
        film.checked(f,film.EXPECTED["s02"])
    g=tmp_path/"linked.mp4"
    g.symlink_to(f)
    with pytest.raises(ValueError):
        film.checked(g,film.EXPECTED["s05"])


def test_geometry_is_not_faked_3by4_stretch_and_rights_do_not_open():
    # 360x640 source at height 1440 is 810 wide; the extra sides are
    # source-derived background only, never stretching the owner's face.
    assert "scale=810:1440" in film.NONSTRETCHED_FILTER
    assert "gblur=sigma=26" in film.NONSTRETCHED_FILTER
    assert "overlay=(W-w)/2:0" in film.NONSTRETCHED_FILTER
    source=(ROOT/"scripts/build_citydiscount_real_omni_15s_looklock.py").read_text()
    assert '"new_paid_model_calls":0' in source
    assert '"new_real_model_shots_generated":0' in source
    assert '"approved_for_publication":False' in source
    assert '"human_identity_style_qa":"NOT_VERIFIED"' in source
    assert '"actual_full_rev5_shots_completed":False' in source
    assert '"owner_rights_for_new_source_uploads":"NOT_AUTHORIZED"' in source
    assert "GEMINI_API_KEY" not in source
    assert '"closing_copy":"都市折扣🌟，您的省钱助手小羊薅薅。"' in source


def test_runner_reuses_exact_old_artifacts_and_never_passes_secrets():
    workflow=(ROOT/".github/workflows/citydiscount-real-omni-15s-looklock.yml").read_text()
    for token in ("39583047905","39596195021","39709324093",
                  "CityDiscount-s02-REAL-original-small-sheep-run-1080x1440-NOT-FINAL",
                  "CityDiscount-s05-REAL-original-small-sheep-run-1080x1440-NOT-FINAL",
                  "CityDiscount-rev5-owner-globe-to-official-logo-5s-ENDCARD-NOT-FINAL",
                  "DRAMA_ENABLE_PAID_GENERATION: 'NO'",
                  "retention-days: 7"):
        assert token in workflow
    assert "secrets." not in workflow
    assert "generate_real_omni" not in workflow
    assert "CityDiscount_REAL_OMNI_LAMB_LOOK_LOCK_15s_NOT_FINAL.mp4" in workflow
