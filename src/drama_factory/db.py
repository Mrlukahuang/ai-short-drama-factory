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
CREATE TABLE IF NOT EXISTS asset_references (
 id TEXT PRIMARY KEY, series_id TEXT NOT NULL, asset_id TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version>0), media_kind TEXT NOT NULL,
 storage_key TEXT NOT NULL, sha256 TEXT NOT NULL, provenance_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending_review','approved','rejected')),
 created_at TEXT NOT NULL, approved_at TEXT, approved_by TEXT,
 FOREIGN KEY(series_id) REFERENCES projects(id),
 FOREIGN KEY(asset_id) REFERENCES series_assets(id), UNIQUE(asset_id,version)
);
CREATE INDEX IF NOT EXISTS idx_asset_references_asset ON asset_references(asset_id,version);
CREATE TABLE IF NOT EXISTS story_bibles (
 id TEXT PRIMARY KEY, series_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
 body_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(series_id) REFERENCES projects(id), UNIQUE(series_id,version)
);
CREATE TABLE IF NOT EXISTS script_drafts (
 id TEXT PRIMARY KEY, series_id TEXT NOT NULL, story_bible_id TEXT NOT NULL,
 prompt_version TEXT NOT NULL, request_json TEXT NOT NULL, result_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('mock_only','review_pending','approved','rejected')),
 created_at TEXT NOT NULL,
 FOREIGN KEY(series_id) REFERENCES projects(id),
 FOREIGN KEY(story_bible_id) REFERENCES story_bibles(id)
);
CREATE INDEX IF NOT EXISTS idx_script_drafts_series ON script_drafts(series_id,created_at);
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
CREATE TABLE IF NOT EXISTS novel_rights_reviews (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
 review_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(source_id) REFERENCES novel_sources(id), UNIQUE(source_id,version)
);
CREATE INDEX IF NOT EXISTS idx_novel_rights_reviews
 ON novel_rights_reviews(source_id,version);
CREATE TABLE IF NOT EXISTS novel_analysis_chunks (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
 chapter_ordinal INTEGER NOT NULL, start_offset INTEGER NOT NULL,
 end_offset INTEGER NOT NULL, content_sha256 TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','running','completed','failed')),
 created_at TEXT NOT NULL,
 FOREIGN KEY(source_id) REFERENCES novel_sources(id),
 UNIQUE(source_id,chapter_ordinal,start_offset,end_offset,content_sha256)
);
CREATE INDEX IF NOT EXISTS idx_novel_chunks_source
  ON novel_analysis_chunks(source_id,chapter_ordinal,start_offset);
CREATE TABLE IF NOT EXISTS shot_jobs (
 id TEXT PRIMARY KEY,
 production_id TEXT NOT NULL REFERENCES productions(id),
 episode_id TEXT NOT NULL REFERENCES episodes(id),
 series_id TEXT NOT NULL REFERENCES projects(id),
 shot_id TEXT NOT NULL,
 provider TEXT NOT NULL, model_id TEXT NOT NULL,
 input_sha256 TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
 max_acknowledged_spend_usd TEXT NOT NULL,
 actual_vendor_charge_usd TEXT DEFAULT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','leased','submission_intent','submitted','succeeded','failed','cancelled')),
 generation_intent_recorded INTEGER NOT NULL DEFAULT 0 CHECK(generation_intent_recorded IN (0,1)),
 attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts>=0),
 max_attempts INTEGER NOT NULL DEFAULT 2 CHECK(max_attempts BETWEEN 1 AND 5),
 provider_task_id TEXT,
 lease_owner TEXT, lease_expires_at TEXT,
 result_sha256 TEXT, result_path TEXT,
 last_error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(production_id,shot_id)
);
CREATE INDEX IF NOT EXISTS idx_shot_jobs_series_status
  ON shot_jobs(series_id,status,created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_shot_jobs_provider_task
  ON shot_jobs(provider,provider_task_id) WHERE provider_task_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS google_existing_files (
 job_id TEXT PRIMARY KEY REFERENCES shot_jobs(id),
 file_id TEXT NOT NULL UNIQUE,
 recovery_active INTEGER NOT NULL DEFAULT 0 CHECK(recovery_active IN (0,1)),
 bound_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shot_job_events (
 id TEXT PRIMARY KEY,
 shot_job_id TEXT NOT NULL REFERENCES shot_jobs(id),
 action TEXT NOT NULL,
 previous_state TEXT, next_state TEXT NOT NULL,
 details_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shot_events_job
  ON shot_job_events(shot_job_id,created_at);
CREATE TRIGGER IF NOT EXISTS shot_job_events_immutable_update
 BEFORE UPDATE ON shot_job_events
 BEGIN SELECT RAISE(ABORT,'shot job events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS shot_job_events_immutable_delete
 BEFORE DELETE ON shot_job_events
 BEGIN SELECT RAISE(ABORT,'shot job events are append-only'); END;
CREATE TABLE IF NOT EXISTS budget_policies (
 id TEXT PRIMARY KEY,
 scope TEXT NOT NULL CHECK(scope IN ('column','series','provider')),
 scope_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
 daily_limit_usd TEXT NOT NULL,
 max_active_jobs INTEGER NOT NULL CHECK(max_active_jobs BETWEEN 1 AND 100),
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
 created_at TEXT NOT NULL,
 UNIQUE(scope,scope_id,revision)
);
CREATE INDEX IF NOT EXISTS idx_budget_policies_scope
 ON budget_policies(scope,scope_id,revision);
CREATE TABLE IF NOT EXISTS job_budget_reservations (
 id TEXT PRIMARY KEY,
 job_id TEXT NOT NULL UNIQUE REFERENCES shot_jobs(id),
 column_id TEXT NOT NULL REFERENCES columns(id),
 series_id TEXT NOT NULL REFERENCES projects(id),
 provider TEXT NOT NULL,day_utc TEXT NOT NULL,
 reserved_usd TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('held','released','reconciled')),
 actual_usd TEXT,evidence_reference TEXT,reviewed_by TEXT,
 policy_snapshot_json TEXT NOT NULL,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_budget_daily
 ON job_budget_reservations(day_utc,column_id,series_id,provider,status);
CREATE TABLE IF NOT EXISTS budget_reservation_events (
 id TEXT PRIMARY KEY,reservation_id TEXT NOT NULL REFERENCES job_budget_reservations(id),
 action TEXT NOT NULL,details_json TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS budget_events_immutable_update
 BEFORE UPDATE ON budget_reservation_events
 BEGIN SELECT RAISE(ABORT,'budget events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS budget_events_immutable_delete
 BEFORE DELETE ON budget_reservation_events
 BEGIN SELECT RAISE(ABORT,'budget events are append-only'); END;
CREATE TABLE IF NOT EXISTS stored_artifacts (
 id TEXT PRIMARY KEY,
 production_id TEXT NOT NULL REFERENCES productions(id),
 episode_id TEXT NOT NULL REFERENCES episodes(id),
 series_id TEXT NOT NULL REFERENCES projects(id),
 shot_job_id TEXT REFERENCES shot_jobs(id),
 kind TEXT NOT NULL CHECK(kind IN ('episode_preview','shot_video')),
 object_key TEXT NOT NULL UNIQUE,
 sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes>=1000),
 media_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 CHECK((kind='episode_preview' AND shot_job_id IS NULL)
    OR (kind='shot_video' AND shot_job_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_stored_artifacts_production
 ON stored_artifacts(production_id,kind,created_at);
CREATE TABLE IF NOT EXISTS cloud_artifacts (
 id TEXT PRIMARY KEY,
 artifact_id TEXT NOT NULL REFERENCES stored_artifacts(id),
 provider TEXT NOT NULL CHECK(provider IN ('r2','s3')),
 bucket TEXT NOT NULL,
 target_id TEXT NOT NULL,
 object_key TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes >= 1000),
 created_at TEXT NOT NULL,
 UNIQUE(artifact_id,target_id)
);
CREATE INDEX IF NOT EXISTS idx_cloud_artifacts_local
 ON cloud_artifacts(artifact_id,provider);
CREATE TABLE IF NOT EXISTS cloud_artifact_events (
 id TEXT PRIMARY KEY,
 cloud_copy_id TEXT NOT NULL REFERENCES cloud_artifacts(id),
 action TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS cloud_events_immutable_update
 BEFORE UPDATE ON cloud_artifact_events
 BEGIN SELECT RAISE(ABORT,'cloud artifact events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS cloud_events_immutable_delete
 BEFORE DELETE ON cloud_artifact_events
 BEGIN SELECT RAISE(ABORT,'cloud artifact events are append-only'); END;
CREATE TABLE IF NOT EXISTS drive_artifacts (
 id TEXT PRIMARY KEY,
 artifact_id TEXT NOT NULL REFERENCES stored_artifacts(id),
 parent_folder_id TEXT NOT NULL,
 drive_file_id TEXT NOT NULL,
 remote_folder_id TEXT NOT NULL,
 object_key TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 size_bytes INTEGER NOT NULL CHECK(size_bytes>=1000),
 created_at TEXT NOT NULL,
 UNIQUE(artifact_id,parent_folder_id),
 UNIQUE(parent_folder_id,drive_file_id)
);
CREATE INDEX IF NOT EXISTS idx_drive_artifacts_source
 ON drive_artifacts(artifact_id,created_at);
CREATE TABLE IF NOT EXISTS drive_artifact_events (
 id TEXT PRIMARY KEY,
 drive_copy_id TEXT NOT NULL REFERENCES drive_artifacts(id),
 action TEXT NOT NULL,
 sha256 TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS drive_events_no_update
 BEFORE UPDATE ON drive_artifact_events
 BEGIN SELECT RAISE(ABORT,'drive events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS drive_events_no_delete
 BEFORE DELETE ON drive_artifact_events
 BEGIN SELECT RAISE(ABORT,'drive events are append-only'); END;
-- PR-10g: isolated LOCAL SQLite per-cue TTS intent (never provider-submitting).
-- Schema is additive; does not migrate or switch production/Turso.
CREATE TABLE IF NOT EXISTS tts_tasks (
 id TEXT PRIMARY KEY,
 production_id TEXT NOT NULL REFERENCES productions(id),
 series_id TEXT NOT NULL REFERENCES projects(id),
 shot_id TEXT NOT NULL,
 cue_index INTEGER NOT NULL CHECK(cue_index>=0),
 request_sha256 TEXT NOT NULL UNIQUE,
 model_id TEXT NOT NULL, voice_name TEXT NOT NULL,
 provider TEXT NOT NULL DEFAULT 'google' CHECK(provider='google'),
 max_acknowledged_spend_usd TEXT NOT NULL,
 approved_slot_seconds INTEGER NOT NULL CHECK(approved_slot_seconds BETWEEN 1 AND 30),
 status TEXT NOT NULL CHECK(status IN
   ('prepared','submission_intent','acknowledged','quarantined','verified')),
 interaction_id TEXT,
 output_sha256 TEXT,
 output_duration_seconds TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(production_id,shot_id,cue_index)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tts_interaction
 ON tts_tasks(provider,interaction_id) WHERE interaction_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tts_tasks_series_status ON tts_tasks(series_id,status);
CREATE TABLE IF NOT EXISTS tts_budget_reservations (
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL UNIQUE REFERENCES tts_tasks(id),
 column_id TEXT NOT NULL REFERENCES columns(id),
 series_id TEXT NOT NULL REFERENCES projects(id),
 provider TEXT NOT NULL DEFAULT 'google',
 day_utc TEXT NOT NULL,
 reserved_usd TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('held','released','reconciled')),
 actual_usd TEXT, evidence_reference TEXT, reviewed_by TEXT,
 policy_snapshot_json TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tts_reservations_day
 ON tts_budget_reservations(day_utc,column_id,series_id,provider,status);
CREATE TABLE IF NOT EXISTS tts_task_events (
 id TEXT PRIMARY KEY,
 task_id TEXT NOT NULL REFERENCES tts_tasks(id),
 action TEXT NOT NULL,
 previous_state TEXT,
 next_state TEXT NOT NULL,
 details_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tts_task_events ON tts_task_events(task_id,created_at);
CREATE TRIGGER IF NOT EXISTS tts_task_events_no_update
 BEFORE UPDATE ON tts_task_events
 BEGIN SELECT RAISE(ABORT,'tts task events are append-only'); END;
CREATE TRIGGER IF NOT EXISTS tts_task_events_no_delete
 BEFORE DELETE ON tts_task_events
 BEGIN SELECT RAISE(ABORT,'tts task events are append-only'); END;
-- PR-10o: optional, immutable OFFLINE assertion of original Google context.
-- This is not an authenticated provider proof and enables NO live GET.
CREATE TABLE IF NOT EXISTS tts_google_origin_scopes (
 task_id TEXT PRIMARY KEY REFERENCES tts_tasks(id),
 project_ref_sha256 TEXT NOT NULL CHECK(length(project_ref_sha256)=64),
 principal_ref_sha256 TEXT NOT NULL CHECK(length(principal_ref_sha256)=64),
 source TEXT NOT NULL DEFAULT 'offline_unverified'
   CHECK(source='offline_unverified'),
 created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS tts_google_origin_no_update
 BEFORE UPDATE ON tts_google_origin_scopes
 BEGIN SELECT RAISE(ABORT,'tts google origin scopes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS tts_google_origin_no_delete
 BEFORE DELETE ON tts_google_origin_scopes
 BEGIN SELECT RAISE(ABORT,'tts google origin scopes are immutable'); END;
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