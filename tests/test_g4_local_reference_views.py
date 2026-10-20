"""Real local file byte-backed views, no virtual angle or approval flags."""
from __future__ import annotations

import hashlib
import io

import pytest
from PIL import Image

from drama_factory.pipeline.local_asset_references import stage_local_asset_reference
from drama_factory.pipeline.local_reference_views import bind_local_reference_views
from drama_factory.pipeline.visual_production_plan import VisualPlanError, build_visual_production_plan
from test_screenplay import setup_series


def _image(rgb):
    out = io.BytesIO()
    Image.new("RGBA", (64, 64), (*rgb, 255)).save(out, format="PNG")
    return out.getvalue()


def _stage(db, sid, aid, root, rgb):
    raw = _image(rgb)
    created = stage_local_asset_reference(db, sid, aid, root, filename="view.png",
                                         content=raw, operator_attests_rights=True)
    assert created["source_sha256"] == hashlib.sha256(raw).hexdigest()
    return created["source_sha256"]


def test_independent_actor_views_use_real_byte_receipts_and_remain_unapproved(client, tmp_path):
    sid, _, aid, scene = setup_series(client, "independent views")
    db, root = client.app.state.db, tmp_path / "references"
    sources = {
        "front": _stage(db,sid,aid,root,(255,0,0)),
        "side": _stage(db,sid,aid,root,(0,255,0)),
        "back": _stage(db,sid,aid,root,(0,0,255)),
    }
    first = bind_local_reference_views(db,sid,aid,root,view_sources=sources)
    assert first == bind_local_reference_views(db,sid,aid,root,view_sources=sources)
    assert [x["view"] for x in first["views"]] == ["front","side","back"]
    assert len({x["source_sha256"] for x in first["views"]}) == 3
    assert len({x["png_sha256"] for x in first["views"]}) == 3
    assert all(x["asset_id"] == aid and x["asset_version"] == 1 for x in first["views"])
    assert all(x["rights_independently_verified"] is False
               and x["operator_approved_for_model"] is False for x in first["views"])
    assert first["model_submission_allowed"] is False
    assert first["paid_api_calls"] == 0
    with pytest.raises(VisualPlanError, match="unapproved"):
        build_visual_production_plan(
            {"schema_version":"g4-shot-asset-binding.v1","series_id":sid,
             "style_sha256":"a"*64,"selected_shot_ids":["s1"],
             "shots":[{"shot_id":"s1","characters":[{"asset_id":aid,"version":1}],
                       "character_ids":[aid],"scene_id":scene,
                       "scene_asset":{"asset_id":scene,"version":1},
                       "reference_mode":"prompt_anchor_only"}]},
            {"s1":{"actor_views":{aid:"front"},"prop_pins":[],"depends_on":[]}},
            first["views"],
        )


def test_duplicate_or_missing_view_or_forged_source_is_rejected(client,tmp_path):
    sid, _, aid, _ = setup_series(client,"views A")
    db,root=client.app.state.db,tmp_path/"refs"
    source=_stage(db,sid,aid,root,(100,50,25))
    for views in (
        {"front":source,"side":source,"back":source},
        {"front":source,"side":"a"*64,"back":"b"*64},
        {"front":source},
        {"front":source,"side":"b"*64,"back":"c"*64,"unknown":"d"*64},
    ):
        with pytest.raises(VisualPlanError):
            bind_local_reference_views(db,sid,aid,root,view_sources=views)
    other, _, other_actor, _ = setup_series(client, "views B")
    with pytest.raises(Exception):
        bind_local_reference_views(db,other,aid,root,view_sources={
            "front":source,"side":"b"*64,"back":"c"*64,
        })
    with pytest.raises(Exception):
        bind_local_reference_views(db,sid,other_actor,root,view_sources={
            "front":source,"side":"b"*64,"back":"c"*64,
        })


def test_scene_master_remains_local_only(client,tmp_path):
    sid, _, _, scene=setup_series(client,"views scene")
    db,root=client.app.state.db,tmp_path/"refs"
    source=_stage(db,sid,scene,root,(90,90,90))
    manifest=bind_local_reference_views(db,sid,scene,root,view_sources={"master":source})
    assert manifest["kind"]=="scene"
    assert manifest["views"][0]["view"]=="master"
    assert manifest["views"][0]["operator_approved_for_model"] is False
    with pytest.raises(VisualPlanError):
        bind_local_reference_views(db,sid,scene,root,view_sources={"front":source})
