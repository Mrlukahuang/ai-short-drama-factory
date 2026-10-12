"""A dedicated Turso metadata table receives only fully verified Drive receipts.

No real Turso connection is created by these tests. The injected sqlite3
connection deliberately mimics only the remote SQL/transaction contract.
"""
from __future__ import annotations

import os
import sqlite3
import shutil

import pytest

from drama_factory.jobs.offline_worker import run_offline_production
from drama_factory.storage.drive_objects import (
    FakeDriveClient, publish_drive_artifact, restore_drive_artifact,
)
from drama_factory.storage.turso_receipts import (
    TursoMetadataTarget, TursoReceiptError, mirror_verified_drive_receipt,
)

TEST_TARGET = TursoMetadataTarget(
    url="libsql://ai-short-drama-factory-example.turso.io",
    engine="libsql",
)
REMOTE = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="Real MP4 needed to prove Drive source integrity before metadata mirroring",
)


def enable(monkeypatch):
    for name in ("DRAMA_ENABLE_DRIVE_UPLOAD", "DRAMA_ENABLE_DRIVE_READ",
                 "DRAMA_ENABLE_TURSO_METADATA_WRITE"):
        monkeypatch.setenv(name, "YES")
    monkeypatch.setenv("DRAMA_TURSO_WRITE_CONFIRM", "MIRROR_VERIFIED_DRIVE_METADATA")


def reviewed(client, tmp_path, label):
    project = client.post("/api/v1/projects", json={
        "title": "Turso " + label,
        "premise": "Entirely fictional offline test content",
    })
    assert project.status_code == 201, project.text
    series = project.json()["series_id"]
    episode = client.post(f"/api/v1/projects/{series}/episodes", json={
        "title": "Test Episode", "episode_number": 1,
        "target_duration_seconds": 2,
        "shots": [
            {"shot_id": "S1", "duration_seconds": 1,
             "visual_description": "First synthetic scene", "dialogue": ["One"]},
            {"shot_id": "S2", "duration_seconds": 1,
             "visual_description": "Second synthetic scene", "dialogue": ["Two"]},
        ],
    })
    assert episode.status_code == 201, episode.text
    production = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
    )
    assert production.status_code == 201, production.text
    pid = production.json()["production_id"]
    for approval in ("approve-script", "approve-characters"):
        assert client.post(f"/api/v1/productions/{pid}/{approval}").status_code == 200
    work = tmp_path / ("work_" + label)
    stored = tmp_path / ("stored_" + label)
    result = run_offline_production(client.app.state.db, pid, work, store_root=stored)
    return series, pid, stored, result["published_artifact_ids"][-1]


def verified(client, tmp_path, monkeypatch, label, fake=None):
    enable(monkeypatch)
    sid, pid, stored, aid = reviewed(client, tmp_path, label)
    db = client.app.state.db
    fake = fake or FakeDriveClient()
    record = publish_drive_artifact(
        db, aid, stored, "fakeDriveRoot0001",
        operator_approved=True, client=fake,
    )
    recovered_dir = tmp_path / ("recovered_" + label)
    restore_drive_artifact(
        db, record["id"], recovered_dir, "fakeDriveRoot0001",
        operator_approved=True, client=fake,
    )
    return sid, pid, record["id"], recovered_dir, fake


def test_target_engine_url_and_dedicated_namespace_validation():
    TursoMetadataTarget(url="https://ai-short-drama-factory-example.turso.io", engine="turso")
    TursoMetadataTarget(url="https://ai-short-drama-factory-example.turso.io", engine="libsql")
    # Regional URLs are returned by the real Turso dashboard (Sydney shown here).
    for url, engine in (
        ("libsql://ai-short-drama-factory-mrlukahuang.aws-ap-southeast-2.turso.io", "libsql"),
        ("https://ai-short-drama-factory-mrlukahuang.aws-ap-southeast-2.turso.io", "libsql"),
        ("https://ai-short-drama-factory-example.aws-ap-southeast-2.turso.io", "turso"),
    ):
        TursoMetadataTarget(url=url, engine=engine)
    for bad in (
        ("https://unrelated-project-example.turso.io", "turso"),
        ("libsql://unrelated-project-example.aws-ap-southeast-2.turso.io", "libsql"),
        ("libsql://ai-short-drama-factory-example.private.aws-ap-southeast-2.turso.io", "libsql"),
        ("libsql://ai-short-drama-factory-example.aws-ap-southeast-2.turso.io.evil.example", "libsql"),
        ("libsql://ai-short-drama-factory-example.aws-ap-southeast-2.turso.io?authToken=secret", "libsql"),
        ("libsql://user:pass@ai-short-drama-factory-example.aws-ap-southeast-2.turso.io", "libsql"),
        ("libsql://ai-short-drama-factory-example.aws-ap-southeast-2.turso.io:443", "libsql"),
        ("libsql://ai-short-drama-factory-example.aws-ap-southeast-2.turso.io/path", "libsql"),
        ("http://ai-short-drama-factory-example.turso.io", "turso"),
        ("libsql://ai-short-drama-factory-example.turso.io", "turso"),
        ("https://ai-short-drama-factory-example.turso.io.evil.com", "turso"),
        ("https://ai-short-drama-factory-example.turso.io/foo", "turso"),
        ("https://ai-short-drama-factory-example.turso.io/?token=secret", "turso"),
        ("https://user:pass@ai-short-drama-factory-example.turso.io", "turso"),
        ("https://ai-short-drama-factory-example.turso.io:8000", "turso"),
        ("https://ai-short-drama-factory-example.turso.io", "unsupported"),
    ):
        with pytest.raises(TursoReceiptError):
            TursoMetadataTarget(url=bad[0], engine=bad[1])


def test_no_remote_access_without_manual_gates(client, tmp_path, monkeypatch):
    monkeypatch.delenv("DRAMA_ENABLE_TURSO_METADATA_WRITE", raising=False)
    monkeypatch.delenv("DRAMA_TURSO_WRITE_CONFIRM", raising=False)
    remote = sqlite3.connect(":memory:")
    with pytest.raises(TursoReceiptError, match="disabled"):
        mirror_verified_drive_receipt(
            client.app.state.db, "missing", tmp_path, TEST_TARGET,
            operator_approved=True, remote=remote,
        )
    assert remote.execute("SELECT name FROM sqlite_master WHERE name='drama_drive_receipts_v1'").fetchone() is None
    remote.close()


@REMOTE
def test_verified_drive_copy_mirrors_once_and_is_immutable(client, tmp_path, monkeypatch):
    sid, pid, copy_id, local_root, fake = verified(client, tmp_path, monkeypatch, "One")
    remote = sqlite3.connect(":memory:")
    receipt = mirror_verified_drive_receipt(
        client.app.state.db, copy_id, local_root, TEST_TARGET,
        operator_approved=True, remote=remote,
    )
    assert receipt["mirrored"] is True and receipt["cached"] is False
    assert receipt["series_id"] == sid and receipt["production_id"] == pid
    assert receipt["google_drive_file_id_redacted"] is True
    assert receipt["new_ai_model_generation_calls"] == 0
    repeat = mirror_verified_drive_receipt(
        client.app.state.db, copy_id, local_root, TEST_TARGET,
        operator_approved=True, remote=remote,
    )
    assert repeat["cached"] is True
    assert remote.execute("SELECT COUNT(*) FROM drama_drive_receipts_v1").fetchone()[0] == 1
    assert remote.execute("SELECT sha256 FROM drama_drive_receipts_v1").fetchone()[0] == receipt["sha256"]
    assert "fakeVideo" not in str(receipt)
    assert fake.upload_calls == 1
    remote.close()


@REMOTE
def test_conflicts_do_not_overwrite_existing_metadata(client, tmp_path, monkeypatch):
    sid, pid, copy_id, local_root, _ = verified(client, tmp_path, monkeypatch, "Conflict")
    remote = sqlite3.connect(":memory:")
    mirror_verified_drive_receipt(
        client.app.state.db, copy_id, local_root, TEST_TARGET,
        operator_approved=True, remote=remote,
    )
    remote.execute(
        "UPDATE drama_drive_receipts_v1 SET sha256=? WHERE drive_copy_id=?",
        ("0" * 64, copy_id),
    )
    remote.commit()
    with pytest.raises(TursoReceiptError, match="conflict"):
        mirror_verified_drive_receipt(
            client.app.state.db, copy_id, local_root, TEST_TARGET,
            operator_approved=True, remote=remote,
        )
    assert remote.execute(
        "SELECT sha256 FROM drama_drive_receipts_v1 WHERE drive_copy_id=?", (copy_id,),
    ).fetchone()[0] == "0" * 64
    remote.close()


@REMOTE
def test_missing_download_evidence_blocks_mirror(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    _, _, stored, artifact_id = reviewed(client, tmp_path, "Missing")
    db = client.app.state.db
    fake = FakeDriveClient()
    sent = publish_drive_artifact(
        db, artifact_id, stored, "fakeDriveRoot0001",
        operator_approved=True, client=fake,
    )
    remote = sqlite3.connect(":memory:")
    with pytest.raises(TursoReceiptError, match="upload AND recovery"):
        mirror_verified_drive_receipt(
            db, sent["id"], stored, TEST_TARGET,
            operator_approved=True, remote=remote,
        )
    assert remote.execute("SELECT name FROM sqlite_master WHERE name='drama_drive_receipts_v1'").fetchone() is None
    remote.close()


@REMOTE
def test_two_series_cannot_reuse_a_drive_object(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    fake = FakeDriveClient()
    s1, p1, a, path1, _ = verified(client, tmp_path, monkeypatch, "A", fake=fake)
    s2, p2, b, path2, _ = verified(client, tmp_path, monkeypatch, "B", fake=fake)
    remote = sqlite3.connect(":memory:")
    for copy_id, root in ((a, path1), (b, path2)):
        mirror_verified_drive_receipt(
            client.app.state.db, copy_id, root, TEST_TARGET,
            operator_approved=True, remote=remote,
        )
    rows = remote.execute(
        "SELECT series_id,production_id,drive_file_id FROM drama_drive_receipts_v1"
    ).fetchall()
    assert {(x[0], x[1]) for x in rows} == {(s1, p1), (s2, p2)}
    assert rows[0][2] != rows[1][2]
    assert remote.execute("SELECT COUNT(*) FROM drama_drive_receipts_v1").fetchone()[0] == 2
    remote.close()


@REMOTE
def test_corrupted_recovered_local_media_must_never_mirror(client, tmp_path, monkeypatch):
    _, _, copy_id, local_root, _ = verified(client, tmp_path, monkeypatch, "Tamper")
    media = next(local_root.rglob("*.mp4"))
    media.write_bytes(b"not a verified mp4" * 100)
    remote = sqlite3.connect(":memory:")
    with pytest.raises(Exception):
        mirror_verified_drive_receipt(
            client.app.state.db, copy_id, local_root, TEST_TARGET,
            operator_approved=True, remote=remote,
        )
    assert remote.execute("SELECT name FROM sqlite_master WHERE name='drama_drive_receipts_v1'").fetchone() is None
    remote.close()
