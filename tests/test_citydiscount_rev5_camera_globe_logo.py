"""Rev5 Owner cinematography: aerial zoom, follow-lamb pullout, globe to exact logo."""
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import render_citydiscount_rev5_globe_logo_previs as studio


def plan():
    return json.loads(studio.TREATMENT.read_text("utf-8"))


def test_owner_rev5_locked_12_shots_exact_60s_and_non_paid_boundaries():
    x=plan()
    assert x["creative_revision"]==5 and x["source_story_revision"]==4
    assert x["output"] == {
        "width":1080,"height":1440,"aspect_ratio":"3:4","fps":24,
        "total_duration_ms":60000,"shots":12,"shot_duration_ms":5000
    }
    shots=x["shot_camera"]
    assert [s["shot_id"] for s in shots]==[f"s{i:02}" for i in range(1,13)]
    assert [s["time"] for s in shots]==[[i*5000,(i+1)*5000] for i in range(12)]
    assert x["no_new_paid_calls"]==0
    assert x["locked"]["publish_approved"] is False
    assert x["locked"]["real_paid_call_authorized"] is False
    assert x["real_camera_transition_success"] is False
    assert x["real_complete_12_shots"] is False


def test_camera_edges_are_grounded_and_cover_owner_world_to_logo():
    x=plan()
    transit=x["transitions"]
    assert [t["id"] for t in transit]==[
        "aerial_to_street","supermarket_to_cafe","cafe_to_shopping",
        "shopping_to_city","family_to_earth","globe_into_logo"
    ]
    for edge in transit:
        assert edge["from"] in {f"s{i:02}" for i in range(1,13)}
        assert edge["to"] in {f"s{i:02}" for i in range(1,13)}
        assert 0<=edge["start_ms"]<edge["end_ms"]<=60000
        assert edge["anchor"]
        assert edge["real_generation_status"]!="verified"
    assert transit[0]["start_ms"] < 15000 < transit[0]["end_ms"]
    assert transit[-2]["start_ms"]<55000<transit[-2]["end_ms"]


def test_exact_new_owner_tagline_is_not_replaced_with_old_marketing_copy():
    x=plan()
    e=x["endcard"]
    assert e["closing_copy"]=="都市折扣🌟，您的省钱助手小羊薅薅。"
    assert e["line1"]=="都市折扣🌟"
    assert e["line2"]=="您的省钱助手小羊薅薅"
    assert e["logo_full_reveal_ms"]==56600
    assert e["logo_hold_until_ms"]-e["logo_full_reveal_ms"]==3400
    assert e["logo_hold_until_ms"]-e["logo_full_reveal_ms"]>=e["logo_min_hold_ms"]>=3000
    assert e["logo_unmodified_original"] is True
    assert e["voiceover_delivery"]=="not_generated_no_robotic_espeak"
    assert e["publish_approved"] is False


def test_source_rev4_still_immutable_and_endcard_real_source_logo():
    x, logo, digest=studio.load()
    story=json.loads(studio.OLD_STORY.read_text("utf-8"))
    assert story["revision"]==4
    assert digest==story["brand_asset_requirements"]["logo"]["source_sha256"]
    assert x["endcard"]["logo_source"]=="assets/citydiscount/v1/citydiscount_logo_v1.png"
    assert studio.original_logo(logo).width <= 850
    assert studio.original_logo(logo).height <= 290


def test_no_fake_claims_or_gemini_secrets_in_solo_endcard_workflow():
    workflow=(ROOT/".github/workflows/citydiscount-rev5-globe-logo-previs.yml").read_text()
    code=(ROOT/"scripts/render_citydiscount_rev5_globe_logo_previs.py").read_text()
    for term in ("DRAMA_ENABLE_PAID_GENERATION: 'NO'",
                 "render_citydiscount_rev5_globe_logo_previs.py",
                 "CityDiscount_rev5_felt_globe_into_official_logo_5s_PREVIS_NOT_FINAL.mp4",
                 "retention-days: 7"):
        assert term in workflow
    assert "GEMINI_API_KEY" not in workflow
    assert "secrets." not in workflow
    assert "generate_approved_reference_envelope" not in code
    assert '"genuine_city_to_street_zoom_verified":False' in code
    assert '"genuine_city_to_globe_zoom_verified":False' in code
    assert '"new_model_calls":0' in code
    assert '"publish_approved":False' in code


def test_globe_preview_is_actually_renderable_in_three_sample_positions(monkeypatch):
    from PIL import ImageFont
    monkeypatch.setattr(studio, "font_family",
                        lambda size,bold=False: ImageFont.load_default(size=size))
    x, logo, _=studio.load()
    for t in (0.0,1.59,4.95):
        rendered=studio.frame(t,logo,x)
        assert rendered.size==(1080,1440)
        assert rendered.mode=="RGB"
    with pytest.raises(ValueError):
        studio.frame(5.0,logo,x)
