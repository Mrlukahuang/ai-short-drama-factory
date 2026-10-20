"""G4: compose existing W2/FND-01 with FND-02/03 in one ZERO-CALL replay.

Inputs are versioned, locally inspected media and explicit signed operator
grants. The result is a sanitized audit receipt, not real model execution.
Do NOT use this function to bypass the W4/W5 content/release gates.
"""
from __future__ import annotations

from pathlib import Path

from drama_factory.pipeline.screenplay import Screenplay
from drama_factory.pipeline.screenplay_visual_bridge import plan_screenplay_visual_references

from drama_factory.pipeline.visual_production_plan import build_visual_production_plan
from drama_factory.pipeline.visual_keyframe_graph import build_keyframe_graph, shot_frame_entry
from drama_factory.pipeline.omni_media_envelope import (
    FakeOmniReferenceProvider, OmniMediaCapability, prepare_offline_omni_envelope,
)
from drama_factory.pipeline.visual_media_admission import (
    MediaAdmissionError, digest_json,
)


def fake_episode_visual_replay(
    w2_manifest: dict, shot_specs: dict[str, dict], gallery: list[dict], *,
    prompts: dict[str, str], image_paths_by_sha256: dict[str, Path],
    grants_by_shot: dict[str, dict], operator_verification_key: bytes,
    approved_frames: list[dict] | None = None,
    first_frame_required: bool = False,
    capability: OmniMediaCapability | None = None,
    now_epoch: int | None = None,
    reviewed_screenplay: Screenplay | None = None,
) -> dict:
    """Execute a full 12-shot dry-run with actual local PNG byte validation.

    No Base64 or private paths are returned; receipts may be stored without
    exposing images. All billing/network/real-video outcomes remain null.
    If supplied, a typed reviewed screenplay must match the complete W2 shot
    order, cast, scene and deterministic continuity before any media is read.
    """
    reviewed_plan = None
    if reviewed_screenplay is not None:
        if (not isinstance(reviewed_screenplay, Screenplay)
                or type(w2_manifest) is not dict
                or [s.shot_id for s in reviewed_screenplay.shots]
                != w2_manifest.get("selected_shot_ids")
                or type(shot_specs) is not dict
                or any(type(spec) is not dict
                       or type(spec.get("actor_views")) is not dict
                       or type(spec.get("prop_pins")) is not list
                       for spec in shot_specs.values())):
            raise MediaAdmissionError("Reviewed screenplay shot scope mismatch")
        reviewed_plan = plan_screenplay_visual_references(
            reviewed_screenplay, w2_manifest, gallery,
            actor_views={sid: spec["actor_views"] for sid, spec in shot_specs.items()},
            prop_pins={sid: spec["prop_pins"] for sid, spec in shot_specs.items()},
        )
    plan = build_visual_production_plan(
        w2_manifest, shot_specs, gallery,
        max_images_per_shot=(capability or OmniMediaCapability()).max_reference_images,
    )
    if reviewed_plan is not None and reviewed_plan["plan_sha256"] != plan["plan_sha256"]:
        raise MediaAdmissionError("Reviewed screenplay continuity or media pins mismatch")
    ids = [row["shot_id"] for row in plan["shots"]]
    if (type(prompts) is not dict or set(prompts) != set(ids)
            or type(grants_by_shot) is not dict or set(grants_by_shot) != set(ids)
            or type(image_paths_by_sha256) is not dict):
        raise MediaAdmissionError("Missing or out-of-scope full episode inputs")
    graph = build_keyframe_graph(
        plan, approved_frames if approved_frames is not None else [],
        first_frame_required=first_frame_required,
    )
    receipts = []
    provider = FakeOmniReferenceProvider()
    for shot in plan["shots"]:
        sid = shot["shot_id"]
        frame = shot_frame_entry(graph, sid)
        references = [
            image_paths_by_sha256.get(item["image"]["png_sha256"])
            for item in shot["selected_references"]
        ]
        first_sha = (frame["first_frame"] or {}).get("png_sha256")
        last_sha = (frame["last_frame"] or {}).get("png_sha256")
        envelope = prepare_offline_omni_envelope(
            plan, sid, original_prompt=prompts[sid],
            reference_paths=references,
            operator_grant=grants_by_shot[sid],
            verification_key=operator_verification_key,
            frame_graph=graph,
            first_frame_path=image_paths_by_sha256.get(first_sha),
            last_frame_path=image_paths_by_sha256.get(last_sha),
            capability=capability,
            now_epoch=now_epoch,
        )
        fake = provider.evaluate(envelope)
        receipts.append({
            "shot_id": sid, "request": envelope.receipt,
            "fake_result": fake,
        })
    out = {
        "schema": "g4-visual-spine-offline-replay.v1",
        "visual_plan_sha256": plan["plan_sha256"],
        "keyframe_graph_sha256": graph["graph_sha256"],
        "shots": receipts, "shot_count": len(receipts),
        "all_requests_offline_prepared": True,
        "real_video_generated": False,
        "provider_reference_applied": False,
        "new_paid_model_calls": 0, "actual_fee_usd": None,
        "g4_content_pass": False, "publish_approved": False,
    }
    out["replay_sha256"] = digest_json(out)
    return out
