from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

DEFAULT_COLUMN_ID = "col_default"

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS columns (
 id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 description TEXT NOT NULL, default_visual_style TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, premise TEXT NOT NULL,
 visual_style TEXT NOT NULL, ratio TEXT NOT NULL, created_at TEXT NOT NULL,
 column_id TEXT REFERENCES columns(id)
);
CREATE INDEX IF NOT EXISTS idx_columns_slug ON columns(slug);
CREATE TABLE IF NOT EXISTS episodes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, episode_number INTEGER NOT NULL,
 title TEXT NOT NULL, body_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(project_id) REFERENCES projects(id), UNIQUE(project_id, episode_number)
);
CREATE TABLE IF NOT EXISTS productions (
 id TEXT PRIMARY KEY, episode_id TEXT NOT NULL, status TEXT NOT NULL,
 result_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(episode_id) REFERENCES episodes(id)
);
CREATE TABLE IF NOT EXISTS series_assets (
 id TEXT PRIMARY KEY, series_id TEXT NOT NULL, kind TEXT NOT NULL
   CHECK(kind IN ('actor','scene','voice','prop')),
 asset_key TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
 specification_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(series_id) REFERENCES projects(id),
 UNIQUE(series_id, kind, asset_key, version)
);
CREATE INDEX IF NOT EXISTS idx_series_assets_scope ON series_assets(series_id,kind,asset_key);
CREATE TABLE IF NOT EXISTS story_bibles (
 id TEXT PRIMARY KEY, series_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
 body_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(series_id) REFERENCES projects(id), UNIQUE(series_id,version)
);
CREATE TABLE IF NOT EXISTS novel_sources (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, original_filename TEXT NOT NULL,
 format TEXT NOT NULL, sha256 TEXT NOT NULL, rights_status TEXT NOT NULL,
 rights_reference TEXT NOT NULL, rights_scope TEXT NOT NULL,
 source_path TEXT NOT NULL, parse_status TEXT NOT NULL, parse_error TEXT,
 chapter_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS novel_chapters (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 title TEXT NOT NULL, start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 excerpt TEXT NOT NULL, FOREIGN KEY(source_id) REFERENCES novel_sources(id),
 UNIQUE(source_id, ordinal)
);
CREATE TABLE IF NOT EXISTS adaptation_jobs (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL, status TEXT NOT NULL,
 request_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(source_id) REFERENCES novel_sources(id)
);
"""

def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:14]}"

class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            # Existing v0.1 databases lacked column_id; add and backfill in place.
            db.executescript(SCHEMA)
            fields = {row["name"] for row in db.execute("PRAGMA table_info(projects)")}
            if "column_id" not in fields:
                db.execute("ALTER TABLE projects ADD COLUMN column_id TEXT REFERENCES columns(id)")
            db.execute("INSERT OR IGNORE INTO columns VALUES (?,?,?,?,?,?)", (
                DEFAULT_COLUMN_ID, "default", "默认栏目", "历史项目及兼容旧 API 的默认栏目",
                "live_action", timestamp()))
            db.execute("UPDATE projects SET column_id=? WHERE column_id IS NULL", (DEFAULT_COLUMN_ID,))
            db.execute("CREATE INDEX IF NOT EXISTS idx_projects_column ON projects(column_id)")
            # Protect all future writes, including direct SQL consumers of a migrated database.
            db.execute("""CREATE TRIGGER IF NOT EXISTS projects_column_required
               BEFORE INSERT ON projects WHEN NEW.column_id IS NULL
               BEGIN SELECT RAISE(ABORT,'column_id is required'); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS projects_column_update_required
               BEFORE UPDATE OF column_id ON projects WHEN NEW.column_id IS NULL
               BEGIN SELECT RAISE(ABORT,'column_id is required'); END""")

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        with self.connection() as db:
            row = db.execute(sql, params).fetchone()
            return dict(row) if row else None

    def many(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.connection() as db:
            return [dict(x) for x in db.execute(sql, params).fetchall()]

    def exec(self, sql: str, params: tuple = ()) -> None:
        with self.connection() as db:
            db.execute(sql, params)

    @staticmethod
    def to_json(data) -> str:
        return json.dumps(data, ensure_ascii=False)