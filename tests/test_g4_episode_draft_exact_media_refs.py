"""G4 R4.4: real EpisodeDraft.reference_asset_ids -> FND plan -> Fake receipt.

No real model use, no Owner authorization. Explicit synthetic test grant only.
"""
from __future__ import annotations

import copy

import pytest

from drama_factory.pipeline.screenplay_visual_bridge import plan_screenplay_visual_references
from drama_factory.pipeline.visual_production_plan import VisualPlanError
from drama_factory.pipeline.visual_keyframe_graph import build_keyframe_graph, shot_frame_entry
from drama_factory.pipeline.visual_media_admission import (
    MediaAdmissionError, digest_json, issue_operator_grant,
)
from drama_factory.pipeline.visual_spine_offline import fake_episode_visual_replay
from test_g4_reviewed_screenplay_fake_media import _case, TEST_KEY


def _draft(data):
    screenplay = data["reviewed_screenplay"]
    draft = screenplay.to_episode_draft()
    pins = data["shot_specs"]
    for shot, bound in zip(draft.shots, data["w2_manifest"]["shots"]):
        assert shot.shot_id == bound["shot_id"]
        shot.reference_asset_ids = (
            list(bound["character_ids"])
            + [bound["scene_id"]]
            + [prop["asset_id"] for prop in pins[shot.shot_id]["prop_pins"]]
        )
    return draft


def _prepared(tmp_path, cast_count, shot_count, series_id):
    data = _case(tmp_path, cast_count, shot_count, series_id)
    draft = _draft(data)
    views = {
        sid: x["actor_views"] for sid, x in data["shot_specs"].items()
    }
    props = {
        sid: x["prop_pins"] for sid, x in data["shot_specs"].items()
    }
    plan = plan_screenplay_visual_references(
        data["reviewed_screenplay"], data["w2_manifest"], data["gallery"],
        actor_views=views, prop_pins=props, episode_draft=draft,
    )
    graph = build_keyframe_graph(
        plan, data["approved_frames"], first_frame_required=False,
    )
    grants = {}
    for shot in plan["shots"]:
        sid = shot["shot_id"]
        hashes = [
            ref["image"]["png_sha256"] for ref in shot["selected_references"]
        ]
        frame = shot_frame_entry(graph, sid)
        hashes.extend(f["png_sha256"] for f in (
            frame["first_frame"], frame["last_frame"]) if f is not None)
        grants[sid] = issue_operator_grant(
            plan, sid, hashes, reviewer="SYNTHETIC_TEST_ONLY",
            expiry_epoch=2_000_000_000, signing_key=TEST_KEY,
        )
    data["episode_draft"] = draft
    data["grants_by_shot"] = grants
    return data


@pytest.mark.parametrize("cast,count,series", [
    (1, 12, "proj_00000000000001"),
    (2, 6, "proj_00000000000002"),
])
def test_episode_draft_id_pins_reach_exact_fake_media_receipt(
    tmp_path, cast, count, series,
):
    data = _prepared(tmp_path, cast, count, series)
    replay = fake_episode_visual_replay(**data)
    assert replay["shot_count"] == count
    assert replay["new_paid_model_calls"] == 0
    assert replay["real_video_generated"] is False
    draft_sha = digest_json(data["episode_draft"].model_dump(mode="json"))
    assert all(
        shot["request"]["episode_draft_sha256"] == draft_sha
        for shot in replay["shots"]
    )
    assert all(shot["fake_result"]["is_mock"] for shot in replay["shots"])
    assert replay == fake_episode_visual_replay(**data)


def test_missing_foreign_reordered_and_unselected_references_fail_before_media(tmp_path):
    data = _prepared(tmp_path, 1, 12, "proj_00000000000001")
    for bad_refs in (
        [],
        ["actor_a"],
        ["scene_cafe", "actor_a"],
        ["actor_a", "another_series_scene"],
        ["actor_a", "scene_cafe", "foreign_prop"],
        ["actor_a", "actor_a", "scene_cafe"],
    ):
        trial = dict(data)
        draft = copy.deepcopy(data["episode_draft"])
        draft.shots[0].reference_asset_ids = bad_refs
        trial["episode_draft"] = draft
        with pytest.raises(VisualPlanError, match="references"):
            fake_episode_visual_replay(**trial)


def test_actor_dialogue_content_cannot_be_changed_in_draft(tmp_path):
    data = _prepared(tmp_path, 2, 6, "proj_00000000000002")
    altered = dict(data)
    draft = copy.deepcopy(data["episode_draft"])
    draft.shots[0].visual_description += " edited without review"
    altered["episode_draft"] = draft
    with pytest.raises(VisualPlanError, match="altered"):
        fake_episode_visual_replay(**altered)


def test_old_signed_grant_does_not_authorize_new_draft_scoped_visual_plan(tmp_path):
    data = _prepared(tmp_path, 1, 12, "proj_00000000000001")
    # Build the same raw W2/FND plan without the EpisodeDraft SHA, then use
    # the original per-shot grant signed by the older, weaker scope.
    from drama_factory.pipeline.visual_production_plan import build_visual_production_plan
    weak_plan = build_visual_production_plan(
        data["w2_manifest"], data["shot_specs"], data["gallery"],
    )
    shot = weak_plan["shots"][0]
    old_hashes = [r["image"]["png_sha256"] for r in shot["selected_references"]]
    # No frames included: this grant is intentionally insufficient.
    weak_grant = issue_operator_grant(
        weak_plan, "s01", old_hashes, reviewer="SYNTHETIC_TEST_ONLY",
        expiry_epoch=2_000_000_000, signing_key=TEST_KEY,
    )
    trial = dict(data)
    trial["grants_by_shot"] = {**data["grants_by_shot"], "s01": weak_grant}
    with pytest.raises(MediaAdmissionError, match="grant"):
        fake_episode_visual_replay(**trial)
