"""FND-01 local dry-run contracts; no model, real media, network or DB."""
import copy
import hashlib
import pytest
from drama_factory.pipeline.visual_production_plan import (
    VisualPlanError, build_visual_production_plan, impacted_shots,
)


def _sha(seed):
    return hashlib.sha256(seed.encode()).hexdigest()


def _data(count=12):
    actors = ["actor_a", "actor_b"]
    scene = "scene_cafe"
    series = "proj_00000000000001"
    shots = []
    directives = {}
    gallery = []
    for a in actors:
        for view in ("front", "side", "back"):
            gallery.append(dict(series_id=series, asset_id=a, kind="actor", asset_version=1,
                                view=view, source_sha256=_sha(a+view+"source"),
                                png_sha256=_sha(a+view+"png"),
                                rights_independently_verified=True, operator_approved_for_model=True))
    for kind, asset_id in (("scene", scene), ("prop", "cup"), ("prop", "table")):
        gallery.append(dict(series_id=series, asset_id=asset_id, kind=kind, asset_version=1,
                            view="master", source_sha256=_sha(asset_id+"source"),
                            png_sha256=_sha(asset_id+"png"),
                            rights_independently_verified=True, operator_approved_for_model=True))
    for i in range(count):
        sid = f"s{i+1:02d}"
        shots.append(dict(shot_id=sid, character_ids=actors,
                          characters=[dict(asset_id=a, version=1) for a in actors],
                          scene_id=scene, scene_asset=dict(asset_id=scene, version=1),
                          reference_mode="prompt_anchor_only"))
        directives[sid] = dict(actor_views={a: "front" if i % 2 == 0 else "side" for a in actors},
                               prop_pins=[dict(asset_id="cup",asset_version=1),
                                          dict(asset_id="table",asset_version=1)],
                               depends_on=[f"s{i:02d}"] if i in (1,2,3) else [])
    manifest = dict(schema_version="g4-shot-asset-binding.v1", series_id=series,
                    style_sha256=_sha("felt"), selected_shot_ids=[s["shot_id"] for s in shots],
                    shots=shots)
    return manifest, directives, gallery


def _build(data=None):
    return build_visual_production_plan(*(data or _data()))


def test_twelve_shot_plan_is_deterministic_and_stays_offline():
    first = _build()
    second = _build()
    assert first == second
    assert len(first["shots"]) == 12
    assert first["model_submission_allowed"] is False
    assert first["provider_reference_applied"] is False
    assert first["production_assets_verified"] is False
    assert first["new_paid_model_calls"] == 0
    assert all(x["candidate_image_count"] == 5 for x in first["shots"])
    assert first["shots"][0]["selected_references"][0]["image"]["view"] == "front"
    assert first["shots"][1]["selected_references"][0]["image"]["view"] == "side"
    assert "png_sha256" in first["shots"][0]["selected_references"][0]["image"]
    assert "specification_sha256" not in first["shots"][0]["selected_references"][0]["image"]


def test_unapproved_or_unverified_reference_is_rejected():
    for field in ("rights_independently_verified", "operator_approved_for_model"):
        data = list(_data())
        data[2] = copy.deepcopy(data[2])
        data[2][0][field] = False
        with pytest.raises(VisualPlanError, match="unapproved"):
            _build(tuple(data))


def test_missing_character_back_image_fails_even_when_front_selected():
    a,b,c = _data()
    c = [ref for ref in c if not (ref["asset_id"] == "actor_a" and ref["view"] == "back")]
    with pytest.raises(VisualPlanError, match="unavailable"):
        _build((a,b,c))


def test_swapped_old_asset_version_not_silent():
    a,b,c=_data()
    a["shots"][0]["characters"][0]["version"] = 2
    with pytest.raises(VisualPlanError, match="unavailable"):
        _build((a,b,c))


def test_foreign_reference_rejected():
    a,b,c=_data()
    c[0]["series_id"] = "foreign"
    with pytest.raises(VisualPlanError, match="unapproved"):
        _build((a,b,c))


def test_invalid_view_or_missing_actor_rejected():
    a,b,c=_data()
    b["s01"]["actor_views"]["actor_a"] = "oblique_unapproved"
    with pytest.raises(VisualPlanError, match="camera angle"):
        _build((a,b,c))
    a,b,c=_data()
    b["s01"]["actor_views"].pop("actor_a")
    with pytest.raises(VisualPlanError, match="Actors"):
        _build((a,b,c))


def test_prop_version_and_limit_rejected():
    a,b,c=_data()
    b["s01"]["prop_pins"][0]["asset_version"] = 9
    with pytest.raises(VisualPlanError, match="unavailable"):
        _build((a,b,c))
    with pytest.raises(VisualPlanError, match="ceiling"):
        build_visual_production_plan(*_data(), max_images_per_shot=4)


def test_duplicate_reference_and_prop_rejected():
    a,b,c=_data()
    c.append(copy.deepcopy(c[0]))
    with pytest.raises(VisualPlanError,match="Duplicated"):
        _build((a,b,c))
    a,b,c=_data()
    b["s01"]["prop_pins"].append(copy.deepcopy(b["s01"]["prop_pins"][0]))
    with pytest.raises(VisualPlanError,match="duplicate prop"):
        _build((a,b,c))


def test_future_dependency_cycle_rejected():
    a,b,c=_data()
    b["s01"]["depends_on"] = ["s02"]
    with pytest.raises(VisualPlanError, match="future"):
        _build((a,b,c))


def test_shot_graph_only_invalidates_true_downstream_dependents():
    plan=_build()
    assert impacted_shots(plan,{"s02"}) == ["s02", "s03", "s04"]
    assert impacted_shots(plan,{"s07"}) == ["s07"]
    assert impacted_shots(plan,set()) == []
    with pytest.raises(VisualPlanError, match="unknown"):
        impacted_shots(plan,{"s13"})


def test_wrong_w2_or_mismatched_shot_prevented():
    a,b,c=_data()
    a["schema_version"]="made_up"
    with pytest.raises(VisualPlanError,match="Invalid W2"):
        _build((a,b,c))
    a,b,c=_data()
    a["shots"][0]["character_ids"]=["actor_b", "actor_a"]
    with pytest.raises(VisualPlanError,match="Actors"):
        _build((a,b,c))
