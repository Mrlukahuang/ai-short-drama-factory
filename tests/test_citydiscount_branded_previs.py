"""G4 Owner first-film original mascot/logo provenance in offline 12-shot review."""
import json
import sys
from pathlib import Path

import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import render_citydiscount_branded_previs as render


def test_actual_owner_script_and_original_repo_asset_bytes():
    original=json.loads(render.PILOT.read_text("utf-8"))
    assert original["project"]=="CityDiscount"
    assert original["revision"]==3
    assert len(original["shots"])==12
    assert original["shots"][2]["shot_title_zh"]=="奥克兰藏着宝"
    roles,logo,sha=render.owned_assets()
    assert len(roles)>=8
    assert logo.width>100 and logo.height>100
    assert sha==original["brand_asset_requirements"]["logo"]["source_sha256"]
    assert "happy" in roles and "three_quarter" in roles
    assert original["controls"]["media_rights_and_remote_upload"]=="not_approved"


def test_private_mascot_media_is_never_sent_to_model_and_s03_sha_is_pinned(tmp_path,monkeypatch):
    missing=tmp_path/"fake-city.mp4"
    missing.write_bytes(b"fake MP4")
    # CI's generic Python runner intentionally lacks FFmpeg. Only this
    # preflight branch is tested here; the specialist renderer workflow runs
    # actual FFmpeg and verifies its MP4.
    monkeypatch.setattr(render.shutil, "which", lambda name: "/usr/bin/true")
    # Local provenance rejects bogus source before any renderer or upload.
    monkeypatch.setattr(sys,"argv",["render_citydiscount_branded_previs",
                                     "--city-plate",str(missing),
                                     "--out",str(tmp_path/"result")])
    with pytest.raises(RuntimeError,match="SHA mismatch"):
        render.main()
    assert not (tmp_path/"result").exists()


def test_owner_copy_and_approved_logo_slots_remain_grounded():
    d=json.loads(render.PILOT.read_text("utf-8"))
    assert [x["logo_placement"] for x in d["shots"] if x["logo_placement"]]==[
        "mascot_chest","discount_book_cover","end_card",
    ]
    assert d["shots"][-1]["logo_hold_seconds"]==3
    assert [x["shot_id"] for x in d["shots"] if x["coin_mark_required"]]==[
        "s01","s11","s12",
    ]
    assert d["brand_asset_requirements"]["coin"]["canonical_coin_artwork_verified"] is False
    assert d["brand_asset_requirements"]["family"]["version_locked"] is False

def test_exact_owner_brand_end_card_remains_visible_in_local_previs():
    script=json.loads(render.PILOT.read_text("utf-8"))
    assert script["storyline"]["end_card_lines"] == [
        "CityDiscount",
        "替你到处挖折扣，让生活多一点。",
        "关注 CityDiscount",
        "下次消费前，先来找找折扣。",
    ]
    assert script["shots"][-1]["logo_hold_seconds"] >= 3
