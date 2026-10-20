"""Generic shot-ID bridge: reviewed screenplay + W2 pins -> FND-01 input.

Never mints legal/remote-model approval, invents images, or changes versions.
"""
from __future__ import annotations

from drama_factory.models import EpisodeDraft
from .screenplay import Screenplay
from .visual_production_plan import build_visual_production_plan, VisualPlanError
from .visual_media_admission import digest_json


def plan_screenplay_visual_references(
    screenplay: Screenplay, w2_manifest: dict, gallery: list[dict], *,
    actor_views: dict[str, dict[str, str]],
    prop_pins: dict[str, list[dict]],
    episode_draft: EpisodeDraft | None = None,
) -> dict:
    if not isinstance(screenplay, Screenplay) or type(w2_manifest) is not dict:
        raise VisualPlanError("Typed screenplay and W2 binding required")
    selected = w2_manifest.get("selected_shot_ids")
    w2_shots = w2_manifest.get("shots")
    if (w2_manifest.get("series_id") != screenplay.series_id
            or type(selected) is not list or type(w2_shots) is not list
            or len(selected) != len(w2_shots)
            or type(actor_views) is not dict or type(prop_pins) is not dict
            or set(actor_views) != set(selected) or set(prop_pins) != set(selected)):
        raise VisualPlanError("Series, version pins or shot specification mismatch")
    by_id = {shot.shot_id: shot for shot in screenplay.shots}
    if len(by_id) != len(screenplay.shots):
        raise VisualPlanError("Duplicate screenplay shot")
    completed = set()
    specs = {}
    for record, shot_id in zip(w2_shots, selected):
        if (type(record) is not dict or record.get("shot_id") != shot_id
                or shot_id not in by_id):
            raise VisualPlanError("W2 shot must match reviewed screenplay order")
        shot = by_id[shot_id]
        if (shot.character_ids != record.get("character_ids")
                or shot.scene_id != record.get("scene_id")):
            raise VisualPlanError("Screenplay and bound cast or scene differ")
        if (type(actor_views[shot_id]) is not dict
                or set(actor_views[shot_id]) != set(shot.character_ids)
                or type(prop_pins[shot_id]) is not list):
            raise VisualPlanError("Explicit shot actor angles and props required")
        # Continuity is a dependency of the PRECEDING selected shot.
        # Shot graph may be refined later, but must not silently jump/rewire.
        previous = selected[len(completed)-1] if completed else None
        specs[shot_id] = {
            "actor_views": dict(actor_views[shot_id]),
            "prop_pins": list(prop_pins[shot_id]),
            "depends_on": [previous] if previous else [],
        }
        completed.add(shot_id)
    # EpisodeDraft.reference_asset_ids is the production-level reference list.
    # It must mirror the reviewed screenplay exactly except for this explicit
    # ordered actor/scene/prop list. Empty legacy defaults never become approval.
    if episode_draft is not None:
        if not isinstance(episode_draft, EpisodeDraft):
            raise VisualPlanError("Typed EpisodeDraft required for media reference pins")
        expected_episode = screenplay.to_episode_draft()
        if (len(episode_draft.shots) != len(expected_episode.shots)
                or episode_draft.title != expected_episode.title
                or episode_draft.episode_number != expected_episode.episode_number
                or episode_draft.target_duration_seconds
                != expected_episode.target_duration_seconds):
            raise VisualPlanError("EpisodeDraft does not match reviewed screenplay")
        selected_ids = set(selected)
        for actual, expected in zip(episode_draft.shots, expected_episode.shots):
            received = actual.model_dump(mode="json")
            pinned = received.pop("reference_asset_ids")
            baseline = expected.model_dump(mode="json")
            baseline.pop("reference_asset_ids")
            if received != baseline:
                raise VisualPlanError("EpisodeDraft altered reviewed screenplay content")
            if actual.shot_id not in selected_ids:
                if pinned:
                    raise VisualPlanError("EpisodeDraft references unselected shot")
                continue
            row = next(s for s in w2_shots if s["shot_id"] == actual.shot_id)
            props = prop_pins[actual.shot_id]
            ids = list(row["character_ids"]) + [row["scene_id"]] + [
                p["asset_id"] for p in props if type(p) is dict
            ]
            if (not all(type(x) is str and x for x in ids)
                    or len(set(ids)) != len(ids) or pinned != ids):
                raise VisualPlanError("EpisodeDraft image references differ from W2 assets")
    plan = build_visual_production_plan(w2_manifest, specs, gallery)
    if episode_draft is not None:
        # Carry this exact upstream JSON SHA into the signed shot visual plan
        # and future FND-02 grant scope; never promote it to usage permission.
        plan["episode_draft_sha256"] = digest_json(
            episode_draft.model_dump(mode="json")
        )
        plan["plan_sha256"] = digest_json({
            key: value for key, value in plan.items() if key != "plan_sha256"
        })
    if plan["model_submission_allowed"] is not False:
        raise VisualPlanError("Visual planner unexpectedly permitted submission")
    return plan
