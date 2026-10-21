"""S05 original owned sheep 360p manual double-dig, zero paid CI."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import pytest
from drama_factory.providers.google_omni_video import VideoCallDisabled

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import citydiscount_s05_omni_reference_once as s05

OPTS={
    "spent_today_usd":"UNKNOWN",
    "paid":False,
    "confirmation":s05.PREVIEW,
    "rights_confirmed":False,
    "google_transfer_confirmed":False,
    "google_terms_accepted":False,
    "invoice_verified":False,
}

def test_owner_real_s05_action_contract_no_cloud_model_call(tmp_path):
    req,receipt=s05.prepare_s05(**OPTS)
    assert req is None
    assert receipt["shot_id"]=="s05"
    assert receipt["model_calls"]==0
    assert receipt["target_px"]==[1080,1440]
    assert receipt["source_request_resolution"]=="360p"
    assert receipt["source_request_aspect"]=="9:16"
    assert receipt["publication_approved"] is False
    assert receipt["actual_fee_usd"] is None
    assert receipt["original_mascot"]["eyes_retouched"] is False
    assert receipt["original_mascot"]["identity_artwork_regenerated"] is False
    assert len(receipt["original_mascot"]["original_png_sha256"])==64
    assert receipt["coin_lettering_status"].startswith("blank model coin")
    assert [(x["relative_ms"],x["event"]) for x in receipt["owner_action_phases"]]==[
        (0,"first_shovel_dig"),(1500,"second_shovel_dig"),
        (3000,"single_CD_coin_found"),(4000,"pack_coin_and_depart")]
    out=s05.run_s05(output_dir=tmp_path/"preview",**OPTS)
    assert out["model_calls"]==0
    assert not list((tmp_path/"preview").glob("*.mp4"))


@pytest.mark.parametrize("bad",["-1","NaN","Infinity","4","3.01","abc",""])
def test_billing_budget_fails_closed(bad):
    with pytest.raises(VideoCallDisabled):
        s05.prepare_s05(**{**OPTS,"spent_today_usd":bad})


def test_paid_s05_require_independent_bill_terms_and_owner_confirmation():
    paid={**OPTS,"paid":True,"confirmation":s05.PAID,
          "spent_today_usd":"0","rights_confirmed":True,
          "google_transfer_confirmed":True,"google_terms_accepted":True,
          "invoice_verified":True}
    with pytest.raises(VideoCallDisabled,match="UNKNOWN"):
        s05.prepare_s05(**{**paid,"spent_today_usd":"UNKNOWN"})
    for k in ("rights_confirmed","google_transfer_confirmed",
              "google_terms_accepted","invoice_verified"):
        with pytest.raises(VideoCallDisabled,match="required"):
            s05.prepare_s05(**{**paid,k:False})
    env,receipt=s05.prepare_s05(**paid)
    assert [p["type"] for p in env.request_payload["input"]]==["image","text"]
    assert env.request_payload["response_format"]=={
        "type":"video","aspect_ratio":"9:16","resolution":"360p","delivery":"uri"}
    assert env.receipt["shot_id"]=="s05"
    assert env.receipt["model_submission_allowed"] is False
    assert env.receipt["media"][0]["png_sha256"]==receipt["original_mascot"]["sanitized_rgb_sha256"]
    assert "DIGS A DISTINCT SECOND" in env.request_payload["input"][-1]["text"]
    assert "ONLY AFTER THE SECOND DIG" in env.request_payload["input"][-1]["text"]
    assert "EXACTLY ONE SMALL GOLD FELT COIN" in env.request_payload["input"][-1]["text"]
    assert "data" not in str(receipt)
    assert receipt["actual_fee_usd"] is None


def test_no_model_request_in_preview_and_missing_paid_switch(tmp_path,monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION","NO")
    paid={**OPTS,"paid":True,"confirmation":s05.PAID,
          "spent_today_usd":"0","rights_confirmed":True,
          "google_transfer_confirmed":True,"google_terms_accepted":True,
          "invoice_verified":True}
    with pytest.raises(VideoCallDisabled,match="disabled"):
        s05.run_s05(output_dir=tmp_path/"never",**paid)
    assert not (tmp_path/"never").exists()


def test_synthetic_single_call_sdk_path_cannot_auto_retry(tmp_path,monkeypatch):
    class Stub:
        n=0
        def generate_approved_reference_envelope(self,envelope,path,*,live_consent):
            self.n+=1
            assert envelope.receipt["shot_id"]=="s05"
            assert live_consent["source_rights_verified_by_operator"] is True
            assert live_consent["provider_retention_terms_accepted"] is True
            assert live_consent["external_model_transfer_approved"] is True
            path.write_bytes(b"synthetic fake CI payload, NOT a real MP4")
            return dict(is_mock=False,model_calls=1,
                        reference_image_count=1,provider_reference_applied=True,
                        provider_task_id="synthetic-ci-do-not-publish")
    sdk=Stub()
    paid={**OPTS,"paid":True,"confirmation":s05.PAID,
          "spent_today_usd":"0","rights_confirmed":True,
          "google_transfer_confirmed":True,"google_terms_accepted":True,
          "invoice_verified":True}
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION","YES")
    monkeypatch.setattr(s05,"_ffprobe",lambda _:{"format":{"duration":"5"},"streams":[
        {"width":360,"height":640,"codec_type":"video"}]})
    x=s05.run_s05(output_dir=tmp_path/"synthetic",provider=sdk,convert_video=False,**paid)
    assert sdk.n==1
    assert x["model_calls"]==1 and x["source_pngs_transmitted"]==1
    assert x["actual_fee_usd"] is None and x["publication_approved"] is False
    with pytest.raises(VideoCallDisabled,match="overwrite"):
        s05.run_s05(output_dir=tmp_path/"synthetic",provider=sdk,convert_video=False,**paid)
    assert sdk.n==1
