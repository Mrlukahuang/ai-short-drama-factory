"""G4 R4.4: original Omni character quality must not be falsely replaced by 3D placeholders."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/"config/pilots/citydiscount_real_video_replacement_rev5.json"
CAMERA=ROOT/"config/pilots/citydiscount_camera_treatment_rev5.json"
STORY=ROOT/"config/pilots/citydiscount_coin_hunt_1080x1440_v2.json"


def data():return json.loads(PACK.read_text(encoding="utf-8"))


def test_rev5_media_manifest_has_exact_story_scope_and_no_paid_call_authorization():
    x=data()
    camera=json.loads(CAMERA.read_text(encoding="utf-8"))
    story=json.loads(STORY.read_text(encoding="utf-8"))
    assert x["schema"]=="g4-citydiscount-real-omni-replacement-readiness.v1"
    assert (x["stage"],x["req"],x["creative_revision"])==("G4","R4.4",5)
    assert x["output"]=={"width":1080,"height":1440,"aspect_ratio":"3:4",
                         "shots":12,"shot_seconds":5,"total_seconds":60}
    assert x["output"]["width"]==camera["output"]["width"]==story["format"]["width"]
    assert x["output"]["height"]==camera["output"]["height"]==story["format"]["height"]
    assert x["acceptance_gate"]["can_trigger_model_run_now"] is False
    assert x["acceptance_gate"]["max_new_model_calls_without_owner_authorization"]==0
    assert x["acceptance_gate"]["publication_approved"] is False
    assert x["acceptance_gate"]["all_real_shots_ready"] is False
    for tag in ("owner_source_viewpoint_rights_verified",
                "owner_new_external_media_transfer_authorized",
                "actual_historical_model_invoice_verified",
                "owner_paid_generation_run_authorized",
                "provider_budget_cap_enforceable"):
        assert x["acceptance_gate"][tag] is False


def test_real_genuine_sources_are_sha_pinned_not_reclassified_fake_s03():
    x=data()
    real=x["pinned_real_sources"]
    assert set(real)=={"s02","s05","s03_environment_only"}
    assert real["s02"]["raw_sha256"]=="a8a25ba43e5e8659d9c5528d685c69e8e0f991b990a48bf77c5c2be4fcfef80c"
    assert real["s05"]["raw_sha256"]=="4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56"
    assert real["s03_environment_only"]["raw_sha256"]=="b718e6b0a6e5a64db66d74e6b1364326d16671823fca12935e8a3667b101af3f"
    assert real["s03_environment_only"]["real_rev5_character_scene_completed"] is False
    for sid in ("s02","s05"):
        assert real[sid]["model_resolution"]==[360,640]
        assert real[sid]["target_pixels"]==[1080,1440]
        assert real[sid]["native_aspect"]=="9:16"
        assert real[sid]["target_aspect"]=="3:4"
        assert real[sid]["actual_provider_fee_usd"] is None
        assert real[sid]["permission_for_new_generation"] is False


def test_each_missing_real_scene_has_one_exact_5second_grounded_prompt():
    x=data()
    originals=[f"s{i:02}" for i in range(1,13)]
    real=set(x["retained_real_mascot_shots"])
    missing=set(x["missing_real_mascot_shots"])
    assert real=={"s02","s05"}
    assert missing==set(originals)-real-{"s12"}
    assert len(missing)==9
    shots=x["proposed_replacements"]
    assert len(shots)==9
    assert {s["shot_id"] for s in shots}==missing
    assert [s["shot_id"] for s in shots[:4]]==["s03","s04","s10","s11"]
    for s in shots:
        assert s["start_ms"]==(int(s["shot_id"][1:])-1)*5000
        assert s["end_ms"]-s["start_ms"]==5000
        assert s["seconds"]==5
        assert s["source_state"]=="REAL_REV5_MOTION_MISSING"
        assert s["approved_for_paid_run"] is False
        assert s["approved_for_publication"] is False
        assert len(s["generation_prompt"])>220
        assert len(s["prev_next_continuity"])>40
        assert len(s["qa_acceptance"])>=4


def test_owner_endcard_exact_copy_no_fake_brand_claims():
    x=data()
    e=x["end_card"]
    assert e["owner_text"]=="都市折扣🌟，您的省钱助手小羊薅薅。"
    assert e["official_logo_hold_seconds"]>=3.0
    assert e["genuine_planetary_3d_video"] is False
    assert x["prompt_identity_style_lock"].count("15-22 percent")==1
    assert x["acceptance_gate"]["existing_G4_offline_ingest_reused"]=="scripts/run_g4_existing_episode_offline.py"
    assert (ROOT/x["acceptance_gate"]["existing_G4_offline_ingest_reused"]).exists()
    assert len(x["acceptance_timeline"])==6
    assert all(s["status"] in ("OWNER_GATE","BLOCKED") for s in x["acceptance_timeline"])
    combined=" ".join([x["prompt_identity_style_lock"]]+
                      [s["generation_prompt"] for s in x["proposed_replacements"]])
    assert "realtime guaranteed discount" not in combined.lower()
    assert "no shop brand" in combined.lower() or "no retailer names" in combined.lower()
