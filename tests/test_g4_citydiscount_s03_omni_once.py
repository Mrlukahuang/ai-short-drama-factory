"""G4 CityDiscount s03 REAL-run entrypoint, preflight tested OFFLINE ONLY."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from decimal import Decimal

import pytest

from scripts.citydiscount_s03_omni_once import (
    DEFAULT_PILOT, prepare_s03_city_plate, run_s03,
)
from drama_factory.providers.google_omni_video import VideoCallDisabled


def test_actual_owner_s03_is_only_input_and_reference_free():
    spec, plan = prepare_s03_city_plate(DEFAULT_PILOT, spent_today_usd="0")
    assert plan["owner_shot_id"] == "s03"
    assert plan["owner_shot_title"] == "奥克兰藏着宝"
    assert plan["source_shot_duration_seconds"] == 5
    assert plan["NOT_full_owner_shot"] is True
    assert plan["source_pngs_transmitted"] == 0
    assert plan["mascot_character_reference_applied"] is False
    assert plan["model_calls"] == 0
    assert plan["output_media"] == "not_generated"
    assert plan["actual_fee_usd"] is None
    assert plan["owner_approved_publication"] is False
    assert spec.model_id == "gemini-omni-1.1-flash"
    assert spec.aspect_ratio == "9:16"
    assert spec.resolution == "360p"
    assert spec.min_duration_seconds == 5
    assert spec.maximum_acknowledged_spend_usd == Decimal("2.00")
    assert spec.operator_approved is True
    assert "Sky Tower" in spec.prompt
    assert "Harbour Bridge" in spec.prompt
    assert "NO mascot" in spec.prompt
    assert "<IMAGE_REF" not in spec.prompt


def test_preflight_creates_only_recipe_and_no_video(tmp_path, monkeypatch):
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    out=tmp_path/"g4-s03"
    result=run_s03(
        pilot_path=DEFAULT_PILOT, output_dir=out,
        spent_today_usd="1.1", paid=False, confirmation="",
    )
    assert result["model_calls"] == 0
    assert sorted(x.name for x in out.iterdir()) == ["receipt.json"]
    assert json.loads((out/"receipt.json").read_text("utf-8")) == result
    with pytest.raises(VideoCallDisabled, match="destination exists"):
        run_s03(
            pilot_path=DEFAULT_PILOT, output_dir=out,
            spent_today_usd="0", paid=False, confirmation="",
        )


@pytest.mark.parametrize("spent", ["3.01","5", "-0.01", "NaN","Infinity","oops"])
def test_spend_reserve_rejects_unsafe_nz_day_declarations(spent):
    with pytest.raises(VideoCallDisabled):
        prepare_s03_city_plate(DEFAULT_PILOT, spent_today_usd=spent)


def test_requires_paid_switch_and_exact_operator_confirmation_before_request(
    tmp_path,monkeypatch,
):
    class NoCalls:
        def generate(self,*args,**kwargs):
            raise AssertionError("NO SDK submission should occur")
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    with pytest.raises(VideoCallDisabled, match="confirm"):
        run_s03(pilot_path=DEFAULT_PILOT,output_dir=tmp_path/"bad",
                spent_today_usd="0",paid=True,
                confirmation="PREVIEW_ONLY",provider=NoCalls())
    with pytest.raises(VideoCallDisabled, match="disabled"):
        run_s03(pilot_path=DEFAULT_PILOT,output_dir=tmp_path/"bad2",
                spent_today_usd="0",paid=True,
                confirmation="GENERATE_ONE_S03_PAID_PLATE",provider=NoCalls())
    assert not (tmp_path/"bad").exists()
    assert not (tmp_path/"bad2").exists()


def test_source_drift_is_detected_before_any_billable_media_call(tmp_path,monkeypatch):
    src=json.loads(DEFAULT_PILOT.read_text("utf-8"))
    src["shots"][2]["shot_title_zh"]="Wrong old scene"
    path=tmp_path/"drift.json"
    path.write_text(json.dumps(src,ensure_ascii=False),encoding="utf-8")
    with pytest.raises(VideoCallDisabled, match="screenplay changed"):
        prepare_s03_city_plate(path,spent_today_usd="0")


def test_expected_real_result_cannot_be_mocked_silently(tmp_path,monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION","YES")
    class FakeModelResult:
        calls=0
        def generate(self,spec,destination):
            self.calls+=1
            return {"is_mock":True,"model_calls":0,"media_path":None}
    fake=FakeModelResult()
    with pytest.raises(VideoCallDisabled,match="reject fake"):
        run_s03(
            pilot_path=DEFAULT_PILOT,output_dir=tmp_path/"mock",
            spent_today_usd="0",paid=True,
            confirmation="GENERATE_ONE_S03_PAID_PLATE",provider=fake,
        )
    assert fake.calls==1
    assert not (tmp_path/"mock"/"receipt.json").exists()
