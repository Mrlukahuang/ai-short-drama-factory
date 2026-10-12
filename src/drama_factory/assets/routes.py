"""Metadata-only reference assets. No binary upload or public media serving."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Request

from ..db import new_id, timestamp
from .references import ApproveReference, MEDIA_TO_ASSET_KIND, ReferenceCreate

router = APIRouter(prefix="/api/v1/series/{series_id}/assets/{asset_id}/references",
                   tags=["asset-references"])


def require_asset(db, series_id: str, asset_id: str) -> dict:
    asset = db.one(
        "SELECT id,series_id,kind FROM series_assets WHERE id=? AND series_id=?",
        (asset_id, series_id),
    )
    if asset is None:
        raise HTTPException(404, "Asset not found in this series")
    return asset


@router.post("", status_code=201)
def attach_reference(series_id: str, asset_id: str, body: ReferenceCreate, request: Request):
    db = request.app.state.db
    asset = require_asset(db, series_id, asset_id)
    expected_kind = MEDIA_TO_ASSET_KIND[body.media_kind]
    if asset["kind"] != expected_kind:
        raise HTTPException(422, "Reference type cannot be attached to this asset kind")
    if not body.storage_key.startswith(f"series/{series_id}/"):
        raise HTTPException(422, "Object storage key must be scoped to its series")
    ref_id = new_id("ref")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        version = conn.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM asset_references WHERE asset_id=?",
            (asset_id,),
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO asset_references
            (id,series_id,asset_id,version,media_kind,storage_key,sha256,
             provenance_json,status,created_at,approved_at,approved_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ref_id, series_id, asset_id, version, body.media_kind,
                body.storage_key, body.sha256, body.model_dump_json(),
                "pending_review", timestamp(), None, None,
            ),
        )
    return {
        "reference_id": ref_id, "asset_id": asset_id, "series_id": series_id,
        "version": version, "status": "pending_review", "media_uploaded": False,
    }


@router.get("")
def references(series_id: str, asset_id: str, request: Request):
    db = request.app.state.db
    require_asset(db, series_id, asset_id)
    return db.many(
        """SELECT id,asset_id,version,media_kind,storage_key,sha256,status,
           created_at,approved_at,approved_by FROM asset_references
           WHERE series_id=? AND asset_id=? ORDER BY version DESC""",
        (series_id, asset_id),
    )


@router.post("/{reference_id}/approve")
def approve_reference(
    series_id: str, asset_id: str, reference_id: str,
    body: ApproveReference, request: Request,
):
    db = request.app.state.db
    require_asset(db, series_id, asset_id)
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        ref = conn.execute(
            """SELECT id,status FROM asset_references
            WHERE id=? AND series_id=? AND asset_id=?""",
            (reference_id, series_id, asset_id),
        ).fetchone()
        if ref is None:
            raise HTTPException(404, "Reference not found in this series and asset")
        if ref["status"] != "pending_review":
            raise HTTPException(409, "Reference was already reviewed")
        conn.execute(
            """UPDATE asset_references
            SET status='approved',approved_at=?,approved_by=?
            WHERE id=? AND status='pending_review'""",
            (timestamp(), body.reviewer_label, reference_id),
        )
    return {"reference_id": reference_id, "status": "approved", "external_calls": 0}
