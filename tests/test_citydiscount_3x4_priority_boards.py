"""G4 Canonical mascot and official brand in ONLY owner-selected 3:4 scenes."""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import render_citydiscount_3x4_priority_boards as studio


def test_owner_selection_and_source_dimensions_are_not_auto_inferred_from_old_9_16():
    plan=studio.source()
    assert studio.CHOICE==("s02","s05","s06","s07","s12")
    assert plan["format"]["width"]==1080
    assert plan["format"]["height"]==1440
    assert plan["format"]["aspect_ratio"]=="3:4"
    assert plan["shots"][11]["logo_placement"]=="end_card"
    assert plan["shots"][11]["logo_hold_seconds"]>=3


def test_only_true_original_mascot_and_logo_are_verifiable():
    plan=studio.source()
    original,logo,digest=studio.owned_assets()
    assert digest==plan["brand_asset_requirements"]["logo"]["source_sha256"]
    assert studio.CANONICAL_ROLES["s02"]=="front"
    assert studio.CANONICAL_ROLES["s05"]=="front"
    assert studio.CANONICAL_ROLES["s06"]=="three_quarter"
    assert studio.CANONICAL_ROLES["s07"]=="front"
    assert original["front"].size[0]>0 and original["front"].size[1]>0
    assert logo.size[0]>100 and logo.size[1]>100


def test_actual_five_selected_source_boards_draw_with_exact_3_4_frame(tmp_path, monkeypatch):
    # Plain Python CI intentionally has no CJK font package. Rendering contract
    # stays fully tested with a local Unicode-capable placeholder here, while
    # the dedicated ACTIONS media job renders the true Noto CJK typography.
    from PIL import ImageFont
    monkeypatch.setattr(studio, "font_family",
                        lambda size, bold=False: ImageFont.load_default(size=size))
    receipt=studio.render(tmp_path/"review")
    assert receipt["owner_selection"]==["s02","s05","s06","s07","s12"]
    assert receipt["target_pixel_size"]==[1080,1440]
    assert receipt["new_paid_calls"]==0
    assert receipt["model_submission_allowed"] is False
    assert receipt["source_png_direct_composite_only"] is True
    assert receipt["sprite_eyes_not_modified"] is True
    assert receipt["all_generated_images_are_publish_approved"] is False
    assert receipt["canonical_coin_design_approved"] is False
    assert len(receipt["frames"])==9
    assert [f["shot_id"] for f in receipt["frames"]] == [
        "s02","s05","s05","s05","s06","s07","s07","s07","s12"
    ]
    assert [(f["phase"]) for f in receipt["frames"] if f["shot_id"]=="s05"] == [
        "dig_1","dig_2","one_coin"
    ]
    assert [(f["phase"]) for f in receipt["frames"] if f["shot_id"]=="s07"] == [
        "dig_1","dig_2","one_coin"
    ]
    for f in receipt["frames"]:
        assert f["size_px"]==[1080,1440]
        if f["shot_id"]!="s12":
            assert f["mascot"]["frame_height_fraction"]<=.27
            assert "eyes not redrawn" in f["mascot"]["identity_pixel_transformation"]
            assert f["mascot_role"] in ("front","three_quarter")
        else:
            assert f["original_logo_used"] is True
    files=list((tmp_path/"review").glob("*.png"))
    assert len(files)==9
    with pytest.raises(FileExistsError):
        studio.render(tmp_path/"review")


def test_reject_wrong_prompt_scene_or_fake_logo_source(tmp_path,monkeypatch):
    p=json.loads(studio.PILOT.read_text("utf-8"))
    p["format"]["height"]=1920
    corrupt=tmp_path/"corrupt.json"
    corrupt.write_text(json.dumps(p,ensure_ascii=False),encoding="utf-8")
    monkeypatch.setattr(studio,"PILOT",corrupt)
    with pytest.raises(ValueError,match="3:4 creative"):
        studio.source()
