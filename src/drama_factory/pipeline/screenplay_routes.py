"""Review and commit structured screenplays; no external model calls."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Request

from ..db import new_id, timestamp
from .screenplay import (
    ReviewedScreenplay, Screenplay, ScreenplayReferenceError, check_screenplay_scope,
)

router = APIRouter(prefix="/api/v1/series/{series_id}/screenplays", tags=["screenplays"])


def validate(db, series_id: str, screenplay: Screenplay) -> None:
    if screenplay.series_id != series_id:
        raise HTTPException(422, "Screenplay series_id must match route")
    try:
        check_screenplay_scope(db, screenplay)
    except ScreenplayReferenceError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/validate")
def validate_screenplay(series_id: str, body: Screenplay, request: Request):
    validate(request.app.state.db, series_id, body)
    episode = body.to_episode_draft()
    return {
        "valid": True,
        "review_required": True,
        "paid_api_calls": 0,
        "episode_draft": episode.model_dump(mode="json"),
        "shot_count": len(body.shots),
    }


@router.post("/commit", status_code=201)
def commit_reviewed_screenplay(series_id: str, body: ReviewedScreenplay, request: Request):
    db = request.app.state.db
    screenplay = body.screenplay
    validate(db, series_id, screenplay)
    episode = screenplay.to_episode_draft()
    episode_id = new_id("ep")
    try:
        with db.connection() as conn:
            # Scope check and insertion share a transaction, so concurrent operations cannot
            # produce duplicate numbered episodes. Assets/Bibles are immutable once created.
            conn.execute(
                """INSERT INTO episodes
                   (id,project_id,episode_number,title,body_json,created_at)
                   VALUES (?,?,?,?,?,?)""",
                (episode_id, series_id, episode.episode_number, episode.title,
                 episode.model_dump_json(), timestamp()),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Episode number already exists") from exc
    return {
        "episode_id": episode_id,
        "series_id": series_id,
        "status": "draft",
        "production_created": False,
        "paid_api_calls": 0,
    }
