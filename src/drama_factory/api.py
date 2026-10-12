from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from .db import Database, timestamp, new_id
from .models import (OriginalProjectCreate, EpisodeDraft, AdaptationRequest,
                     RightsStatus, ProductionState)
from .novels.reader import extract_text, split_chapters, ReaderError, SUPPORTED_EXTENSIONS, MAX_UPLOAD_BYTES

class RightsInfo(BaseModel):
    rights_status: RightsStatus
    rights_reference: str = ""
    rights_scope: str = ""


def create_app(data_dir: str | Path = "./data") -> FastAPI:
    root = Path(data_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    db = Database(root / "factory.sqlite3")
    app = FastAPI(title="AI Short Drama Factory v0.1", version="0.1.0")
    app.state.db = db

    @app.get("/health")
    def health():
        return {"ok": True, "provider_calls_enabled": False, "novel_ai_adaptation_enabled": False}

    @app.get("/api/v1/models")
    def models():
        cfg = Path(__file__).resolve().parents[2] / "config" / "model_registry.json"
        # Works from source checkout; in installed package use built-in fallback.
        if cfg.is_file():
            return json.loads(cfg.read_text(encoding="utf-8"))
        return {"default_video": "gemini-omni-1.1-flash", "notice": "Research config only; provider is disabled"}

    @app.post("/api/v1/projects", status_code=201)
    def new_original_project(body: OriginalProjectCreate):
        project_id = new_id("proj")
        db.exec("INSERT INTO projects VALUES (?,?,?,?,?,?)", (
            project_id, body.title, body.premise, body.visual_style.value, body.default_ratio, timestamp()))
        return {"project_id": project_id, "kind": "original", "status": "created"}

    @app.get("/api/v1/projects")
    def projects():
        return db.many("SELECT * FROM projects ORDER BY created_at DESC")

    @app.post("/api/v1/projects/{project_id}/episodes", status_code=201)
    def add_episode(project_id: str, episode: EpisodeDraft):
        if not db.one("SELECT id FROM projects WHERE id=?", (project_id,)):
            raise HTTPException(404, "Unknown project")
        episode_id = new_id("ep")
        try:
            db.exec("INSERT INTO episodes VALUES (?,?,?,?,?,?)", (
                episode_id, project_id, episode.episode_number, episode.title,
                episode.model_dump_json(), timestamp()))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Episode number already exists") from exc
        return {"episode_id": episode_id, "status": "draft"}

    @app.get("/api/v1/projects/{project_id}/episodes")
    def list_episodes(project_id: str):
        return db.many("SELECT id,episode_number,title,body_json FROM episodes WHERE project_id=? ORDER BY episode_number", (project_id,))

    @app.post("/api/v1/episodes/{episode_id}/productions", status_code=201)
    def create_production(episode_id: str):
        if not db.one("SELECT id FROM episodes WHERE id=?", (episode_id,)):
            raise HTTPException(404, "Episode not found")
        run_id = new_id("run")
        now = timestamp()
        db.exec("INSERT INTO productions VALUES (?,?,?,?,?,?)", (
            run_id, episode_id, ProductionState.SCRIPT_REVIEW.value, None, now, now))
        return {"production_id": run_id, "status": ProductionState.SCRIPT_REVIEW.value}

    @app.get("/api/v1/productions")
    def productions():
        return db.many("SELECT * FROM productions ORDER BY created_at DESC")

    @app.post("/api/v1/productions/{production_id}/approve-script")
    def approve_script(production_id: str):
        return advance(production_id, ProductionState.SCRIPT_REVIEW, ProductionState.CHARACTER_REVIEW)

    @app.post("/api/v1/productions/{production_id}/approve-characters")
    def approve_characters(production_id: str):
        return advance(production_id, ProductionState.CHARACTER_REVIEW, ProductionState.VIDEO_READY)

    def advance(production_id, expected, next_status):
        row = db.one("SELECT status FROM productions WHERE id=?", (production_id,))
        if not row:
            raise HTTPException(404, "Production not found")
        if row["status"] != expected.value:
            raise HTTPException(409, f"Expected {expected.value}, found {row['status']}")
        db.exec("UPDATE productions SET status=?, updated_at=? WHERE id=? AND status=?", (
            next_status.value, timestamp(), production_id, expected.value))
        return {"production_id": production_id, "status": next_status.value}

    @app.post("/api/v1/productions/{production_id}/simulate")
    def simulate(production_id: str):
        row = db.one("SELECT status FROM productions WHERE id=?", (production_id,))
        if not row:
            raise HTTPException(404, "Production not found")
        if row["status"] != ProductionState.VIDEO_READY.value:
            raise HTTPException(409, "Both approvals are required before generation")
        fake = {"test_mode": True, "video_created": False, "paid_api_calls": 0,
                "note": "State machine only; no playable MP4 is generated"}
        db.exec("UPDATE productions SET status=?, result_json=?, updated_at=? WHERE id=?", (
            ProductionState.MOCK_FINISHED.value, db.to_json(fake), timestamp(), production_id))
        return {"production_id": production_id, "status": ProductionState.MOCK_FINISHED.value, **fake}

    @app.post("/api/v1/novels/upload", status_code=201)
    async def upload_novel(
        file: UploadFile = File(...), title: str = Form(...),
        rights_status: RightsStatus = Form(RightsStatus.PENDING),
        rights_reference: str = Form(""),
        rights_scope: str = Form(""),
    ):
        ext = Path(file.filename or "").suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(415, "Supported types: TXT, MD, DOCX, PDF, EPUB")
        if len(title) > 200 or not title.strip():
            raise HTTPException(422, "A book title (1..200 characters) is required")
        raw = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Maximum 20 MiB per file")
        try:
            extracted = extract_text(raw, ext)
        except ReaderError as exc:
            raise HTTPException(422, str(exc)) from exc
        if rights_status == RightsStatus.LICENSED and not rights_reference.strip():
            raise HTTPException(422, "Licensed works require a rights reference")
        book_id = new_id("book")
        digest = hashlib.sha256(raw).hexdigest()
        path = root / "novels" / f"{book_id}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        extracted_path = root / "novels" / f"{book_id}.txt"
        extracted_path.write_text(extracted, encoding="utf-8")
        chapters = split_chapters(extracted)
        with db.connection() as conn:
            conn.execute("INSERT INTO novel_sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                book_id, title.strip(), Path(file.filename or "book").name, ext, digest,
                rights_status.value, rights_reference.strip(), rights_scope.strip(),
                str(path), "parsed", None, len(chapters), timestamp()))
            for ch in chapters:
                conn.execute("INSERT INTO novel_chapters VALUES (?,?,?,?,?,?,?)", (
                    new_id("chapter"), book_id, ch["ordinal"], ch["title"],
                    ch["start_offset"], ch["end_offset"], ch["excerpt"]))
        return {"source_id": book_id, "parse_status": "parsed", "chapter_count": len(chapters),
                "rights_status": rights_status.value, "source_sha256": digest,
                "ai_adaptation_started": False}

    @app.get("/api/v1/novels")
    def novels():
        return db.many("SELECT id,title,format,chapter_count,rights_status,parse_status,created_at FROM novel_sources ORDER BY created_at DESC")

    @app.get("/api/v1/novels/{source_id}")
    def novel_detail(source_id: str):
        novel = db.one("SELECT * FROM novel_sources WHERE id=?", (source_id,))
        if novel is None:
            raise HTTPException(404, "Novel not found")
        novel.pop("source_path", None)
        return novel

    @app.get("/api/v1/novels/{source_id}/chapters")
    def chapters(source_id: str):
        if not db.one("SELECT id FROM novel_sources WHERE id=?", (source_id,)):
            raise HTTPException(404, "Novel not found")
        return db.many("SELECT id,ordinal,title,start_offset,end_offset,excerpt FROM novel_chapters WHERE source_id=? ORDER BY ordinal", (source_id,))

    @app.post("/api/v1/novels/{source_id}/adaptation-jobs", status_code=202)
    def request_adaptation(source_id: str, body: AdaptationRequest):
        source = db.one("SELECT * FROM novel_sources WHERE id=?", (source_id,))
        if not source:
            raise HTTPException(404, "Novel not found")
        if source["rights_status"] == RightsStatus.PENDING.value:
            raise HTTPException(403, "Rights status is pending; confirm ownership or license before adaptation")
        if "screen_adaptation" not in source["rights_scope"].split(","):
            raise HTTPException(403, "Rights scope must explicitly include screen_adaptation")
        # Contract reservation: no model execution, no automatic episode split yet.
        job_id = new_id("adapt")
        db.exec("INSERT INTO adaptation_jobs VALUES (?,?,?,?,?)", (
            job_id, source_id, "awaiting_adaptation_engine", body.model_dump_json(), timestamp()))
        return {"adaptation_job_id": job_id, "status": "awaiting_adaptation_engine",
                "episodes_generated": 0,
                "notice": "Import and entitlement gate are active; script adaptation engine is a future module"}

    return app

app = create_app()

def main():
    import uvicorn
    uvicorn.run("drama_factory.api:app", host="127.0.0.1", port=8000, reload=False)
