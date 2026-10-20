"""CityDiscount first-video direction: zero-fee storyboard contract tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from drama_factory.pipeline.promo_motion_graphics import (
    PromoPlanError, build_offline_citydiscount_promo_plan,
)

PILOT = (Path(__file__).resolve().parents[1] /
         "config/pilots/citydiscount_first_promo_v1.json")


def _candidate():
    return json.loads(PILOT.read_text(encoding="utf-8"))


def test_fixed_sixty_second_brand_promo_not_fictional_felt_episode():
    out = build_offline_citydiscount_promo_plan(_candidate())
    assert out["shot_count"] == 12
    assert out["duration_seconds"] == 60
    assert out["purpose"] == "brand_first_motion_graphics"
    assert [s["shot_id"] for s in out["shots"]] == [
        f"s{i:02d}" for i in range(1, 13)
    ]
    assert out["model_calls"] == 0
    assert out["video_generated"] is False
    assert out["model_submission_allowed"] is False
    assert out["publish_approved"] is False
    assert out["g4_exit_approved"] is False
    assert "CityDiscount" in out["shots"][3]["postproduction_overlay_text"] or (
        "CITYDISCOUNT" in out["shots"][3]["postproduction_overlay_text"]
    )


def test_stable_source_and_offline_plan_hash():
    assert build_offline_citydiscount_promo_plan(_candidate()) == (
        build_offline_citydiscount_promo_plan(_candidate())
    )
    src = _candidate()
    changed = copy.deepcopy(src)
    changed["shots"][1]["voiceover_zh"] += "啊"
    assert build_offline_citydiscount_promo_plan(src)["offline_plan_sha256"] != (
        build_offline_citydiscount_promo_plan(changed)["offline_plan_sha256"]
    )


@pytest.mark.parametrize("field,bad", [
    ("real_paid_call_authorized", True),
    ("media_rights_and_remote_upload", "approved"),
    ("publish_approved", True),
    ("g4_exit_approved", True),
    ("model_calls", 1),
])
def test_cannot_auto_approve_real_media_or_fees(field, bad):
    c = _candidate()
    c["controls"][field] = bad
    with pytest.raises(PromoPlanError):
        build_offline_citydiscount_promo_plan(c)


def test_no_invented_prices_and_false_products():
    for content in ("全场NZ$9.99", "手机上直接扫码领券",
                    "保证全网最低，CityDiscount App",
                    "KFC 官方合作专享"):
        c = _candidate()
        c["shots"][0]["on_screen_text_zh"] = content
        with pytest.raises(PromoPlanError, match="Unchecked"):
            build_offline_citydiscount_promo_plan(c)


def test_time_and_dependencies_must_remain_ordered():
    c = _candidate()
    c["shots"][5]["start_ms"] += 1000
    with pytest.raises(PromoPlanError, match="Wrong shot"):
        build_offline_citydiscount_promo_plan(c)
    c = _candidate()
    c["shots"][0]["shot_dependencies"] = ["s12"]
    with pytest.raises(PromoPlanError, match="future"):
        build_offline_citydiscount_promo_plan(c)


def test_no_fake_brand_actor_or_auto_generated_logo():
    c = _candidate()
    c["shots"][1]["asset_roles"] = ["fake_actor_called_citydiscount"]
    with pytest.raises(PromoPlanError, match="Brand reference"):
        build_offline_citydiscount_promo_plan(c)
    output = build_offline_citydiscount_promo_plan(_candidate())
    for shot in output["shots"]:
        assert shot["media_pending_approval"] is True
        assert "postproduction_overlay_text" in shot
        assert "video_background_prompt" in shot
        assert not shot.get("provider_reference_applied", False)
