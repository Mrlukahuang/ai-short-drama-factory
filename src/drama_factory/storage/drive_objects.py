"""Explicit private Google Drive MP4 backup, with no public sharing or AI calls.

Only publish reviewed MP4s already stored in the immutable local artifact
catalog. Drive creates new files (never updates/deletes/shares) and all claimed
uploads are downloaded and hashed before being marked successful.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
from pathlib import Path
from uuid import uuid4

from drama_factory.db import Database, new_id, timestamp
from drama_factory.pipeline.offline_render import inspect_mp4
from drama_factory.storage.artifacts import (
    ArtifactStoreError, _id, _hash_file, _publish_bytes, verify_stored_artifact,
)

DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
_FILE_ID = re.compile(r"[a-zA-Z0-9_-]{8,160}")
_DIGEST = re.compile(r"[0-9a-f]{64}")
_MAX_SIZE = 200 * 1024 * 1024


class DriveArtifactError(ArtifactStoreError):
    pass


def _gated(flag: str, approved: bool):
    if approved is not True or os.getenv(flag) != "YES":
        raise DriveArtifactError("Google Drive operations disabled by default")


def _file_id(raw: str) -> str:
    if not isinstance(raw, str) or not _FILE_ID.fullmatch(raw):
        raise DriveArtifactError("Invalid Google Drive file/folder ID")
    return raw


def _key(local: dict) -> str:
    series = _id(local["series_id"])
    production = _id(local["production_id"])
    sha = local["sha256"]
    if not _DIGEST.fullmatch(sha):
        raise DriveArtifactError("Invalid catalog SHA256")
    if local["kind"] == "shot_video":
        suffix = f"shot_video/{_id(local['shot_job_id'])}/{sha}.mp4"
    elif local["kind"] == "episode_preview":
        suffix = f"episode_preview/{sha}.mp4"
    else:
        raise DriveArtifactError("Unsupported artifact kind")
    key = f"{series}/{production}/{suffix}"
    if key != local["object_key"]:
        raise DriveArtifactError("Catalog identity or object key mismatch")
    return key


class GoogleDriveApiClient:
    """Construct only with an explicit OAuth 2.0 user authorization, never SA."""

    def __init__(self, authorized_user_info: dict):
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise DriveArtifactError("Install optional drive-storage dependencies") from exc
        creds = Credentials.from_authorized_user_info(
            authorized_user_info, scopes=[DRIVE_FILE_SCOPE]
        )
        if not creds.refresh_token:
            raise DriveArtifactError("Offline user OAuth refresh token required")
        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_named(self, parent_id: str, name: str) -> list[dict]:
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        q = f"'{_file_id(parent_id)}' in parents and name = '{escaped}' and trashed = false"
        results = self.service.files().list(
            q=q, spaces="drive", page_size=100,
            fields="nextPageToken,files(id,name,mimeType,parents,appProperties,size,md5Checksum)",
        )
        items = []
        while results:
            batch = results.execute()
            items.extend(batch.get("files", []))
            results = self.service.files().list(
                q=q, spaces="drive", page_size=100,
                page_token=batch["nextPageToken"],
                fields="nextPageToken,files(id,name,mimeType,parents,appProperties,size,md5Checksum)",
            ) if batch.get("nextPageToken") else None
        return items

    def create_folder(self, parent_id: str, name: str) -> dict:
        return self.service.files().create(
            body={"name": name, "mimeType": "application/vnd.google-apps.folder",
                  "parents": [_file_id(parent_id)]},
            fields="id,name,mimeType,parents",
        ).execute()

    def upload_mp4(self, parent_id: str, name: str, path: Path, properties: dict) -> dict:
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(str(path), mimetype="video/mp4",
                                resumable=True, chunksize=8 * 1024 * 1024)
        return self.service.files().create(
            body={"name": name, "mimeType": "video/mp4",
                  "parents": [_file_id(parent_id)], "appProperties": properties},
            media_body=media, fields="id,name,mimeType,parents,appProperties,size",
        ).execute()

    def metadata(self, file_id: str) -> dict:
        return self.service.files().get(
            fileId=_file_id(file_id),
            fields="id,name,mimeType,parents,appProperties,size,trashed",
        ).execute()

    def download(self, file_id: str, output_path: Path) -> None:
        from googleapiclient.http import MediaIoBaseDownload
        request = self.service.files().get_media(fileId=_file_id(file_id))
        with Path(output_path).open("xb") as stream:
            downloader = MediaIoBaseDownload(stream, request, chunksize=8*1024*1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()


class FakeDriveClient:
    """In-memory Drive file/folder contract without Google credentials."""

    def __init__(self):
        self.entries = {
            "fakeDriveRoot0001": {
                "id": "fakeDriveRoot0001", "name": "root",
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [], "appProperties": {},
            }
        }
        self.data = {}
        self.upload_calls = 0
        self.download_calls = 0
        self.corrupt_download = False

    def list_named(self, parent_id, name):
        return [dict(v) for v in self.entries.values()
                if parent_id in v.get("parents", []) and v["name"] == name]

    def create_folder(self, parent_id, name):
        assert parent_id in self.entries
        fid = f"fakeFolder{uuid4().hex}"
        record = {
            "id": fid, "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id], "appProperties": {},
        }
        self.entries[fid] = record
        return dict(record)

    def upload_mp4(self, parent_id, name, path, properties):
        assert parent_id in self.entries
        self.upload_calls += 1
        fid = f"fakeVideo{uuid4().hex}"
        body = Path(path).read_bytes()
        self.data[fid] = body
        record = {
            "id": fid, "name": name, "mimeType": "video/mp4",
            "parents": [parent_id], "appProperties": properties.copy(),
            "size": str(len(body)), "trashed": False,
        }
        self.entries[fid] = record
        return dict(record)

    def metadata(self, file_id):
        return dict(self.entries[file_id])

    def download(self, file_id, output_path):
        self.download_calls += 1
        raw = self.data[file_id]
        if self.corrupt_download:
            raw = raw[:-1] + b"x"
        with Path(output_path).open("xb") as handle:
            handle.write(raw)


def _folder(client, parent: str, name: str) -> str:
    found = client.list_named(parent, name)
    if len(found) > 1:
        raise DriveArtifactError("Ambiguous folder name; refusing cross-series access")
    if found:
        folder = found[0]
        if (folder.get("mimeType") != "application/vnd.google-apps.folder"
                or parent not in folder.get("parents", [])):
            raise DriveArtifactError("Existing Drive item is not expected folder")
        return _file_id(folder["id"])
    created = client.create_folder(parent, name)
    if (created.get("mimeType") != "application/vnd.google-apps.folder"
            or parent not in created.get("parents", [])):
        raise DriveArtifactError("Created Drive folder has unexpected parent")
    return _file_id(created["id"])


def _verify_remote(client, file_id: str, folder_id: str, name: str,
                   artifact_id: str, expected_sha: str, expected_bytes: int,
                   *, destination: Path | None = None) -> bytes | None:
    item = client.metadata(_file_id(file_id))
    props = item.get("appProperties") or {}
    if (item.get("name") != name or item.get("mimeType") != "video/mp4"
            or folder_id not in item.get("parents", [])
            or props.get("drama_artifact") != artifact_id
            or props.get("sha256") != expected_sha
            or int(item.get("size", -1)) != expected_bytes
            or item.get("trashed") is True):
        raise DriveArtifactError("Drive metadata or ownership scope mismatch")
    tmp = destination or Path(os.getcwd()) / ("." + uuid4().hex + ".drivecheck")
    if tmp.exists():
        raise DriveArtifactError("Temporary verification target already exists")
    try:
        client.download(file_id, tmp)
        if not tmp.is_file() or tmp.is_symlink():
            raise DriveArtifactError("Remote video was not downloaded")
        actual_sha, size = _hash_file(tmp)
        if (actual_sha, size) != (expected_sha, expected_bytes):
            raise DriveArtifactError("Google Drive downloaded MP4 SHA256 mismatch")
        inspect_mp4(tmp)
        if destination is None:
            return None
    finally:
        if destination is None or not tmp.exists():
            tmp.unlink(missing_ok=True)


def _event(conn, entry_id: str, action: str, sha: str):
    conn.execute(
        "INSERT INTO drive_artifact_events (id,drive_copy_id,action,sha256,created_at) "
        "VALUES (?,?,?,?,?)",
        (new_id("driveevt"), entry_id, action, sha, timestamp()),
    )


def publish_drive_artifact(
    db: Database, artifact_id: str, local_store_root: Path,
    parent_folder_id: str, *, operator_approved: bool = False, client=None,
) -> dict:
    """Upload only after reviewing the approved local video, no overwrite."""
    _gated("DRAMA_ENABLE_DRIVE_UPLOAD", operator_approved)
    parent = _file_id(parent_folder_id)
    item = verify_stored_artifact(db, artifact_id, local_store_root)
    local = db.one("SELECT * FROM stored_artifacts WHERE id=?", (artifact_id,))
    key = _key(local)
    drive = client if client is not None else create_drive_client_from_env()
    root = _folder(drive, parent, "ai-short-drama-factory")
    series_folder = _folder(drive, root, _id(local["series_id"]))
    production_folder = _folder(drive, series_folder, _id(local["production_id"]))
    kind_folder = _folder(drive, production_folder, local["kind"])
    if local["kind"] == "shot_video":
        kind_folder = _folder(drive, kind_folder, _id(local["shot_job_id"]))
    name = f"{item['sha256']}.mp4"
    matches = drive.list_named(kind_folder, name)
    if len(matches) > 1:
        raise DriveArtifactError("Duplicate Drive objects; manual review required")
    if matches:
        remote_id = _file_id(matches[0]["id"])
    else:
        uploaded = drive.upload_mp4(
            kind_folder, name, Path(item["path"]),
            {"drama_artifact": artifact_id, "sha256": item["sha256"]},
        )
        remote_id = _file_id(uploaded["id"])
    _verify_remote(
        drive, remote_id, kind_folder, name, artifact_id,
        item["sha256"], item["size_bytes"],
    )
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT * FROM drive_artifacts WHERE artifact_id=? AND parent_folder_id=?",
            (artifact_id, parent),
        ).fetchone()
        if existing:
            if existing["drive_file_id"] != remote_id:
                raise DriveArtifactError("Drive catalog file ID conflicts with prior verified upload")
            return dict(existing)
        copy_id = new_id("drivecopy")
        conn.execute(
            """INSERT INTO drive_artifacts
            (id,artifact_id,parent_folder_id,drive_file_id,remote_folder_id,
            object_key,sha256,size_bytes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (copy_id, artifact_id, parent, remote_id, kind_folder, key,
             item["sha256"], item["size_bytes"], timestamp()),
        )
        _event(conn, copy_id, "uploaded_verified_by_download", item["sha256"])
        return dict(conn.execute(
            "SELECT * FROM drive_artifacts WHERE id=?", (copy_id,),
        ).fetchone())


def restore_drive_artifact(
    db: Database, drive_copy_id: str, local_store_root: Path,
    parent_folder_id: str, *, operator_approved: bool = False, client=None,
) -> dict:
    """Restore exact verified Drive bytes to the local immutable artifact tree."""
    _gated("DRAMA_ENABLE_DRIVE_READ", operator_approved)
    parent = _file_id(parent_folder_id)
    copy = db.one("SELECT * FROM drive_artifacts WHERE id=?", (drive_copy_id,))
    if copy is None or copy["parent_folder_id"] != parent:
        raise DriveArtifactError("Drive copy missing or outside requested parent")
    local = db.one("SELECT * FROM stored_artifacts WHERE id=?", (copy["artifact_id"],))
    if local is None or copy["object_key"] != _key(local):
        raise DriveArtifactError("Local catalog and Drive copy scope mismatch")
    if copy["sha256"] != local["sha256"] or copy["size_bytes"] != local["size_bytes"]:
        raise DriveArtifactError("Drive copy does not match reviewed local catalog")
    drive = client if client is not None else create_drive_client_from_env()
    root = Path(local_store_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    temp = root / ("." + uuid4().hex + ".driveincoming")
    try:
        _verify_remote(
            drive, copy["drive_file_id"], copy["remote_folder_id"],
            copy["sha256"] + ".mp4", local["id"],
            copy["sha256"], copy["size_bytes"], destination=temp,
        )
        _publish_bytes(
            temp, root, local["object_key"],
            copy["sha256"], copy["size_bytes"],
        )
        checked = verify_stored_artifact(db, local["id"], root)
        with db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            _event(conn, copy["id"], "downloaded_verified_local_copy", copy["sha256"])
        return {
            "drive_copy_id": copy["id"], "artifact_id": local["id"],
            "series_id": local["series_id"], "production_id": local["production_id"],
            "path": checked["path"], "sha256": checked["sha256"], "verified": True,
            "new_model_generation_calls": 0,
        }
    finally:
        temp.unlink(missing_ok=True)


def create_drive_client_from_env():
    """Only explicit calls can construct a network client; user OAuth, not SA."""
    import json
    encoded = os.getenv("DRAMA_DRIVE_USER_OAUTH_JSON")
    if not encoded:
        raise DriveArtifactError("User OAuth credentials unavailable")
    try:
        return GoogleDriveApiClient(json.loads(encoded))
    except (ValueError, TypeError, KeyError) as exc:
        raise DriveArtifactError("Invalid Drive OAuth credential structure") from exc
