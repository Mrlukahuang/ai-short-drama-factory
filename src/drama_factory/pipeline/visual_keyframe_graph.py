"""G4 FND-03: deterministic storyboard/first-last-frame graph, offline only.

Derived from ViMax's camera/dependency concept and Jellyfish's frame readiness
gates. No image generation, downloads, edits, billing or W1-W5 mutations.
Human-approved frame metadata is a *claim*; byte-level and signed rights
admission belongs to visual_media_admission before any remote media use.
"""
from __future__ import annotations

from drama_factory.pipeline.visual_media_admission import (
    MediaAdmissionError, _plan_shot, digest_json, valid_sha,
)

SCHEMA = "g4-visual-keyframe-graph.v1"


class FrameGraphError(MediaAdmissionError):
    pass


def build_keyframe_graph(plan: dict, approved_frames: list[dict], *,
                         first_frame_required: bool = True) -> dict:
    """Map approved first/last images onto ordered shots and inherit last frames.

    Approvals may be from local human review and *never* count as true model
    media permission or a cryptographic operator grant.
    """
    if (type(plan) is not dict or type(plan.get("shots")) is not list
            or not 1 <= len(plan["shots"]) <= 12
            or type(approved_frames) is not list or len(approved_frames) > 24
            or type(first_frame_required) is not bool):
        raise FrameGraphError("Invalid frame graph input")
    shot_ids = []
    scenes = {}
    dependencies = {}
    for row in plan["shots"]:
        name = row.get("shot_id")
        _plan_shot(plan, name)
        if (type(row.get("scene_id")) is not str or not row["scene_id"]
                or type(row.get("depends_on")) is not list
                or any(dep not in shot_ids for dep in row["depends_on"])
                or len(set(row["depends_on"])) != len(row["depends_on"])):
            raise FrameGraphError("Invalid screenplay order or frame dependencies")
        scenes[name] = row["scene_id"]
        dependencies[name] = row["depends_on"]
        shot_ids.append(name)
    if len(set(shot_ids)) != len(shot_ids):
        raise FrameGraphError("Duplicate storyboard shot ID")
    registry = {}
    for row in approved_frames:
        if (type(row) is not dict
                or row.get("shot_id") not in scenes
                or row.get("kind") not in ("first", "last")
                or row.get("scene_id") != scenes[row["shot_id"]]
                or not valid_sha(row.get("png_sha256"))
                or row.get("human_reviewed") is not True
                or type(row.get("reviewer")) is not str or not row["reviewer"].strip()):
            raise FrameGraphError("Unapproved, foreign or corrupt storyboard frame")
        key = (row["shot_id"], row["kind"])
        if key in registry:
            raise FrameGraphError("Duplicate storyboard frame variant")
        registry[key] = {key: row[key] for key in (
            "shot_id", "kind", "scene_id", "png_sha256", "reviewer",
        )}
    graph = []
    for shot_id in shot_ids:
        first = registry.get((shot_id, "first"))
        inherited_from = None
        if first is None:
            # A previous shot's last frame is useful only when it is an
            # EXPLICIT dependency in the same scene, never an arbitrary sN-1.
            candidates = [
                d for d in dependencies[shot_id]
                if scenes[d] == scenes[shot_id] and (d, "last") in registry
            ]
            if candidates:
                inherited_from = candidates[-1]
                source = registry[(inherited_from, "last")]
                first = {**source, "kind": "first", "source_kind": "previous_last"}
        last = registry.get((shot_id, "last"))
        blockers = []
        if first_frame_required and first is None:
            blockers.append("first_frame_not_approved")
        graph.append({
            "shot_id": shot_id, "scene_id": scenes[shot_id],
            "first_frame": first, "last_frame": last,
            "inherited_from_shot_id": inherited_from,
            "readiness": "offline_candidate_only" if not blockers else "blocked",
            "blockers": blockers,
        })
    out = {
        "schema": SCHEMA, "visual_plan_sha256": plan["plan_sha256"],
        "frames": graph, "reference_frame_media_applied": False,
        "model_submission_allowed": False,
        "new_paid_model_calls": 0,
    }
    out["graph_sha256"] = digest_json(out)
    return out


def shot_frame_entry(graph: dict, shot_id: str, *, require_ready: bool = True) -> dict:
    if (type(graph) is not dict or graph.get("schema") != SCHEMA
            or not valid_sha(graph.get("graph_sha256"))
            or graph["graph_sha256"] != digest_json({
                k: v for k, v in graph.items() if k != "graph_sha256"
            })
            or graph.get("model_submission_allowed") is not False
            or type(graph.get("frames")) is not list):
        raise FrameGraphError("Unverifiable frame graph")
    matches = [row for row in graph["frames"] if row.get("shot_id") == shot_id]
    if len(matches) != 1:
        raise FrameGraphError("Unknown or duplicate frame graph shot")
    row = matches[0]
    if require_ready and row["blockers"]:
        raise FrameGraphError("Approved first frame unavailable")
    return row
