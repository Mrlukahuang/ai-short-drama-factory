"""Rev5 full 60s moving camera PREVIS: no fabricated real animation or cost."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import build_citydiscount_rev5_60s_moving_previs as cut


def test_exact_rev5_storyboard_with_real_source_sha_and_no_release():
    plan, logo, digest=cut.endcard.load()
    assert plan["endcard"]["closing_copy"]=="都市折扣🌟，您的省钱助手小羊薅薅。"
    assert cut.SOURCE_REV4_SHA=="e65d01356dcc977ab40c6cfea2ed479b812b8d16ffae6ccc41bfde8ce430288e"
    assert cut.SOURCE_END_SHA=="273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1"
    assert cut.REAL_IDS==("s02","s05")
    assert "s03" in cut.DRAWN_IDS and "s11" in cut.DRAWN_IDS
    assert set(cut.REAL_IDS+cut.DRAWN_IDS+("s12",))==set(f"s{i:02}" for i in range(1,13))
    assert plan["locked"]["publish_approved"] is False


def test_two_d_camera_zoom_is_a_2d_crop_not_an_AI_model_call():
    m=cut.mini_map()
    assert m.size==(540,720)
    first=cut.zoom(m,1.0)
    close=cut.zoom(m,3.8)
    assert first.tobytes()!=close.tobytes()
    assert cut.ease(0)==0 and cut.ease(1)==1


def test_illustrated_2d_transition_frames_real_source_sprite(monkeypatch):
    from PIL import ImageFont
    monkeypatch.setattr(cut.boards, "font_family",
                        lambda s,bold=False:ImageFont.load_default(size=s))
    roles,logo,sha=cut.boards.owned_assets()
    ctx={"map":cut.mini_map(),"front":roles["front"].convert("RGBA")}
    for k in ("home","supermarket","cafe","shopping","family"):
        ctx[k]=cut.street(k)
    for sid,t in (("s03",4.8),("s04",0.0),("s04",4.8),
                  ("s10",0),("s10",4.9),("s11",3.4),("s11",4.9),
                  ("s06",2.5),("s07",2.5),("s08",2.5),("s09",2.5)):
        im=cut.movie_frame(sid,t,ctx)
        assert im.size==(540,720)
        assert im.mode=="RGB"
    assert cut.movie_frame("s03",0,ctx).tobytes()!=cut.movie_frame("s03",4.8,ctx).tobytes()
    assert cut.movie_frame("s10",0,ctx).tobytes()!=cut.movie_frame("s10",4.9,ctx).tobytes()


def test_tampering_from_previous_gh_artifact_is_denied(tmp_path):
    f=tmp_path/"fake.mp4"
    f.write_bytes(b"not-the-actual-frozen-media")
    with pytest.raises(ValueError,match="SHA"):
        cut.valid_input(f,cut.SOURCE_REV4_SHA)
    with pytest.raises(ValueError,match="SHA"):
        cut.valid_input(f,cut.SOURCE_END_SHA)


def test_workflow_does_not_call_google_or_claim_complete_3d_reality():
    workflow=(ROOT/".github/workflows/citydiscount-rev5-60s-motion-review.yml").read_text()
    code=(ROOT/"scripts/build_citydiscount_rev5_60s_moving_previs.py").read_text()
    for token in ("39706186718","39709324093",
                  "DRAMA_ENABLE_PAID_GENERATION: 'NO'",
                  "CityDiscount_rev5_60s_CINEMATIC_CAMERA_PREVIS_NOT_FINAL.mp4",
                  "retention-days: 7"):
        assert token in workflow
    assert "GEMINI_API_KEY" not in workflow and "secrets." not in workflow
    assert "generate_approved_reference_envelope" not in code
    for name in ("genuine_aerial_to_street_3D_camera_pass",
                 "genuine_sheep_travel_world_zoom_pass",
                 "true_complete_12shot_AI_film"):
        assert '"'+name+'":False' in code
    assert '"publish_approved":False' in code
