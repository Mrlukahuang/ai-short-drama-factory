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



def test_true_xyz_projected_city_faces_change_under_camera_orbit():
    import citydiscount_3d_diorama as geo
    p=(2.5,1.5,0.0)
    high=(2.5,1.5,1.2)
    c0=geo.Camera(azimuth=.55,elevation=.65,zoom=90)
    c1=geo.Camera(azimuth=1.12,elevation=.65,zoom=90)
    assert c0.project(p)!=c1.project(p)
    assert c0.project(high)[1] < c0.project(p)[1]
    assert len(geo.BUILDINGS) >= 20
    assert all(b["h"]>0 and b["x1"]>b["x0"] for b in geo.BUILDINGS)


def test_through_city_camera_is_real_xyz_projection_and_mascot_moves(monkeypatch):
    import citydiscount_3d_diorama as geo
    from PIL import ImageFont
    monkeypatch.setattr(cut.boards,"font_family",
                        lambda s,bold=False:ImageFont.load_default(size=s))
    roles,logo,digest=cut.boards.owned_assets()
    first=geo.scene_frame("s03",.0,roles["front"])
    next_view=geo.scene_frame("s03",4.8,roles["front"])
    street=geo.scene_frame("s04",4.2,roles["front"])
    weave=geo.scene_frame("s10",2.1,roles["front"])
    assert first.size==street.size==weave.size==(540,720)
    assert first.tobytes()!=next_view.tobytes()
    assert first.tobytes()!=street.tobytes()
    assert geo.camera_for("s03",0).elevation!=geo.camera_for("s03",4.8).elevation
    assert geo.camera_for("s03",0).azimuth!=geo.camera_for("s03",4.8).azimuth
    assert geo.camera_for("s10",0).zoom>geo.camera_for("s10",4.8).zoom
    assert abs(geo.route("s03",4.999)[0]-geo.route("s04",0)[0])<.05
    assert abs(geo.route("s09",4.999)[0]-geo.route("s10",0)[0])<.05
    assert abs(geo.route("s10",4.999)[1]-geo.route("s11",0)[1])<.05


def test_pipeline_really_uses_depth_sorted_xyz_world_not_old_flat_map():
    code=(ROOT/"scripts/build_citydiscount_rev5_60s_moving_previs.py").read_text()
    geo=(ROOT/"scripts/citydiscount_3d_diorama.py").read_text()
    assert 'city3d.scene_frame(sid,t,context["front"])' in code
    assert '"procedural_3d_scene_rendered":True' in code
    assert '"original_sheep_2d_billboard_in_xyz_city":True' in code
    assert '"sheep_actor_is_billed_3d_rigged":False' in code
    assert 'cam.project' in geo and 'draw_building' in geo
    assert 'entities.sort(key=lambda e:e[0])' in geo
    assert 'sheep_actor_3d_rigged' not in geo
    assert '"true_complete_12shot_AI_film":False' in code



def test_sheep_paths_follow_street_lines_never_building_lots():
    import citydiscount_street_motion as motion
    for sid in motion.PATHS:
        for i in range(51):
            x,y=motion.world_path(sid,i*.098)
            assert motion.within_road(x,y), (sid,i,x,y)
    for sid,path in motion.PATHS.items():
        for a,b in zip(path[:-1],path[1:]):
            assert a[0]==b[0] or a[1]==b[1], (sid,a,b)


def test_sheep_route_world_coordinates_remain_contiguous_at_cuts():
    import citydiscount_street_motion as motion
    for before,after in [("s03","s04"),("s04","s06"),
                         ("s06","s07"),("s07","s08"),("s08","s09"),
                         ("s09","s10"),("s10","s11")]:
        x1,y1=motion.world_path(before,5)
        x2,y2=motion.world_path(after,0)
        assert abs(x1-x2)<.00001 and abs(y1-y2)<.00001,(before,after)


def test_real_xyz_camera_transform_continuity_between_local_shots():
    import citydiscount_street_motion as motion
    import citydiscount_3d_diorama as geo
    for before,after in [("s03","s04"),("s06","s07"),("s07","s08"),
                         ("s08","s09"),("s09","s10"),("s10","s11")]:
        a=motion.camera_key(before,5)
        b=motion.camera_key(after,0)
        assert all(abs(x-y)<.000001 for x,y in zip(a,b)),(before,after)
    aerial=geo.Camera(*motion.camera_key("s03",0))
    street=geo.Camera(*motion.camera_key("s04",4.999))
    assert aerial.elevation>street.elevation
    assert aerial.zoom<street.zoom
    assert geo.Camera(*motion.camera_key("s11",4.999)).zoom<street.zoom


def test_lamb_animates_bob_step_bow_without_redrawing_owner_face():
    import citydiscount_street_motion as motion
    a=motion.pose("s06",.16)
    b=motion.pose("s06",.36)
    assert a["walking"] and b["walking"]
    assert a["tilt_degrees"] != b["tilt_degrees"]
    assert abs(a["tilt_degrees"])<=2.71
    assert abs(b["tilt_degrees"])<=2.71
    assert 0<=a["bob_height"]<=.043
    first=motion.pose("s07",1.0)
    second=motion.pose("s07",2.3)
    third=motion.pose("s07",3.0)
    assert [first["dig_stroke"],second["dig_stroke"],third["dig_stroke"]]==[1,2,0]
    assert not first["coin_visible"] and not second["coin_visible"]
    assert third["coin_visible"]
    assert motion.pose("s09",3)["coin_visible"]
    assert not motion.pose("s04",3)["coin_visible"]


def test_mini_city_3d_renderer_uses_new_gait_and_keeps_publishing_blocked():
    render=(ROOT/"scripts/citydiscount_3d_diorama.py").read_text()
    editor=(ROOT/"scripts/build_citydiscount_rev5_60s_moving_previs.py").read_text()
    workflow=(ROOT/".github/workflows/citydiscount-rev5-60s-motion-review.yml").read_text()
    assert "motion.actor_key(sid,t)" in render
    assert "motion.composite_actor" in render
    assert "citydiscount_street_motion.py" in workflow
    assert '"street_routes_use_continuous_xyz_grid":True' in editor
    assert '"sheep_is_original_billboard_not_3d_rigged":True' in editor
    assert '"true_complete_12shot_AI_film":False' in editor
    assert '"publish_approved":False' in editor
    assert "GEMINI_API_KEY" not in workflow



def test_true_xyz_wool_body_and_four_independent_projected_legs():
    import citydiscount_3d_diorama as geo
    import citydiscount_volumetric_lamb as wool
    from PIL import Image
    cam=geo.Camera(target_x=2,target_y=3,azimuth=.7,elevation=.9,zoom=110)
    other=geo.Camera(target_x=2,target_y=3,azimuth=1.4,elevation=.9,zoom=110)
    blob=wool.projected_ellipsoid(cam,(2,3,.45),(.43,.32,.4))
    blob_other=wool.projected_ellipsoid(other,(2,3,.45),(.43,.32,.4))
    assert len(blob)>=6 and blob!=blob_other
    a=Image.new("RGB",(540,720),"#d2e0d5")
    b=a.copy()
    metadata=wool.volumetric_lamb_frame(a,cam,(2,3,.065),t=.1,walking=True)
    wool.volumetric_lamb_frame(b,cam,(2,3,.065),t=.42,walking=True)
    assert a.tobytes()!=b.tobytes()
    assert metadata["four_xyz_jointed_gait_legs"] is True
    assert metadata["canonical_face_is_2d_source_overlay"] is True
    assert metadata["approved_rigged_3d_sheep"] is False


def test_3d_body_still_uses_original_source_face_not_new_model_pixels():
    src=(ROOT/"scripts/citydiscount_street_motion.py").read_text()
    code=(ROOT/"scripts/citydiscount_volumetric_lamb.py").read_text()
    assert "wool3d.volumetric_lamb_frame" in src
    assert "source.convert(" in src
    assert "face_source=full.crop" in src
    assert "approved_rigged_3d_sheep" in code
    assert "generate_approved_reference_envelope" not in src
    assert "GEMINI_API_KEY" not in src


def test_city_s11_last_frame_blends_into_globe_with_no_logo_hold_loss():
    from PIL import Image
    import citydiscount_city_to_globe_bridge as globe
    city=Image.new("RGB",(540,720),"#214f44")
    earth=Image.new("RGB",(540,720),"#b9d6d0")
    first=globe.bridge_frame(city,earth,0)
    middle=globe.bridge_frame(city,earth,.55)
    arrived=globe.bridge_frame(city,earth,.95)
    assert first.tobytes()==city.tobytes()
    assert arrived.tobytes()==earth.tobytes()
    assert middle.tobytes()!=city.tobytes()
    assert middle.tobytes()!=earth.tobytes()
    with pytest.raises(ValueError):
        globe.bridge_frame(city,earth,5)
    with pytest.raises(ValueError):
        globe.bridge_frame(Image.new("RGB",(1080,1440)),earth,.4)


def test_60sec_movie_includes_city_to_globe_bridge_and_locked_real_video_truth():
    workflow=(ROOT/".github/workflows/citydiscount-rev5-60s-motion-review.yml").read_text()
    editor=(ROOT/"scripts/build_citydiscount_rev5_60s_moving_previs.py").read_text()
    assert "citydiscount_volumetric_lamb.py" in workflow
    assert "citydiscount_city_to_globe_bridge.py" in workflow
    assert "globe_bridge.encode(city_last,end,target)" in editor
    assert '"hybrid_lamb_projected_3d_wool_body_and_four_gait_legs":True' in editor
    assert '"hybrid_lamb_owner_3d_identity_approval":False' in editor
    assert '"planetary_full_3d_camera_animation_pass":False' in editor
    assert '"true_complete_12shot_AI_film":False' in editor
    assert '"publish_approved":False' in editor
    assert "secrets." not in workflow



def test_dollhouse_cutaway_is_local_smooth_and_does_not_flatten_city():
    import citydiscount_3d_diorama as geo
    home=geo.BUILDINGS[0]
    near_x,near_y=(home["x0"]+home["x1"])/2,(home["y0"]+home["y1"])/2
    high=geo.dollhouse_height(home,"s06",near_x,near_y,108)
    assert 0.4*home["h"]<=high<home["h"]
    assert geo.dollhouse_height(home,"s03",near_x,near_y,108)==home["h"]
    assert geo.dollhouse_height(home,"s06",near_x+3,near_y+3,108)==home["h"]
    assert geo.dollhouse_height(home,"s06",near_x,near_y,43)==home["h"]


def test_home_family_volumes_make_real_visible_non_final_scenes():
    from PIL import Image
    import citydiscount_3d_diorama as geo
    a=Image.new("RGB",(540,720),"#cbded7")
    b=a.copy()
    cam=geo.camera_for("s01",2)
    geo.draw_home_family(a,cam,"s01",2)
    geo.draw_home_family(b,cam,"s11",1)
    assert a.tobytes()!=Image.new("RGB",(540,720),"#cbded7").tobytes()
    assert b.tobytes()!=a.tobytes()
    assert len(geo.BUILDINGS)>=20


def test_actual_encoded_video_contact_sheet_keeps_manual_quality_gate(monkeypatch,tmp_path):
    from io import BytesIO
    from PIL import Image
    import citydiscount_visual_contact_sheet as sheet
    video=tmp_path/"reused_existing.mp4"
    video.write_bytes(b"tiny mock encoded bytes")
    receipt=tmp_path/"receipt.json"
    receipt.write_text(json.dumps({
        "film_sha256":sheet.sha(video),"shot_count":12,
        "resolution":[1080,1440],"duration_seconds":60.0,
        "publish_approved":False,"existing_real_AI_lamb_shots":["s02","s05"]
    }))
    payload=BytesIO()
    Image.new("RGB",(54,72),"#aac3ad").save(payload,format="PNG")
    class Proc:
        def __init__(self):self.stdout=payload.getvalue()
    calls=[]
    def fake_run(cmd,**kwargs):
        calls.append(cmd)
        assert cmd[0]=="ffmpeg"
        assert "-ss" in cmd and "-frames:v" in cmd
        return Proc()
    monkeypatch.setattr(sheet.subprocess,"run",fake_run)
    output=tmp_path/"scene_grid.png"
    result=sheet.collect(video,receipt,output)
    assert len(calls)==12
    assert Image.open(output).size==(1620,772)
    assert result["visual_quality_pass"] is None
    assert result["owner_character_design_pass"] is None
    assert result["approved_for_release"] is False
    assert result["actual_ai_generated_lamb_motion_shots"]==["s02","s05"]
    assert len(result["sampled_real_output_frames"])==12
    assert (tmp_path/"visual_review.json").is_file()
    video.write_bytes(b"tamper")
    with pytest.raises(ValueError,match="Refuse"):
        sheet.collect(video,receipt,tmp_path/"different_grid.png")



def test_genuine_s05_sanitized_source_is_explicitly_sha_pinned_and_not_paid():
    assert cut.SOURCE_CLEAN_S05_SHA=="7a4a7e5f261a641dd7035698a5aad3a9a331bf51a70c5ccd7565677a2694a652"
    assert cut.REAL_IDS==("s02","s05")
    assert cut.SOURCE_REV4_SHA=="e65d01356dcc977ab40c6cfea2ed479b812b8d16ffae6ccc41bfde8ce430288e"
    code=(ROOT/"scripts/build_citydiscount_rev5_60s_moving_previs.py").read_text()
    assert 'elif sid in REAL_IDS:' in code
    assert 'if sid=="s05" and s05_clean is not None:' in code
    assert "extract_clean_s05(s05_clean,target)" in code
    assert "scale=810:1440:flags=lanczos" in code
    assert "overlay=(W-w)/2:0,format=yuv420p,fps=24" in code
    assert '"s05_native_9by16_reframed_without_stretch":s05_clean is not None' in code
    assert 'kind="EXISTING_REAL_OMNI_S05_BRAND_SIGN_REDACTED_LOCAL_REVIEW"' in code
    assert '"s05_clean_reuses_existing_omni_not_new_ai":True' in code
    assert '"s05_original_audio_replaced_by_temporary_mix":True' in code
    assert '"s05_coin_exact_design_approved":False' in code
    assert '"s05_two_digs_owner_verified":False' in code
    assert '"publish_approved":False' in code


def test_s05_sha_invalid_does_not_silently_fall_back_to_original(tmp_path):
    corrupted=tmp_path/"s05_clean.mp4"
    corrupted.write_bytes(b"not the authorized real s05 redacted media")
    with pytest.raises(ValueError,match="SHA"):
        cut.valid_input(corrupted,cut.SOURCE_CLEAN_S05_SHA)
    link=tmp_path/"linked.mp4"
    link.symlink_to(corrupted)
    with pytest.raises(ValueError):
        cut.valid_input(link,cut.SOURCE_CLEAN_S05_SHA)


def test_final_real_s05_integrated_60s_workflow_still_requires_all_media_checks():
    wf=(ROOT/".github/workflows/citydiscount-rev5-60s-motion-review.yml").read_text()
    assert "CityDiscount-s05-REAL-OMNI-SIGN-REDACTED-5s-REVIEW-NOT-FINAL" in wf
    assert "run-id: 39747140543" in wf
    assert "--s05-clean artifacts/clean-s05/CityDiscount_s05_REAL_OMNI_BANNER_REDACTED_5s_NOT_FINAL.mp4" in wf
    assert 'assert r["s05_shop_sign_hallucination_removed_in_cut"] is True' in wf
    assert 'assert r["s05_clean_reuses_existing_omni_not_new_ai"] is True' in wf
    assert 'assert r["s05_coin_exact_design_approved"] is False' in wf
    assert "CONTACT_SHEET_12_SHOTS.png" in wf
    assert "visual_review.json" in wf
    assert "retention-days: 7" in wf
    assert "secrets." not in wf
    assert "GEMINI_API_KEY" not in wf



def test_exact_historical_real_felt_auckland_s03_is_a_city_only_source():
    assert cut.SOURCE_REAL_S03_ENV_SHA=="b718e6b0a6e5a64db66d74e6b1364326d16671823fca12935e8a3667b101af3f"
    code=(ROOT/"scripts/build_citydiscount_rev5_60s_moving_previs.py").read_text()
    assert 'if sid=="s03" and s03_city is not None:' in code
    assert 'extract_real_s03_city_zoom(s03_city,target)' in code
    assert '"s03_genuine_existing_omni_environment_in_60s":s03_city is not None' in code
    assert '"s03_original_camera_crane_out_retimed_in_reverse":s03_city is not None' in code
    assert '"s03_native_9by16_nonstretched_reframe":s03_city is not None' in code
    assert '"s03_has_original_mascot_performance":False' in code
    assert '"s03_s04_unbroken_real_world_camera_verified":False' in code
    assert '"real_model_generated_shots_added_in_this_run":0' in code
    assert '"true_complete_12shot_AI_film":False' in code


def test_real_s03_reverse_movie_uses_old_source_geometry_not_fake_stretch(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(cut,"call",lambda args:calls.append(args))
    original=tmp_path/"source.mp4"
    target=tmp_path/"s03.mp4"
    cut.extract_real_s03_city_zoom(original,target)
    assert len(calls)==1
    argv=calls[0]
    assert "-filter_complex" in argv
    vf=argv[argv.index("-filter_complex")+1]
    assert "trim=duration=5,setpts=PTS-STARTPTS,reverse,split=2" in vf
    assert "scale=810:1440:flags=lanczos" in vf
    assert "gblur=sigma=26" in vf
    assert "overlay=(W-w)/2:0" in vf
    assert "-frames:v" in argv and argv[argv.index("-frames:v")+1]=="120"
    assert "-an" in argv
    assert "-c:v" in argv and "libx264" in argv
    assert str(original) in argv and str(target) in argv


def test_s03_sha_bypass_or_missing_real_plate_fails_closed(tmp_path):
    false=tmp_path/"s03_city_plate.mp4"
    false.write_bytes(b"synthetic city cannot masquerade as old model-generated video")
    with pytest.raises(ValueError,match="SHA"):
        cut.valid_input(false,cut.SOURCE_REAL_S03_ENV_SHA)
    linked=tmp_path/"symlink.mp4"
    linked.symlink_to(false)
    with pytest.raises(ValueError):
        cut.valid_input(linked,cut.SOURCE_REAL_S03_ENV_SHA)


def test_actual_full_60s_runner_uses_real_s03_without_spending_or_claiming_character():
    wf=(ROOT/".github/workflows/citydiscount-rev5-60s-motion-review.yml").read_text()
    assert "run-id: 39441034483" in wf
    assert "citydiscount-s03-city-plate-not-final-episode" in wf
    assert "--s03-city artifacts/real-city-s03/s03-real/s03_city_plate.mp4" in wf
    assert 'assert r["s03_real_source_sha256"]=="b718e6b0a6e5a64db66d74e6b1364326d16671823fca12935e8a3667b101af3f"' in wf
    assert 'assert r["s03_has_original_mascot_performance"] is False' in wf
    assert 'assert r["s03_s04_unbroken_real_world_camera_verified"] is False' in wf
    assert 'assert r["real_model_generated_shots_added_in_this_run"]==0' in wf
    assert "CONTACT_SHEET_12_SHOTS.png" in wf
    assert "visual_review.json" in wf
    assert "DRAMA_ENABLE_PAID_GENERATION: 'NO'" in wf
    assert "secrets." not in wf



def test_s04_same_real_city_is_explicitly_only_a_digital_push_not_real_character():
    src=(ROOT/"scripts/build_citydiscount_rev5_60s_moving_previs.py").read_text()
    for marker in ('"s04_same_original_real_city_frame_followup":s04_same_real_plate',
                   '"s04_last_s03_frame_local_digital_push_only":s04_same_real_plate',
                   '"s04_genuine_new_ai_character_performance":False',
                   '"s04_genuine_3d_parallax_camera_motion":False',
                   '"s03_s04_unbroken_real_world_camera_verified":False',
                   '"real_model_generated_shots_added_in_this_run":0',
                   '"s04_original_program_city_unmodified_in_default_cut":not s04_same_real_plate'):
        assert marker in src
    assert 'if sid=="s04" and s04_same_real_plate:' in src
    assert 'extract_real_s04_same_plate_digital_push(seg/"s03.mp4",target)' in src
    assert 'if s04_same_real_plate and s03_city is None:' in src


def test_s04_uses_exact_final_120th_frame_and_zoom_at_most_1point5(monkeypatch,tmp_path):
    from PIL import Image
    calls=[]
    def fake(cmd):
        calls.append(cmd)
        if cmd[-1].endswith(".png"):
            Image.new("RGB",(1080,1440),"#ddd1b7").save(cmd[-1])
    monkeypatch.setattr(cut,"call",fake)
    src=tmp_path/"s03.mp4"
    target=tmp_path/"s04.mp4"
    cut.extract_real_s04_same_plate_digital_push(src,target)
    assert len(calls)==2
    assert "select=eq(n\\,119)" in calls[0]
    assert "-frames:v" in calls[0]
    assert str(src) in calls[0]
    vf=calls[1][calls[1].index("-vf")+1]
    assert "zoompan" in vf
    assert "on*0.0042,1.5" in vf
    assert "d=120:s=1080x1440:fps=24" in vf
    assert str(target) in calls[1]
    assert not (tmp_path/"s04.s03-last.png").exists()  # no stray imagery


def test_s04_never_uses_synthetic_city_when_real_plate_gate_broken(monkeypatch,tmp_path):
    # Deliberately no SHA-pinned old real s03 input and no offline visual fallback.
    monkeypatch.setattr(cut,"valid_input",lambda p,s:p)
    with pytest.raises(ValueError,match="requires exact SHA-pinned"):
        cut.make_cut(rev4=tmp_path/"rev4.mp4",end=tmp_path/"end.mp4",
                     out=tmp_path/"no_review_cut",s04_same_real_plate=True)


def test_s04_60second_artifact_is_separate_from_previous_review_edition():
    workflow=(ROOT/".github/workflows/citydiscount-rev5-60s-motion-review.yml").read_text()
    assert "--s04-same-real-plate" in workflow
    assert "CityDiscount-rev5-60s-S03-S04-SAME-REAL-WOOL-PLATE-DIGITAL-PUSH-AB-NOT-FINAL" in workflow
    assert "run-id: 39441034483" in workflow
    assert 'assert r["s04_genuine_3d_parallax_camera_motion"] is False' in workflow
    assert 'assert r["s04_genuine_new_ai_character_performance"] is False' in workflow
    assert 'assert r["provenance"][3]["kind"]=="LOCAL_ZOOMPAN_OF_HISTORICAL_REAL_OMNI_CITY_S03_FRAME_NOT_NEW_REAL_SHOT"' in workflow
    assert "CONTACT_SHEET_12_SHOTS.png" in workflow
    assert "retention-days: 7" in workflow
    assert "DRAMA_ENABLE_PAID_GENERATION: 'NO'" in workflow
    assert "secrets." not in workflow
