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
