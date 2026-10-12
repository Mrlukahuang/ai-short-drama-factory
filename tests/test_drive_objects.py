"""Google Drive storage adapter: private, scoped, no network in CI."""
from __future__ import annotations
import shutil
import sqlite3
from pathlib import Path
import pytest

from drama_factory.jobs.offline_worker import run_offline_production
from drama_factory.storage.drive_objects import (
    DriveArtifactError, FakeDriveClient, GoogleDriveApiClient,
    publish_drive_artifact, restore_drive_artifact,
)
from drama_factory.storage.artifacts import verify_stored_artifact, recompose_from_stored_shots

PARENT = "fakeDriveRoot0001"
MEDIA = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="FFmpeg required for real stored MP4 contract tests",
)


def approved(client, label):
    p = client.post("/api/v1/projects", json={
        "title": "Drive " + label,
        "premise": "An original and fictional scene without real identities",
    })
    assert p.status_code == 201, p.text
    sid = p.json()["series_id"]
    ep = client.post(f"/api/v1/projects/{sid}/episodes", json={
        "title": "Episode", "episode_number": 1,
        "target_duration_seconds": 2,
        "shots": [
            {"shot_id": "S1", "duration_seconds": 1,
             "visual_description": "Ball rolls", "dialogue": ["One"]},
            {"shot_id": "S2", "duration_seconds": 1,
             "visual_description": "Ball stops", "dialogue": ["Two"]},
        ],
    })
    assert ep.status_code == 201, ep.text
    production = client.post(
        f"/api/v1/episodes/{ep.json()['episode_id']}/productions"
    )
    assert production.status_code == 201, production.text
    pid = production.json()["production_id"]
    assert client.post(f"/api/v1/productions/{pid}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{pid}/approve-characters").status_code == 200
    return sid, pid


def archived(client, tmp_path, label):
    sid, production = approved(client, label)
    work, store = tmp_path / ("temp" + label), tmp_path / ("store" + label)
    result = run_offline_production(
        client.app.state.db, production, work, store_root=store,
    )
    return sid, production, work, store, result["published_artifact_ids"]


def enable(monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_DRIVE_UPLOAD", "YES")
    monkeypatch.setenv("DRAMA_ENABLE_DRIVE_READ", "YES")


def test_gates_fail_closed_before_any_remote_calls(client, tmp_path, monkeypatch):
    fake = FakeDriveClient()
    monkeypatch.delenv("DRAMA_ENABLE_DRIVE_UPLOAD", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_DRIVE_READ", raising=False)
    with pytest.raises(DriveArtifactError, match="disabled"):
        publish_drive_artifact(client.app.state.db, "unregistered", tmp_path,
                               PARENT, operator_approved=True, client=fake)
    with pytest.raises(DriveArtifactError, match="disabled"):
        restore_drive_artifact(client.app.state.db, "unregistered", tmp_path,
                               PARENT, operator_approved=True, client=fake)
    assert fake.upload_calls == fake.download_calls == 0


@MEDIA
def test_upload_one_verified_preview_and_restore_after_local_delete(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    db = client.app.state.db
    sid, prod, work, store, ids = archived(client, tmp_path, "Alpha")
    fake = FakeDriveClient()
    artifact_id = ids[-1]
    sent = publish_drive_artifact(db, artifact_id, store, PARENT,
                                  operator_approved=True, client=fake)
    assert fake.upload_calls == 1
    assert fake.download_calls == 1
    assert sent["drive_file_id"].startswith("fakeVideo")
    assert sent["object_key"].startswith(sid + "/" + prod + "/")
    assert len(db.many("SELECT * FROM drive_artifacts")) == 1
    again = publish_drive_artifact(db, artifact_id, store, PARENT,
                                   operator_approved=True, client=fake)
    assert sent["id"] == again["id"]
    assert fake.upload_calls == 1
    shutil.rmtree(store)
    shutil.rmtree(work)
    restored_store = tmp_path / "empty-drive-restore"
    restored = restore_drive_artifact(db, sent["id"], restored_store, PARENT,
                                      operator_approved=True, client=fake)
    assert restored["verified"] is True
    assert restored["sha256"] == sent["sha256"]
    assert restored["new_model_generation_calls"] == 0
    assert verify_stored_artifact(db, artifact_id, restored_store)["verified"]
    assert len(db.many("SELECT id FROM drive_artifact_events")) == 2


@MEDIA
def test_two_series_keep_separate_private_folders_and_can_recompose(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    db = client.app.state.db
    fake = FakeDriveClient()
    pairs = []
    for label in ("A", "B"):
        sid, production, work, store, ids = archived(client, tmp_path, label)
        received = [
            publish_drive_artifact(db, aid, store, PARENT,
                                   operator_approved=True, client=fake)
            for aid in ids
        ]
        pairs.append((sid, production, work, store, received))
    assert fake.upload_calls == 6
    assert len({r["drive_file_id"] for x in pairs for r in x[-1]}) == 6
    for sid, prod, work, store, cloud in pairs:
        shutil.rmtree(store)
        shutil.rmtree(work)
        restored_dir = tmp_path / ("fresh" + sid)
        for item in cloud:
            restored = restore_drive_artifact(
                db, item["id"], restored_dir, PARENT,
                operator_approved=True, client=fake,
            )
            assert restored["series_id"] == sid
        rebuilt = recompose_from_stored_shots(
            db, prod, restored_dir, tmp_path / ("rebuilt" + sid),
        )
        assert rebuilt["supplied_local_clips"] == 2
        assert rebuilt["new_model_generation_calls"] == 0
    assert db.many("SELECT id FROM stored_artifacts") != []


@MEDIA
def test_corruption_and_wrong_drive_root_never_restore(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    db = client.app.state.db
    _, _, _, store, ids = archived(client, tmp_path, "Corruption")
    fake = FakeDriveClient()
    sent = publish_drive_artifact(db, ids[-1], store, PARENT,
                                  operator_approved=True, client=fake)
    fake.corrupt_download = True
    with pytest.raises(DriveArtifactError, match="SHA256"):
        restore_drive_artifact(db, sent["id"], tmp_path / "damaged",
                               PARENT, operator_approved=True, client=fake)
    assert list((tmp_path / "damaged").rglob("*.mp4")) == []
    fake.corrupt_download = False
    with pytest.raises(DriveArtifactError, match="outside requested parent"):
        restore_drive_artifact(db, sent["id"], tmp_path / "wrong",
                               "differentDriveRoot0001",
                               operator_approved=True, client=fake)


@MEDIA
def test_existing_name_collision_rejected_not_overwritten(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    db = client.app.state.db
    _, _, _, store, ids = archived(client, tmp_path, "Collision")
    fake = FakeDriveClient()
    uploaded = publish_drive_artifact(db, ids[-1], store, PARENT,
                                      operator_approved=True, client=fake)
    entry = fake.entries[uploaded["drive_file_id"]]
    entry["appProperties"]["sha256"] = "0" * 64
    with pytest.raises(DriveArtifactError, match="metadata"):
        publish_drive_artifact(db, ids[-1], store, PARENT,
                               operator_approved=True, client=fake)
    assert fake.upload_calls == 1
    assert len(db.many("SELECT id FROM drive_artifacts")) == 1


@MEDIA
def test_nonreviewed_artifact_not_uploaded_and_audit_is_append_only(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    db = client.app.state.db
    fake = FakeDriveClient()
    with pytest.raises(Exception):
        publish_drive_artifact(db, "missing_artifact", tmp_path, PARENT,
                               operator_approved=True, client=fake)
    _, _, _, store, ids = archived(client, tmp_path, "Audit")
    result = publish_drive_artifact(db, ids[-1], store, PARENT,
                                    operator_approved=True, client=fake)
    event = db.one("SELECT id FROM drive_artifact_events WHERE drive_copy_id=?",
                   (result["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.exec("DELETE FROM drive_artifact_events WHERE id=?", (event["id"],))
    assert fake.upload_calls == 1


def test_google_sdk_files_list_uses_camel_case_and_paginates():
    """Use the Google API v3 keyword signature, not permissive **kwargs fakes."""
    class StrictDriveService:
        def __init__(self):
            self.calls = []
            self.response = None

        def files(self):
            return self

        def list(self, *, q, spaces, pageSize, fields, pageToken=None):
            assert q == "'fakeDriveRoot0001' in parents and name = 'video' and trashed = false"
            assert spaces == "drive"
            assert pageSize == 100
            assert "nextPageToken" in fields
            self.calls.append(pageToken)
            if pageToken is None:
                self.response = {
                    "files": [{"id": "firstvideo"}],
                    "nextPageToken": "second-page",
                }
            elif pageToken == "second-page":
                self.response = {"files": [{"id": "secondvideo"}]}
            else:
                raise AssertionError("Unexpected Drive pagination token")
            return self

        def execute(self):
            return self.response

    service = StrictDriveService()
    adapter = GoogleDriveApiClient.__new__(GoogleDriveApiClient)
    adapter.service = service
    files = adapter.list_named("fakeDriveRoot0001", "video")
    assert [item["id"] for item in files] == ["firstvideo", "secondvideo"]
    assert service.calls == [None, "second-page"]
