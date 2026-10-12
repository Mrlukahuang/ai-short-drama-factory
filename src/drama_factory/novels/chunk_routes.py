"""Offline chapter chunk preparation. Preparation is not AI analysis."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..db import timestamp
from .chunks import SourceIndexError, plan_chunks, read_extracted_text, verify_chunks

router = APIRouter(prefix="/api/v1/novels/{source_id}/analysis", tags=["novel-analysis"])


@router.post("/prepare", status_code=202)
def prepare_analysis_chunks(source_id: str, request: Request):
    db = request.app.state.db
    source = db.one("SELECT * FROM novel_sources WHERE id=?", (source_id,))
    if source is None:
        raise HTTPException(404, "Novel source not found")
    # Never treat this as a legal clearance. This is a conservative dev-mode gate.
    if (
        source["rights_status"] == "pending"
        or "screen_adaptation" not in source["rights_scope"].split(",")
    ):
        raise HTTPException(403, "Screen adaptation rights must be recorded before planning")
    chapters = db.many(
        """SELECT ordinal,start_offset,end_offset FROM novel_chapters
        WHERE source_id=? ORDER BY ordinal""", (source_id,),
    )
    try:
        extracted = read_extracted_text(db.path.parent, source_id)
        parts = plan_chunks(source_id, extracted, chapters)
        verify_chunks(extracted, parts)
    except SourceIndexError as exc:
        raise HTTPException(409, str(exc)) from exc
    # Idempotent: existing chunks and future approved results are never overwritten.
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for part in parts:
            conn.execute(
                """INSERT OR IGNORE INTO novel_analysis_chunks
                (id,source_id,chapter_ordinal,start_offset,end_offset,
                 content_sha256,status,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (part["id"], source_id, part["chapter_ordinal"],
                 part["start_offset"], part["end_offset"],
                 part["content_sha256"], "pending", timestamp()),
            )
    return {
        "source_id": source_id, "chunk_count": len(parts),
        "status": "prepared_only", "extraction_started": False,
        "model_calls": 0, "source_text_sent_to_provider": False,
    }


@router.get("/chunks")
def list_analysis_chunks(source_id: str, request: Request):
    db = request.app.state.db
    if db.one("SELECT id FROM novel_sources WHERE id=?", (source_id,)) is None:
        raise HTTPException(404, "Novel source not found")
    # Return metadata only; never include raw copyrighted text.
    return db.many(
        """SELECT id,chapter_ordinal,start_offset,end_offset,content_sha256,status,
        created_at FROM novel_analysis_chunks
        WHERE source_id=? ORDER BY chapter_ordinal,start_offset""", (source_id,),
    )
