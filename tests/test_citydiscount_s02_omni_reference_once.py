"""G4/R4.4: manual one-shot reference-video route, NEVER a real paid test."""
from __future__ import annotations
import copy
import json
from pathlib import Path

import pytest
from drama_factory.providers.google_omni_video import VideoCallDisabled
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import citydiscount_s02_omni_reference_once as s02

DEF=dict(
    spent_today_usd="0",
    paid=False,
    confirmation=s02.PREVIEW,
    rights_confirmed=False,
    google_transfer_confirmed=False,
    google_terms_accepted=False,
    invoice_verified=False,
)

def test_source_material_and_owner3_by4_preflight_no_media_transfer(tmp_path):
    envelope, r=s02.prepare_one_shot(**DEF)
    assert envelope is None and r["model_calls"]==0
    assert r["shot_id"]=="s02"
    assert r["output_target_px"]==[1080,1440]
    assert r["model_request_ratio"]=="9:16"
    assert r["not_native_1080p_model"] is True
    assert r["original_mascot"]["role"]=="front"
    assert r["original_mascot"]["eyes_retouched"] is False
    assert r["original_mascot"]["identity_artwork_regenerated"] is False
    assert len(r["original_mascot"]["original_png_sha256"])==64
    assert r["publication_approved"] is False
    rec=s02.run_s02(output_dir=tmp_path/"preview",**DEF)
    assert rec["model_calls"]==0
    assert not (tmp_path/"preview"/"s02_raw_omni_9x16.mp4").exists()


@pytest.mark.parametrize("spent",["-1","NaN","Infinity","4.1","3.01","abc",""])
def test_strict_budget_preflight_never_generates_when_unaffordable(spent):
    with pytest.raises(VideoCallDisabled):
        s02.prepare_one_shot(**{**DEF,"spent_today_usd":spent})


def test_paid_requires_google_terms_separate_owner_authorization_and_verified_invoice():
    opts={**DEF,"paid":True,"confirmation":s02.PAID,
          "rights_confirmed":True,
          "google_transfer_confirmed":True,
          "google_terms_accepted":True,
          "invoice_verified":True}
    for flag in ("rights_confirmed","google_transfer_confirmed",
                 "google_terms_accepted","invoice_verified"):
        with pytest.raises(VideoCallDisabled,match="requires"):
            s02.prepare_one_shot(**{**opts,flag:False})
    envelope, receipt=s02.prepare_one_shot(**opts)
    assert len(envelope.request_payload["input"])==2
    assert [x["type"] for x in envelope.request_payload["input"]]==["image","text"]
    assert envelope.request_payload["response_format"]["aspect_ratio"]=="9:16"
    assert "EYES" in envelope.request_payload["input"][1]["text"]
    assert envelope.receipt["media"][0]["png_sha256"]==receipt["original_mascot"]["sanitized_rgb_sha256"]
    assert envelope.receipt["model_submission_allowed"] is False
    assert receipt["actual_fee_usd"] is None
    assert "data" not in str(receipt) and "base64" not in str(receipt)
    assert receipt["model_calls"]==0


def test_no_paid_key_rejects_before_creating_directory(tmp_path,monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION","NO")
    opts={**DEF,"paid":True,"confirmation":s02.PAID,
          "rights_confirmed":True,"google_transfer_confirmed":True,
          "google_terms_accepted":True,"invoice_verified":True}
    with pytest.raises(VideoCallDisabled,match="not enabled"):
        s02.run_s02(output_dir=tmp_path/"never",**opts)
    assert not (tmp_path/"never").exists()


def test_one_model_call_by_injected_fake_sdk_but_never_claims_real_media_in_ci(
    tmp_path,monkeypatch
):
    # Stub exercises the actual production call boundary, not external paid
    # Google requests. Check that no second provider submission is possible.
    class SDKStub:
        calls=0
        def generate_approved_reference_envelope(self,envelope,destination,*,live_consent):
            self.calls+=1
            assert live_consent["source_rights_verified_by_operator"] is True
            assert live_consent["external_model_transfer_approved"] is True
            assert live_consent["provider_retention_terms_accepted"] is True
            assert live_consent["max_run_spend_usd"]=="2.00"
            assert [part["type"] for part in envelope.request_payload["input"]]==[
                "image","text"]
            destination.write_bytes(b"fake stub video -- NOT AN ACTUAL MP4")
            return {
                "is_mock":False,"model_calls":1,
                "reference_image_count":1,"provider_reference_applied":True,
                "provider_task_id":"synthetic-sdk-only",
            }
    fake=SDKStub()
    monkeypatch.setenv("DRAMA_ENABLE_PAID_GENERATION","YES")
    opts={**DEF,"paid":True,"confirmation":s02.PAID,
          "rights_confirmed":True,"google_transfer_confirmed":True,
          "google_terms_accepted":True,"invoice_verified":True}
    monkeypatch.setattr(s02,"_ffprobe",lambda path:{"format":{"duration":"5.00"},
         "streams":[{"codec_type":"video","width":360,"height":640}]})
    receipt=s02.run_s02(output_dir=tmp_path/"fake",provider=fake,
                        convert_video=False,**opts)
    assert fake.calls==1
    assert receipt["source_pngs_transmitted"]==1
    assert receipt["model_calls"]==1
    assert receipt["provider_billing_unverified"] is True
    assert receipt["actual_fee_usd"] is None
    assert receipt["publication_approved"] is False
    with pytest.raises(VideoCallDisabled,match="already exists"):
        s02.run_s02(output_dir=tmp_path/"fake",provider=fake,
                   convert_video=False,**opts)
    assert fake.calls==1


def test_invalid_source_image_hash_blocks_reference_buildup(monkeypatch,tmp_path):
    inv=s02.INVENTORY
    original=json.loads(inv.read_text("utf-8"))
    front=next(x for x in original["images"] if x["role"]=="front")
    front["source_sha256"]="0"*64
    corrupted=tmp_path/"fake_inventory.json"
    corrupted.write_text(json.dumps(original),encoding="utf-8")
    monkeypatch.setattr(s02,"INVENTORY",corrupted)
    with pytest.raises(VideoCallDisabled,match="changed"):
        s02.prepare_one_shot(**DEF)
