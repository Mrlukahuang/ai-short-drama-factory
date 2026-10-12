"""Verified local artifact catalog for reviewed episode previews and shot video.

There are no external uploads, public URLs, or model generation calls.
Object keys are generated from database-owned scope IDs and verified SHA256,
never from a user-provided filename. The caller must supply a persistent root
outside the disposable rendering workspace.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from drama_factory.db import Database, new_id, timestamp
from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.offline_render import inspect_mp4
from drama_factory.pipeline.media_ingest import inspect_source


class ArtifactStoreError(ValueError):
    pass


_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{3,100}")
_SHA = re.compile(r"[0-9a-f]{64}")


def _id(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ArtifactStoreError("Invalid artifact scope identifier")
    return value


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            length += len(chunk)
            if length > 200 * 1024 * 1024:
                raise ArtifactStoreError("Media artifact exceeds 200 MB safety bound")
            digest.update(chunk)
    if length < 1000:
        raise ArtifactStoreError("Media artifact is empty or truncated")
    return digest.hexdigest(), length


def _canonical_input(path: Path, work_root: Path) -> Path:
    work = Path(work_root).resolve(strict=True)
    source = Path(path)
    # Reject a symlink in any component below the trusted work root.
    try:
        relative = source.absolute().relative_to(work)
    except ValueError as exc:
        raise ArtifactStoreError("Source media outside production work root") from exc
    at = work
    for component in relative.parts:
        at = at / component
        if at.is_symlink():
            raise ArtifactStoreError("Source media cannot be a symlink")
    if not source.is_file() or source.resolve(strict=True) != (work / relative):
        raise ArtifactStoreError("Invalid local media source")
    return source.resolve()


def _verified_source(
    source: Path, work_root: Path, *, duration: int, expect_sha: str,
    must_have_subtitles: bool,
) -> tuple[str, int, dict]:
    path = _canonical_input(source, work_root)
    if path.suffix.lower() != ".mp4":
        raise ArtifactStoreError("Only MP4 artifacts are supported")
    meta = inspect_mp4(path, duration)
    if must_have_subtitles and meta["subtitle_codec"] != "mov_text":
        raise ArtifactStoreError("Final episode preview must include subtitles")
    digest, byte_count = _hash_file(path)
    if digest != expect_sha:
        raise ArtifactStoreError("Source SHA256 differs from reviewed job or preview manifest")
    return digest, byte_count, meta


def _publish_bytes(source: Path, store_root: Path, key: str,
                   expect_sha: str, size: int) -> Path:
    root = Path(store_root).resolve()
    dest = root.joinpath(*key.split("/"))
    if dest.resolve(strict=False) != dest:
        raise ArtifactStoreError("Storage path contains symlink or escape")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink() or dest.parent.resolve() != dest.parent:
        raise ArtifactStoreError("Storage destination contains symlink")
    if dest.exists():
        actual_sha, actual_size = _hash_file(dest)
        if actual_sha != expect_sha or actual_size != size:
            raise ArtifactStoreError("Immutable object key exists with different bytes")
        return dest
    temp = dest.with_name("." + uuid4().hex + ".pending")
    try:
        # Exclusive staging copy plus SHA of bytes actually written.
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        digest = hashlib.sha256()
        written = 0
        with os.fdopen(fd, "wb") as target, source.open("rb") as original:
            for chunk in iter(lambda: original.read(1024 * 1024), b""):
                written += len(chunk)
                if written > 200 * 1024 * 1024:
                    raise ArtifactStoreError("Source exceeded maximum during copy")
                digest.update(chunk)
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if digest.hexdigest() != expect_sha or written != size:
            raise ArtifactStoreError("Source changed while copying to storage")
        try:
            os.link(temp, dest)
        except FileExistsError:
            # Parallel publisher completed first; verify immutable content.
            if dest.is_symlink() or _hash_file(dest) != (expect_sha, size):
                raise ArtifactStoreError("Concurrent object differs from expected SHA")
        return dest
    finally:
        temp.unlink(missing_ok=True)


def _catalog(db: Database, *, kind: str, row: dict, job_id: str | None,
             sha256: str, size: int, meta: dict, object_key: str) -> dict:
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        production = conn.execute(
            """SELECT e.id AS episode_id,e.project_id FROM productions p
            JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
            (row["production_id"],),
        ).fetchone()
        if (
            production is None or production["project_id"] != row["series_id"]
            or production["episode_id"] != row["episode_id"]
        ):
            raise ArtifactStoreError("Series or production changed during artifact publication")
        if kind == "shot_video":
            job = conn.execute(
                """SELECT status,result_sha256,result_path FROM shot_jobs WHERE id=?
                AND production_id=? AND series_id=?""",
                (job_id, row["production_id"], row["series_id"]),
            ).fetchone()
            if job is None or job["status"] != "succeeded" or job["result_sha256"] != sha256:
                raise ArtifactStoreError("Shot result no longer approved in job ledger")
        else:
            record = conn.execute(
                "SELECT status,result_json FROM productions WHERE id=?",
                (row["production_id"],),
            ).fetchone()
            if record is None or record["status"] != "offline_preview_finished":
                raise ArtifactStoreError("Episode preview is not completed")
            manifest = json.loads(record["result_json"])
            if manifest.get("mp4_sha256") != sha256:
                raise ArtifactStoreError("Episode preview provenance changed")
        existing = conn.execute(
            "SELECT * FROM stored_artifacts WHERE object_key=?", (object_key,),
        ).fetchone()
        if existing:
            if existing["sha256"] != sha256 or existing["size_bytes"] != size:
                raise ArtifactStoreError("Object catalog conflict")
            return dict(existing)
        conn.execute(
            """INSERT INTO stored_artifacts
               (id,production_id,episode_id,series_id,shot_job_id,kind,
               object_key,sha256,size_bytes,media_json,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (new_id("artifact"), row["production_id"], row["episode_id"],
             row["series_id"], job_id, kind, object_key, sha256, size,
             json.dumps(meta, sort_keys=True), timestamp()),
        )
        return dict(conn.execute(
            "SELECT * FROM stored_artifacts WHERE object_key=?", (object_key,),
        ).fetchone())


def publish_episode_preview(
    db: Database, production_id: str, work_root: Path, store_root: Path,
) -> dict:
    """Publish the already-reviewed FFmpeg MP4, not a claimed AI movie."""
    p = db.one(
        """SELECT p.status,p.result_json,e.id AS episode_id,e.project_id
        FROM productions p JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
        (production_id,),
    )
    if p is None or p["status"] != "offline_preview_finished" or not p["result_json"]:
        raise ArtifactStoreError("Reviewed offline preview not yet finished")
    manifest = json.loads(p["result_json"])
    series_id = _id(p["project_id"])
    production_id = _id(production_id)
    episode = db.one("SELECT body_json FROM episodes WHERE id=?", (p["episode_id"],))
    expected_duration = EpisodeDraft.model_validate_json(episode["body_json"]).target_duration_seconds
    expected = Path(work_root).resolve() / series_id / production_id / "preview.mp4"
    if Path(manifest.get("mp4_path", "")).resolve() != expected:
        raise ArtifactStoreError("Preview manifest path does not match production")
    if manifest.get("series_id") != series_id or manifest.get("production_id") != production_id:
        raise ArtifactStoreError("Preview manifest scope is inconsistent")
    sha = manifest.get("mp4_sha256")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise ArtifactStoreError("Preview manifest SHA256 missing")
    digest, size, meta = _verified_source(
        expected, work_root, duration=expected_duration,
        expect_sha=sha, must_have_subtitles=True,
    )
    key = f"{series_id}/{production_id}/episode_preview/{digest}.mp4"
    _publish_bytes(expected, store_root, key, digest, size)
    return _catalog(
        db, kind="episode_preview",
        row={"production_id":production_id,"series_id":series_id,"episode_id":p["episode_id"]},
        job_id=None, sha256=digest, size=size, meta=meta, object_key=key,
    )


def publish_shot_video(
    db: Database, shot_job_id: str, work_root: Path, store_root: Path,
) -> dict:
    """Verify a succeeded video job, then record an immutable scoped object."""
    job = db.one("SELECT * FROM shot_jobs WHERE id=?", (shot_job_id,))
    if job is None or job["status"] != "succeeded":
        raise ArtifactStoreError("Only succeeded shot jobs can be published")
    series = _id(job["series_id"])
    production = _id(job["production_id"])
    shot_id = _id(shot_job_id)
    ep = db.one("SELECT body_json,project_id FROM episodes WHERE id=?", (job["episode_id"],))
    if ep is None or ep["project_id"] != series:
        raise ArtifactStoreError("Shot episode scope mismatch")
    draft = EpisodeDraft.model_validate_json(ep["body_json"])
    shot = next((s for s in draft.shots if s.shot_id == job["shot_id"]), None)
    if shot is None:
        raise ArtifactStoreError("Job shot is missing from episode")
    expected_sha = job["result_sha256"]
    if not isinstance(expected_sha, str) or not _SHA.fullmatch(expected_sha):
        raise ArtifactStoreError("Verified shot SHA256 missing")
    path = Path(job["result_path"])
    trusted = Path(work_root).resolve() / series / production
    resolved = path.resolve()
    try:
        resolved.relative_to(trusted)
    except ValueError as exc:
        raise ArtifactStoreError("Shot video is outside its production") from exc
    digest, size, meta = _verified_source(
        path, work_root, duration=shot.duration_seconds,
        expect_sha=expected_sha, must_have_subtitles=False,
    )
    key = f"{series}/{production}/shot_video/{shot_id}/{digest}.mp4"
    _publish_bytes(path, store_root, key, digest, size)
    return _catalog(
        db, kind="shot_video",
        row={"production_id":production,"series_id":series,"episode_id":job["episode_id"]},
        job_id=shot_job_id, sha256=digest, size=size, meta=meta, object_key=key,
    )


def verify_stored_artifact(
    db: Database, artifact_id: str, store_root: Path,
) -> dict:
    """Verify bytes from durable storage; no fallback to disposable work files."""
    row = db.one("SELECT * FROM stored_artifacts WHERE id=?", (artifact_id,))
    if row is None:
        raise ArtifactStoreError("Stored artifact does not exist")
    if row["kind"] == "episode_preview":
        key = f"{_id(row['series_id'])}/{_id(row['production_id'])}/episode_preview/{row['sha256']}.mp4"
    elif row["kind"] == "shot_video":
        key = f"{_id(row['series_id'])}/{_id(row['production_id'])}/shot_video/{_id(row['shot_job_id'])}/{row['sha256']}.mp4"
    else:
        raise ArtifactStoreError("Unknown artifact kind")
    if key != row["object_key"] or not _SHA.fullmatch(row["sha256"]):
        raise ArtifactStoreError("Stored artifact object key is invalid")
    root = Path(store_root).resolve()
    dest = root.joinpath(*key.split("/"))
    if dest.is_symlink() or dest.resolve() != dest:
        raise ArtifactStoreError("Storage object is linked or redirected")
    digest, size = _hash_file(dest)
    if digest != row["sha256"] or size != row["size_bytes"]:
        raise ArtifactStoreError("Persisted artifact failed integrity check")
    media = inspect_mp4(dest)
    if row["kind"] == "episode_preview" and media["subtitle_codec"] != "mov_text":
        raise ArtifactStoreError("Stored episode lost subtitles")
    return {
        "artifact_id": row["id"], "series_id": row["series_id"],
        "production_id": row["production_id"], "kind": row["kind"],
        "object_key": key, "sha256": digest, "size_bytes": size,
        "path": str(dest), "media": media, "verified": True,
    }
