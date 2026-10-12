"""Internal-only versioned rights review endpoints; not a production admin console."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request

from ..db import new_id, timestamp
from .rights import RightsReviewCreate, evaluate_eligibility

router = APIRouter(prefix="/api/v1/novels/{source_id}", tags=["novel-rights"])


@router.post("/rights-reviews", status_code=201)
def record_rights_review(source_id: str, body: RightsReviewCreate, request: Request):
    db = request.app.state.db
    source = db.one("SELECT * FROM novel_sources WHERE id=?", (source_id,))
    if source is None:
        raise HTTPException(404, "Novel not found")
    if (
        body.decision == "approved"
        and (source["rights_status"] == "pending"
             or "screen_adaptation" not in [x.strip() for x in source["rights_scope"].split(",")])
    ):
        raise HTTPException(403, "Cannot approve a source with unconfirmed adaptation rights")
    review_id = new_id("rights")
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        version = conn.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM novel_rights_reviews WHERE source_id=?",
            (source_id,),
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO novel_rights_reviews
            (id,source_id,version,review_json,created_at) VALUES (?,?,?,?,?)""",
            (review_id, source_id, version, body.model_dump_json(), timestamp()),
        )
    return {
        "review_id": review_id, "source_id": source_id,
        "version": version, "decision": body.decision,
        "model_calls_enabled": False,
    }


@router.get("/rights-reviews")
def list_rights_reviews(source_id: str, request: Request):
    db = request.app.state.db
    if db.one("SELECT id FROM novel_sources WHERE id=?", (source_id,)) is None:
        raise HTTPException(404, "Novel not found")
    return db.many(
        """SELECT id,source_id,version,review_json,created_at
        FROM novel_rights_reviews WHERE source_id=? ORDER BY version DESC""",
        (source_id,),
    )


@router.get("/rights-eligibility")
def check_rights_eligibility(
    source_id: str, request: Request,
    territory: str = Query(default="NZ", min_length=2, max_length=30),
    language: str = Query(default="zh", min_length=2, max_length=30),
    media_type: str = Query(default="short_drama", pattern=r"^(short_drama|animation|film|series)$"),
    external_ai: bool = False,
):
    db = request.app.state.db
    source = db.one("SELECT * FROM novel_sources WHERE id=?", (source_id,))
    if source is None:
        raise HTTPException(404, "Novel not found")
    latest = db.one(
        """SELECT version,review_json FROM novel_rights_reviews
        WHERE source_id=? ORDER BY version DESC LIMIT 1""", (source_id,),
    )
    return evaluate_eligibility(
        source, latest, territory, language, media_type, external_ai,
    ).model_dump(mode="json")
