"""Read-only bridge from REAL versioned local gallery files to FND-01 view roles.

Does not infer angles from image pixels, invent a viewpoint, grant legal rights,
sign HMAC grants, or send media to a provider. A trusted operator must separately
declare each angle and attest image-use permission.
"""
from __future__ import annotations

from pathlib import Path

from drama_factory.db import Database
from .local_asset_references import list_local_asset_references, _asset_row
from .visual_production_plan import VisualPlanError

_ACTOR_VIEWS = ("front", "side", "back", "three_quarter")


def bind_local_reference_views(
    db: Database, series_id: str, asset_id: str, root: Path, *,
    view_sources: dict[str, str],
) -> dict:
    """Return locally verified, NOT model-approved gallery metadata.

    Actor requires independently selected front/side/back source images.
    Scene/prop requires only master. Reject using one image as multiple angles.
    SHA checks refer to the actual staged RGB PNG and its immutable source.
    """
    if type(view_sources) is not dict:
        raise VisualPlanError("Explicit reference view mapping required")
    row = _asset_row(db, series_id, asset_id)
    required = {"front", "side", "back"} if row["kind"] == "actor" else {"master"}
    permitted = set(_ACTOR_VIEWS) if row["kind"] == "actor" else {"master"}
    if (not required.issubset(view_sources)
            or not set(view_sources).issubset(permitted)
            or any(type(v) is not str or not v for v in view_sources.values())
            or len(set(view_sources.values())) != len(view_sources)):
        raise VisualPlanError("Missing, duplicate or unsupported image viewpoints")
    staged = list_local_asset_references(db, series_id, asset_id, root)
    by_source = {x["source_sha256"]: x for x in staged}
    if not set(view_sources.values()).issubset(by_source):
        raise VisualPlanError("View source not verified in the scoped asset gallery")
    ordered = [v for v in (*_ACTOR_VIEWS, "master") if v in view_sources]
    return {
        "schema": "g4-local-view-provenance.v1",
        "series_id": series_id,
        "asset_id": asset_id,
        "kind": row["kind"],
        "asset_version": row["version"],
        "views": [{
            "series_id": series_id,
            "kind": row["kind"], "asset_id": asset_id,
            "asset_version": row["version"], "view": view,
            "source_sha256": by_source[view_sources[view]]["source_sha256"],
            "png_sha256": by_source[view_sources[view]]["png_sha256"],
            # Self-attestation is not independent legal verification.
            "rights_independently_verified": False,
            "operator_approved_for_model": False,
        } for view in ordered],
        "operator_review_required": True,
        "model_submission_allowed": False,
        "paid_api_calls": 0,
    }


def build_unapproved_shot_image_review(
    w2_manifest: dict, inventories_by_actor: dict[str, dict],
    folders_by_actor: dict[str, Path],
    shot_actor_views: dict[str, dict[str, str]],
) -> dict:
    """Read REAL image bytes and pin per-shot review candidates, not approvals.

    Requires an existing W2 asset/version/specification pin for every actor and
    scene. Does not stage a DB asset, mint rights or HMAC, make a video request,
    or trust inventory labels as visually correct camera angles. Returned JSON
    contains only hashes, basename and IDs; all media remains local.
    """
    import hashlib
    import re

    from .local_asset_references import _canonical_png
    from .visual_media_admission import digest_json, valid_sha

    if (type(w2_manifest) is not dict
            or w2_manifest.get("schema_version") != "g4-shot-asset-binding.v1"
            or type(w2_manifest.get("series_id")) is not str
            or not w2_manifest["series_id"]
            or not valid_sha(w2_manifest.get("style_sha256"))
            or type(w2_manifest.get("selected_shot_ids")) is not list
            or type(w2_manifest.get("shots")) is not list
            or not 1 <= len(w2_manifest["shots"]) <= 12
            or type(inventories_by_actor) is not dict
            or type(folders_by_actor) is not dict
            or type(shot_actor_views) is not dict):
        raise VisualPlanError("Invalid W2 or actual image review inputs")

    shots = w2_manifest["shots"]
    ids = w2_manifest["selected_shot_ids"]
    if (len(ids) != len(shots) or len(set(ids)) != len(ids)
            or any(type(s) is not dict or s.get("shot_id") != sid
                   for s, sid in zip(shots, ids))
            or set(shot_actor_views) != set(ids)):
        raise VisualPlanError("Shot review identity or order mismatch")

    actors = {}
    for shot in shots:
        cast = shot.get("characters")
        scene = shot.get("scene_asset")
        if (type(cast) is not list or not cast or type(scene) is not dict
                or shot.get("reference_mode") != "prompt_anchor_only"
                or type(shot.get("character_ids")) is not list
                or shot.get("character_ids") != [
                    a.get("asset_id") for a in cast if type(a) is dict
                ] or len(set(shot["character_ids"])) != len(cast)
                or shot.get("scene_id") != scene.get("asset_id")
                or type(scene.get("version")) is not int
                or scene["version"] < 1
                or not valid_sha(scene.get("specification_sha256"))):
            raise VisualPlanError("Unpinned W2 scene or actor shot")
        for actor in cast:
            if (type(actor) is not dict
                    or type(actor.get("asset_id")) is not str
                    or not actor["asset_id"]
                    or type(actor.get("version")) is not int
                    or actor["version"] < 1
                    or not valid_sha(actor.get("specification_sha256"))):
                raise VisualPlanError("Unpinned actor specification")
            pin = (actor["version"], actor["specification_sha256"])
            if actor["asset_id"] in actors and actors[actor["asset_id"]] != pin:
                raise VisualPlanError("Actor changes version between reviewed shots")
            actors[actor["asset_id"]] = pin

    if set(inventories_by_actor) != set(actors) or set(folders_by_actor) != set(actors):
        raise VisualPlanError("Missing or foreign actor image inventory")

    verified = {}
    for aid in sorted(actors):
        inventory, folder = inventories_by_actor[aid], folders_by_actor[aid]
        if (type(inventory) is not dict
                or inventory.get("schema") != "g4-local-operator-image-inventory.v1"
                or inventory.get("model_submission_allowed") is not False
                or inventory.get("operator_approved_for_model") is not False
                or inventory.get("rights_independently_verified") is not False
                or type(inventory.get("images")) is not list
                or not 3 <= len(inventory["images"]) <= 20
                or type(folder) is not Path
                or any(path.is_symlink() for path in (folder, *folder.parents))
                or not folder.is_dir()):
            raise VisualPlanError("Untrusted local image inventory or approval claim")
        index = {}
        original = set()
        normalized = set()
        for item in inventory["images"]:
            if type(item) is not dict:
                raise VisualPlanError("Invalid inventoried image")
            view = item.get("role")
            if view not in _ACTOR_VIEWS:
                continue  # Expressions/actions are NOT camera angles.
            name = item.get("filename")
            sha = item.get("source_sha256")
            if (view in index or type(name) is not str
                    or re.fullmatch(r"[A-Za-z0-9_.-]{1,160}\.png", name) is None
                    or name in (".", "..") or not valid_sha(sha)
                    or sha in original):
                raise VisualPlanError("Duplicated or invalid physical camera view")
            path = folder / name
            if path.is_symlink() or not path.is_file():
                raise VisualPlanError("Physical camera view missing")
            try:
                with path.open("rb") as handle:
                    raw = handle.read(8 * 1024 * 1024 + 1)
            except OSError:
                raise VisualPlanError("Physical camera view unreadable") from None
            if (not 100 <= len(raw) <= 8 * 1024 * 1024
                    or hashlib.sha256(raw).hexdigest() != sha):
                raise VisualPlanError("Physical camera view SHA or byte limit mismatch")
            try:
                canonical, _, _, _ = _canonical_png(raw)
            except ValueError:
                raise VisualPlanError("Physical camera view not decodable") from None
            canonical_sha = hashlib.sha256(canonical).hexdigest()
            if canonical_sha in normalized:
                raise VisualPlanError("Duplicated normalized camera view")
            original.add(sha)
            normalized.add(canonical_sha)
            index[view] = {
                "series_id": w2_manifest["series_id"], "kind": "actor",
                "asset_id": aid, "asset_version": actors[aid][0],
                "specification_sha256": actors[aid][1],
                "view": view, "filename": name, "source_sha256": sha,
                "png_sha256": canonical_sha,
                "visual_angle_human_verified": False,
                "rights_independently_verified": False,
                "operator_approved_for_model": False,
            }
        if not {"front", "side", "back"}.issubset(index):
            raise VisualPlanError("Physical front/side/back views required")
        verified[aid] = index

    rows = []
    for shot, sid in zip(shots, ids):
        views = shot_actor_views[sid]
        if (type(views) is not dict
                or set(views) != set(shot["character_ids"])):
            raise VisualPlanError("Shot viewpoint actors differ from W2 cast")
        selected = []
        for aid in shot["character_ids"]:
            view = views[aid]
            if type(view) is not str or view not in verified[aid]:
                raise VisualPlanError("Unverified camera view selection")
            selected.append(dict(verified[aid][view]))
        rows.append({
            "shot_id": sid, "scene_id": shot["scene_id"],
            "scene_asset_version": shot["scene_asset"]["version"],
            "scene_specification_sha256": shot["scene_asset"]["specification_sha256"],
            "actor_image_candidates": selected,
            "blockers": [
                "human_viewpoint_review_required",
                "scene_reference_media_not_reviewed",
                "rights_and_provider_use_not_approved",
            ],
        })
    result = {
        "schema": "g4-actual-image-shot-review.v1",
        "series_id": w2_manifest["series_id"],
        "w2_manifest_sha256": digest_json(w2_manifest),
        "shots": rows, "shot_count": len(rows),
        "actual_png_bytes_checked": True,
        "angle_semantics_human_verified": False,
        "model_submission_allowed": False,
        "provider_reference_applied": False,
        "new_paid_model_calls": 0,
    }
    result["review_sha256"] = digest_json(result)
    return result
