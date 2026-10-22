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
