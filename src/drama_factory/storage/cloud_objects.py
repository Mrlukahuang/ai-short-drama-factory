"""Opt-in private R2/AWS S3 backup of already reviewed local MP4 artifacts.

No public upload API, pre-signed URL, delete, list-bucket, model invocation or
cloud request at import time. Every cloud object is content-addressed, conditionally
created, and verified by streaming GET before its catalog record is committed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from drama_factory.db import Database, new_id, timestamp
from drama_factory.pipeline.offline_render import inspect_mp4
from drama_factory.storage.artifacts import (
    ArtifactStoreError, _hash_file, _id, _publish_bytes,
    verify_stored_artifact,
)

_MAX_BYTES = 200 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
_REGION = re.compile(r"[a-z0-9-]{3,32}")
_R2_ACCOUNT = re.compile(r"[0-9a-f]{32}")


class CloudArtifactError(ArtifactStoreError):
    pass


@dataclass(frozen=True)
class CloudTarget:
    provider: str
    bucket: str
    region: str = "auto"
    r2_account_id: str | None = None

    def __post_init__(self):
        if self.provider not in ("r2", "s3"):
            raise CloudArtifactError("Supported cloud providers are r2 and s3")
        if (not _BUCKET.fullmatch(self.bucket) or ".." in self.bucket
                or self.bucket.startswith("xn--") or self.bucket.endswith("-s3alias")):
            raise CloudArtifactError("Invalid bucket name")
        if self.provider == "r2":
            if not self.r2_account_id or not _R2_ACCOUNT.fullmatch(self.r2_account_id):
                raise CloudArtifactError("R2 account ID must be 32 lower-case hex digits")
            if self.region != "auto":
                raise CloudArtifactError("R2 endpoint region must be auto")
        else:
            if self.r2_account_id is not None or self.region == "auto":
                raise CloudArtifactError("AWS S3 needs a region, not an R2 account ID")
            if not _REGION.fullmatch(self.region):
                raise CloudArtifactError("Invalid AWS region")

    @property
    def identity(self) -> str:
        material = (
            f"{self.provider}:{self.bucket}:{self.region}:"
            f"{self.r2_account_id or ''}"
        )
        return hashlib.sha256(material.encode("ascii")).hexdigest()

    @property
    def endpoint_url(self) -> str | None:
        if self.provider == "r2":
            return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"
        return None


def create_s3_client(target: CloudTarget):
    """SDK construction requires explicit caller action; not run during tests."""
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise CloudArtifactError(
            "Install optional cloud-s3 dependency to use R2/S3"
        ) from exc
    # R2 credentials come from the standard AWS credential environment/chain.
    return boto3.client(
        "s3",
        region_name=target.region if target.provider == "s3" else "auto",
        endpoint_url=target.endpoint_url,
        config=Config(signature_version="s3v4", retries={"max_attempts": 1}),
    )


def _allowed(flag: str, approved: bool) -> None:
    if approved is not True or os.getenv(flag) != "YES":
        raise CloudArtifactError(
            "Cloud storage operation disabled: operator approval and explicit gate required"
        )


def _key(catalog: dict) -> str:
    # Never accept a caller-controlled URL or remote key.
    series = _id(catalog["series_id"])
    production = _id(catalog["production_id"])
    if catalog["kind"] == "episode_preview":
        suffix = f"episode_preview/{catalog['sha256']}.mp4"
    elif catalog["kind"] == "shot_video":
        suffix = f"shot_video/{_id(catalog['shot_job_id'])}/{catalog['sha256']}.mp4"
    else:
        raise CloudArtifactError("Unknown stored artifact kind")
    if not _SHA.fullmatch(catalog["sha256"]):
        raise CloudArtifactError("Invalid artifact SHA256")
    expected = f"{series}/{production}/{suffix}"
    if catalog["object_key"] != expected:
        raise CloudArtifactError("Catalog object key does not match series/production")
    return "private/" + expected


def _cloud_error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str(response.get("Error", {}).get("Code", ""))
    return None


def _remote_bytes(client, target: CloudTarget, key: str,
                  *, expected_sha: str, expected_size: int,
                  destination: Path | None = None) -> int:
    """Stream entire object, do not trust ETag or head metadata as a checksum."""
    head = client.head_object(Bucket=target.bucket, Key=key)
    metadata = head.get("Metadata") or {}
    if metadata.get("sha256") != expected_sha or head.get("ContentLength") != expected_size:
        raise CloudArtifactError("Cloud object metadata or size mismatch")
    reply = client.get_object(Bucket=target.bucket, Key=key)
    if reply.get("ContentLength") != expected_size:
        raise CloudArtifactError("Remote response length mismatch")
    body = reply["Body"]
    digest = hashlib.sha256()
    total = 0
    try:
        handle = destination.open("xb") if destination is not None else None
        try:
            while True:
                chunk = body.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_BYTES or total > expected_size:
                    raise CloudArtifactError("Cloud media exceeds approved artifact size")
                digest.update(chunk)
                if handle is not None:
                    handle.write(chunk)
            if handle is not None:
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if handle is not None:
                handle.close()
    finally:
        close = getattr(body, "close", None)
        if callable(close):
            close()
    if total != expected_size or digest.hexdigest() != expected_sha:
        raise CloudArtifactError("Cloud object SHA256 mismatch")
    return total


def _audit(conn, copy_id: str, action: str, sha256: str):
    conn.execute(
        """INSERT INTO cloud_artifact_events
        (id,cloud_copy_id,action,sha256,created_at) VALUES (?,?,?,?,?)""",
        (new_id("cloud_evt"), copy_id, action, sha256, timestamp()),
    )


def publish_cloud_artifact(
    db: Database, artifact_id: str, local_store_root: Path,
    target: CloudTarget, *, operator_approved: bool = False, client=None,
) -> dict:
    """Explicit, conditional create-only upload; verify full remote bytes."""
    _allowed("DRAMA_ENABLE_CLOUD_UPLOAD", operator_approved)
    checked = verify_stored_artifact(db, artifact_id, local_store_root)
    catalog = db.one("SELECT * FROM stored_artifacts WHERE id=?", (artifact_id,))
    if catalog is None:
        raise CloudArtifactError("Catalog record missing")
    key = _key(catalog)
    store = client if client is not None else create_s3_client(target)
    existing = db.one(
        """SELECT * FROM cloud_artifacts WHERE artifact_id=? AND target_id=?""",
        (artifact_id, target.identity),
    )
    if existing:
        if existing["object_key"] != key or existing["sha256"] != checked["sha256"]:
            raise CloudArtifactError("Existing cloud catalog entry differs")
        _remote_bytes(
            store, target, key,
            expected_sha=checked["sha256"], expected_size=checked["size_bytes"],
        )
        return existing

    with Path(checked["path"]).open("rb") as file:
        kwargs = {
            "Bucket": target.bucket, "Key": key, "Body": file,
            "ContentLength": checked["size_bytes"],
            "IfNoneMatch": "*",
            "ContentType": "video/mp4",
            "CacheControl": "private, no-store",
            "Metadata": {
                "sha256": checked["sha256"],
                "artifact-id": artifact_id,
            },
        }
        # R2 rejects AWS x-amz-server-side-encryption PUT headers. R2's
        # provider-managed encryption is configured at the storage service.
        if target.provider == "s3":
            kwargs["ServerSideEncryption"] = "AES256"
        try:
            store.put_object(**kwargs)
        except Exception as exc:
            if _cloud_error_code(exc) not in ("412", "PreconditionFailed"):
                raise
            # Existing immutable object is acceptable ONLY after full GET hash.
    _remote_bytes(
        store, target, key,
        expected_sha=checked["sha256"], expected_size=checked["size_bytes"],
    )
    with db.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute(
            """SELECT * FROM cloud_artifacts WHERE artifact_id=? AND target_id=?""",
            (artifact_id, target.identity),
        ).fetchone()
        if previous:
            return dict(previous)
        copy_id = new_id("cloudcopy")
        conn.execute(
            """INSERT INTO cloud_artifacts
               (id,artifact_id,provider,bucket,target_id,object_key,sha256,size_bytes,created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (copy_id, artifact_id, target.provider, target.bucket,
             target.identity, key, checked["sha256"], checked["size_bytes"], timestamp()),
        )
        _audit(conn, copy_id, "uploaded_and_remote_hash_verified", checked["sha256"])
        return dict(conn.execute(
            "SELECT * FROM cloud_artifacts WHERE id=?", (copy_id,),
        ).fetchone())


def restore_cloud_artifact(
    db: Database, cloud_copy_id: str, target: CloudTarget, local_store_root: Path,
    *, operator_approved: bool = False, client=None,
) -> dict:
    """Private full-download restore into local verified artifact store.

    This is not a public URL or a signed-download endpoint. Calling it requires
    explicit operator permission and the separate cloud-read environment gate.
    """
    _allowed("DRAMA_ENABLE_CLOUD_READ", operator_approved)
    record = db.one("SELECT * FROM cloud_artifacts WHERE id=?", (cloud_copy_id,))
    if record is None:
        raise CloudArtifactError("Cloud artifact record missing")
    if (
        record["target_id"] != target.identity
        or record["provider"] != target.provider
        or record["bucket"] != target.bucket
    ):
        raise CloudArtifactError("Cloud target differs from catalog")
    catalog = db.one(
        "SELECT * FROM stored_artifacts WHERE id=?", (record["artifact_id"],),
    )
    if catalog is None or (
        record["object_key"] != _key(catalog)
        or record["sha256"] != catalog["sha256"]
        or record["size_bytes"] != catalog["size_bytes"]
    ):
        raise CloudArtifactError("Cloud catalog and local asset scope disagree")
    destination_root = Path(local_store_root).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    temp = destination_root / ("." + uuid4().hex + ".incoming.mp4")
    s3 = client if client is not None else create_s3_client(target)
    try:
        _remote_bytes(
            s3, target, record["object_key"],
            expected_sha=record["sha256"], expected_size=record["size_bytes"],
            destination=temp,
        )
        media = inspect_mp4(temp)
        if catalog["kind"] == "episode_preview" and media["subtitle_codec"] != "mov_text":
            raise CloudArtifactError("Cloud preview has lost subtitle track")
        # Local catalog key is independent of the private/ cloud prefix.
        committed = _publish_bytes(
            temp, destination_root, catalog["object_key"],
            record["sha256"], record["size_bytes"],
        )
        checked = verify_stored_artifact(db, catalog["id"], destination_root)
        if Path(checked["path"]) != committed:
            raise CloudArtifactError("Restored artifact path unexpectedly changed")
        with db.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            _audit(conn, record["id"], "downloaded_and_local_hash_verified",
                   record["sha256"])
        return {
            "cloud_copy_id": record["id"],
            "artifact_id": catalog["id"],
            "series_id": catalog["series_id"],
            "production_id": catalog["production_id"],
            "path": str(committed),
            "sha256": record["sha256"],
            "verified": True,
            "new_model_generation_calls": 0,
        }
    finally:
        temp.unlink(missing_ok=True)


class FakeS3ObjectError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3ArtifactClient:
    """In-memory S3 contract double; no credentials, network or server startup."""

    def __init__(self):
        self.objects: dict[tuple[str, str], dict] = {}
        self.put_calls = 0
        self.get_calls = 0
        self.fail_get = False

    def put_object(self, **kwargs):
        self.put_calls += 1
        key = (kwargs["Bucket"], kwargs["Key"])
        if key in self.objects and kwargs.get("IfNoneMatch") == "*":
            raise FakeS3ObjectError("PreconditionFailed")
        body = kwargs["Body"].read()
        if len(body) != kwargs["ContentLength"]:
            raise FakeS3ObjectError("InvalidContentLength")
        self.objects[key] = {
            "bytes": body, "metadata": kwargs.get("Metadata", {}).copy(),
            "headers": {k: v for k, v in kwargs.items() if k not in ("Body",)},
        }
        return {"ETag": "not-a-reliable-sha256"}

    def head_object(self, *, Bucket, Key):
        try:
            record = self.objects[(Bucket, Key)]
        except KeyError:
            raise FakeS3ObjectError("NoSuchKey") from None
        return {
            "ContentLength": len(record["bytes"]),
            "Metadata": record["metadata"].copy(),
        }

    def get_object(self, *, Bucket, Key):
        from io import BytesIO
        self.get_calls += 1
        if self.fail_get:
            raise FakeS3ObjectError("InjectedDownloadFailure")
        record = self.objects[(Bucket, Key)]
        return {
            "ContentLength": len(record["bytes"]),
            "Body": BytesIO(record["bytes"]),
        }
