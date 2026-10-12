"""Isolated draft planning routes; no paid provider calls and no implicit approvals."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from ..db import new_id, timestamp
from .text import FakeTextProvider, ScriptContext, ScriptOutline, ScriptPlanRequest

router = APIRouter(prefix="/api/v1/series/{series_id}", tags=["script-planning"])


@router.post("/script-drafts", status_code=201)
def fake_script_draft(series_id: str, body: ScriptPlanRequest, request: Request):
    db = request.app.state.db
    series = db.one("SELECT id FROM projects WHERE id=?", (series_id,))
    if series is None:
        raise HTTPException(404, "Unknown series")
    bible = db.one(
        "SELECT id,body_json FROM story_bibles WHERE id=? AND series_id=?",
        (body.story_bible_id, series_id),
    )
    if bible is None:
        raise HTTPException(422, "Story Bible does not belong to this series")
    for actor_id in body.actor_asset_ids:
        row = db.one(
            "SELECT id FROM series_assets WHERE id=? AND series_id=? AND kind='actor'",
            (actor_id, series_id),
        )
        if row is None:
            raise HTTPException(422, f"Actor reference does not belong to this series: {actor_id}")
    if body.scene_asset_id:
        row = db.one(
            "SELECT id FROM series_assets WHERE id=? AND series_id=? AND kind='scene'",
            (body.scene_asset_id, series_id),
        )
        if row is None:
            raise HTTPException(422, "Scene reference does not belong to this series")
    context = ScriptContext(
        series_id=series_id,
        story_bible_id=bible["id"],
        story_bible_json=json.loads(bible["body_json"]),
        allowed_actor_ids=body.actor_asset_ids,
        allowed_scene_id=body.scene_asset_id,
    )
    draft = FakeTextProvider().generate(body, context)
    draft_id = new_id("draft")
    db.exec(
        """INSERT INTO script_drafts
        (id,series_id,story_bible_id,prompt_version,request_json,result_json,status,created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (
            draft_id, series_id, bible["id"], body.prompt_version,
            body.model_dump_json(), draft.model_dump_json(), "mock_only", timestamp(),
        ),
    )
    return {
        "draft_id": draft_id, "series_id": series_id, "status": "mock_only",
        "paid_api_calls": 0, "episodes_created": 0, "draft": draft.model_dump(mode="json"),
    }


@router.get("/script-drafts")
def list_script_drafts(series_id: str, request: Request):
    db = request.app.state.db
    if db.one("SELECT id FROM projects WHERE id=?", (series_id,)) is None:
        raise HTTPException(404, "Unknown series")
    rows = db.many(
        """SELECT id,series_id,story_bible_id,prompt_version,status,created_at
        FROM script_drafts WHERE series_id=? ORDER BY created_at DESC,id DESC""",
        (series_id,),
    )
    return rows


@router.get("/script-drafts/{draft_id}")
def get_script_draft(series_id: str, draft_id: str, request: Request):
    db = request.app.state.db
    row = db.one(
        """SELECT result_json,status FROM script_drafts
        WHERE id=? AND series_id=?""", (draft_id, series_id),
    )
    if row is None:
        raise HTTPException(404, "Draft not found in this series")
    draft = ScriptOutline.model_validate_json(row["result_json"])
    return {"status": row["status"], "draft": draft.model_dump(mode="json")}
