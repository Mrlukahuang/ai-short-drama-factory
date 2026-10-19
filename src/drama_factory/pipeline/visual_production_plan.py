"""G4 FND-01: offline visual reference plan, never a provider permission.

Inputs are projections of the immutable W2 manifest and local reference records.
This module does not read image files or verify remote usage rights. Those
trust boundaries belong to the upstream local media verifier and a future
separately-approved model admission layer. No model request can be submitted
from the result of this module.
"""
from __future__ import annotations

import hashlib
import json
import re

SCHEMA = "g4-fnd01-visual-production-plan.v1"
W2_SCHEMA = "g4-shot-asset-binding.v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_VIEWS = frozenset({"front", "side", "back", "three_quarter"})
_REQUIRED_VIEWS = ("front", "side", "back")


class VisualPlanError(ValueError):
    """Fixed, non-sensitive failure for invalid production-reference inputs."""


def _sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _digest(value: object) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _media_index(gallery: list[dict], series_id: str) -> dict[tuple, dict]:
    if type(gallery) is not list or len(gallery) > 200:
        raise VisualPlanError("Invalid visual reference catalog size")
    index = {}
    for item in gallery:
        if (type(item) is not dict or item.get("series_id") != series_id
                or item.get("kind") not in {"actor", "scene", "prop"}
                or type(item.get("asset_id")) is not str or not item["asset_id"]
                or type(item.get("asset_version")) is not int or item["asset_version"] < 1
                or type(item.get("view")) is not str
                or not _digest(item.get("source_sha256"))
                or not _digest(item.get("png_sha256"))
                or item.get("rights_independently_verified") is not True
                or item.get("operator_approved_for_model") is not True):
            raise VisualPlanError("Unknown, unapproved or inconsistent visual reference")
        if (item["kind"] == "actor" and item["view"] not in _VIEWS) or (
                item["kind"] != "actor" and item["view"] != "master"):
            raise VisualPlanError("Invalid reference angle or asset kind")
        key = (item["kind"], item["asset_id"], item["asset_version"], item["view"])
        if key in index:
            raise VisualPlanError("Duplicated visual reference identity")
        # Keep only canonical, nonsensitive metadata: never image bytes/paths.
        index[key] = {k: item[k] for k in (
            "series_id", "kind", "asset_id", "asset_version", "view",
            "source_sha256", "png_sha256")}
    return index


def _select(index: dict, kind: str, asset_id: str, version: int, view: str) -> dict:
    image = index.get((kind, asset_id, version, view))
    if image is None:
        raise VisualPlanError("Required versioned image reference is unavailable")
    return dict(image)


def build_visual_production_plan(w2_manifest: dict, shot_specs: dict[str, dict],
                                 approved_gallery: list[dict], *,
                                 max_images_per_shot: int = 8) -> dict:
    """Deterministic offline plan for W2 shots; never submits/authorizes models.

    The gallery's approval flags are caller assertions, NOT cryptographic
    attestations; the result is always offline-only. Production must reverify
    image bytes, actual legal rights and operator approval independently.
    """
    if (type(w2_manifest) is not dict
            or w2_manifest.get("schema_version") != W2_SCHEMA
            or type(w2_manifest.get("series_id")) is not str
            or not w2_manifest["series_id"]
            or not _digest(w2_manifest.get("style_sha256"))
            or type(w2_manifest.get("shots")) is not list
            or type(w2_manifest.get("selected_shot_ids")) is not list
            or type(max_images_per_shot) is not int
            or not 1 <= max_images_per_shot <= 10):
        raise VisualPlanError("Invalid W2 manifest or reference image ceiling")
    shots = w2_manifest["shots"]
    ordered = w2_manifest["selected_shot_ids"]
    if (not 1 <= len(shots) <= 12 or len(shots) != len(ordered)
            or not all(type(n) is str and n for n in ordered)
            or len(set(ordered)) != len(ordered)
            or any(type(s) is not dict or s.get("shot_id") != name
                   for s, name in zip(shots, ordered))
            or type(shot_specs) is not dict or set(shot_specs) != set(ordered)):
        raise VisualPlanError("W2 shot identities or visual shot inputs mismatch")
    index = _media_index(approved_gallery, w2_manifest["series_id"])
    output = []
    completed = set()
    for shot in shots:
        shot_id = shot["shot_id"]
        spec = shot_specs[shot_id]
        cast = shot.get("characters")
        scene = shot.get("scene_asset")
        if (type(spec) is not dict or type(cast) is not list or not cast
                or type(scene) is not dict or type(spec.get("actor_views")) is not dict
                or type(spec.get("prop_pins")) is not list
                or type(spec.get("depends_on")) is not list):
            raise VisualPlanError("Shot needs explicit camera, actor, scene and prop pins")
        actor_ids = [a.get("asset_id") for a in cast if type(a) is dict]
        if (len(actor_ids) != len(cast) or len(set(actor_ids)) != len(actor_ids)
                or set(spec["actor_views"]) != set(actor_ids)
                or shot.get("character_ids") != actor_ids
                or shot.get("scene_id") != scene.get("asset_id")
                or shot.get("reference_mode") != "prompt_anchor_only"):
            raise VisualPlanError("Actors or scene differ from the immutable W2 plan")
        deps = spec["depends_on"]
        if (len(set(deps)) != len(deps) or any(dep not in completed for dep in deps)):
            raise VisualPlanError("Shot dependency cycle, missing or future reference")
        refs = []
        for actor in cast:
            asset_id, version = actor["asset_id"], actor["version"]
            if type(version) is not int or version < 1:
                raise VisualPlanError("Invalid pinned actor version")
            for view in _REQUIRED_VIEWS:
                _select(index, "actor", asset_id, version, view)
            selected_view = spec["actor_views"][asset_id]
            if selected_view not in _VIEWS:
                raise VisualPlanError("Invalid actor camera angle")
            refs.append({"role": "actor", "shot_actor_id": asset_id,
                         "image": _select(index, "actor", asset_id, version, selected_view)})
        if type(scene.get("version")) is not int or scene["version"] < 1:
            raise VisualPlanError("Invalid pinned scene version")
        refs.append({"role": "scene", "image": _select(
            index, "scene", scene["asset_id"], scene["version"], "master")})
        prop_seen = set()
        for prop in spec["prop_pins"]:
            if (type(prop) is not dict or set(prop) != {"asset_id", "asset_version"}
                    or type(prop["asset_id"]) is not str or not prop["asset_id"]
                    or type(prop["asset_version"]) is not int or prop["asset_version"] < 1
                    or prop["asset_id"] in prop_seen):
                raise VisualPlanError("Invalid or duplicate prop pin")
            prop_seen.add(prop["asset_id"])
            refs.append({"role": "prop", "image": _select(
                index, "prop", prop["asset_id"], prop["asset_version"], "master")})
        if len(refs) > max_images_per_shot:
            raise VisualPlanError("Shot references exceed model capability ceiling")
        output.append({"shot_id": shot_id, "scene_id": shot["scene_id"],
                       "depends_on": list(deps), "selected_references": refs,
                       "candidate_image_count": len(refs),
                       "review_state": "offline_candidate_only"})
        completed.add(shot_id)
    plan = {
        "schema": SCHEMA,
        "series_id": w2_manifest["series_id"],
        "w2_manifest_sha256": _sha(w2_manifest),
        "style_sha256": w2_manifest["style_sha256"],
        "shots": output,
        "provider_reference_applied": False,
        "production_assets_verified": False,
        "model_submission_allowed": False,
        "new_paid_model_calls": 0,
    }
    plan["plan_sha256"] = _sha(plan)
    return plan


def impacted_shots(plan: dict, changed_shot_ids: set[str]) -> list[str]:
    """Shot-graph invalidation, preserving unaffected historical clip versions."""
    if type(plan) is not dict or plan.get("schema") != SCHEMA:
        raise VisualPlanError("Invalid visual production plan")
    shots = plan.get("shots")
    if type(shots) is not list:
        raise VisualPlanError("Invalid visual shot list")
    ids = [s["shot_id"] for s in shots]
    if type(changed_shot_ids) is not set or not changed_shot_ids.issubset(set(ids)):
        raise VisualPlanError("Cannot invalidate unknown or unpinned shots")
    affected = set(changed_shot_ids)
    for s in shots:
        if any(dep in affected for dep in s["depends_on"]):
            affected.add(s["shot_id"])
    return [shot_id for shot_id in ids if shot_id in affected]
