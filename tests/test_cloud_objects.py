"""R2/S3 cloud adapter contract tests: offline FakeS3 only, zero external calls."""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from drama_factory.jobs.offline_worker import run_offline_production
from drama_factory.storage.cloud_objects import (
    CloudArtifactError, CloudTarget, FakeS3ArtifactClient,
    publish_cloud_artifact, restore_cloud_artifact,
)
from drama_factory.storage.artifacts import (
    verify_stored_artifact, restore_stored_artifact, recompose_from_stored_shots,
)


ffmpeg_required = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="Cloud-backed media contract needs FFmpeg to validate real MP4 bytes",
)

R2 = CloudTarget(
    provider="r2", bucket="private-drama-test",
    r2_account_id="a" * 32,
)
AWS = CloudTarget(
    provider="s3", bucket="private-drama-aws",
    region="ap-southeast-2",
)


def prepared(client, name):
    project = client.post("/api/v1/projects", json={
        "title": f"Cloud {name}",
        "premise": "Entirely original fake camera exercise",
    })
    assert project.status_code == 201, project.text
    series = project.json()["series_id"]
    ep = client.post(f"/api/v1/projects/{series}/episodes", json={
        "title": "Episode", "episode_number": 1,
        "target_duration_seconds": 2, "shots": [
            {"shot_id": "S1", "duration_seconds": 1,
             "visual_description": "A red ball rolls gently", "dialogue": ["One"]},
            {"shot_id": "S2", "duration_seconds": 1,
             "visual_description": "The ball stops", "dialogue": ["Two"]},
        ],
    })
    assert ep.status_code == 201, ep.text
    result = client.post(
        f"/api/v1/episodes/{ep.json()['episode_id']}/productions"
    )
    assert result.status_code == 201, result.text
    pid = result.json()["production_id"]
    assert client.post(f"/api/v1/productions/{pid}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{pid}/approve-characters").status_code == 200
    return series, pid


def enable(monkeypatch):
    monkeypatch.setenv("DRAMA_ENABLE_CLOUD_UPLOAD", "YES")
    monkeypatch.setenv("DRAMA_ENABLE_CLOUD_READ", "YES")


def sample_archive(client, tmp_path, name):
    series, production = prepared(client, name)
    db = client.app.state.db
    work = tmp_path / ("work-" + name)
    local_store = tmp_path / ("catalog-" + name)
    result = run_offline_production(db, production, work, store_root=local_store)
    return db, series, production, work, local_store, result


def test_target_config_is_strict_and_endpoints_are_provider_defined():
    assert R2.endpoint_url == "https://" + "a" * 32 + ".r2.cloudflarestorage.com"
    assert AWS.endpoint_url is None
    assert R2.identity != AWS.identity
    for kwargs in (
        {"provider": "r2", "bucket": "abc", "r2_account_id": "evil.example"},
        {"provider": "r2", "bucket": "abc", "r2_account_id": "a"*32, "region": "us-east-1"},
        {"provider": "s3", "bucket": "bad/bucket", "region": "us-east-1"},
        {"provider": "s3", "bucket": "abc", "region": "auto"},
        {"provider": "file", "bucket": "abc"},
    ):
        with pytest.raises(CloudArtifactError):
            CloudTarget(**kwargs)


def test_cloud_upload_and_download_are_off_by_default(client, tmp_path, monkeypatch):
    monkeypatch.delenv("DRAMA_ENABLE_CLOUD_UPLOAD", raising=False)
    monkeypatch.delenv("DRAMA_ENABLE_CLOUD_READ", raising=False)
    fake = FakeS3ArtifactClient()
    db = client.app.state.db
    with pytest.raises(CloudArtifactError, match="disabled"):
        publish_cloud_artifact(db, "missing", tmp_path, R2,
                               operator_approved=True, client=fake)
    assert fake.put_calls == fake.get_calls == 0
    with pytest.raises(CloudArtifactError, match="disabled"):
        restore_cloud_artifact(db, "missing", R2, tmp_path,
                               operator_approved=True, client=fake)
    assert fake.put_calls == fake.get_calls == 0


@ffmpeg_required
def test_r2_upload_integrity_restore_after_local_store_deleted(client, tmp_path, monkeypatch):
    db, _, production, work, local, render = sample_archive(client, tmp_path, "r2")
    fake = FakeS3ArtifactClient()
    enable(monkeypatch)
    target_id = render["published_artifact_ids"][-1]
    uploaded = publish_cloud_artifact(
        db, target_id, local, R2, operator_approved=True, client=fake,
    )
    assert uploaded["provider"] == "r2"
    assert uploaded["object_key"].startswith("private/")
    headers = fake.objects[(R2.bucket, uploaded["object_key"])]["headers"]
    assert headers["IfNoneMatch"] == "*"
    assert "ServerSideEncryption" not in headers
    assert "ACL" not in headers
    assert headers["CacheControl"] == "private, no-store"
    assert uploaded["sha256"] == db.one(
        "SELECT sha256 FROM stored_artifacts WHERE id=?", (target_id,),
    )["sha256"]
    assert len(db.many("SELECT * FROM cloud_artifacts")) == 1
    assert publish_cloud_artifact(
        db, target_id, local, R2, operator_approved=True, client=fake,
    )["id"] == uploaded["id"]
    assert fake.put_calls == 1
    shutil.rmtree(local)
    shutil.rmtree(work)
    new_local = tmp_path / "restored-catalog"
    recovered = restore_cloud_artifact(
        db, uploaded["id"], R2, new_local,
        operator_approved=True, client=fake,
    )
    assert recovered["verified"] and recovered["new_model_generation_calls"] == 0
    verified = verify_stored_artifact(db, target_id, new_local)
    assert verified["sha256"] == recovered["sha256"]
    second = restore_stored_artifact(
        db, target_id, new_local, tmp_path / "new-working-dir",
    )
    assert Path(second["restored_path"]).is_file()


@ffmpeg_required
def test_s3_upload_sse_headers_and_cross_series_isolation(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    fake = FakeS3ArtifactClient()
    db1, series1, p1, w1, local1, r1 = sample_archive(client, tmp_path, "alpha")
    db2, series2, p2, w2, local2, r2 = sample_archive(client, tmp_path, "beta")
    assert db1 is db2
    ids = []
    for aid, root in ((r1["published_artifact_ids"][-1], local1),
                      (r2["published_artifact_ids"][-1], local2)):
        ids.append(publish_cloud_artifact(
            db1, aid, root, AWS, operator_approved=True, client=fake,
        ))
    assert ids[0]["object_key"] != ids[1]["object_key"]
    assert ids[0]["object_key"].startswith("private/" + series1 + "/" + p1)
    assert ids[1]["object_key"].startswith("private/" + series2 + "/" + p2)
    assert all(record["headers"]["ServerSideEncryption"] == "AES256"
               for record in fake.objects.values())
    with pytest.raises(CloudArtifactError, match="target"):
        restore_cloud_artifact(
            db1, ids[0]["id"], R2, tmp_path / "wrong",
            operator_approved=True, client=fake,
        )


@ffmpeg_required
def test_fake_cloud_corruption_and_conflicting_object_cannot_silently_pass(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    db, _, _, _, local, render = sample_archive(client, tmp_path, "corrupt")
    fake = FakeS3ArtifactClient()
    aid = render["published_artifact_ids"][-1]
    # Simulate an earlier unrecorded upload whose object is correct.
    saved = publish_cloud_artifact(
        db, aid, local, R2, operator_approved=True, client=fake,
    )
    fake.objects[(R2.bucket, saved["object_key"])]["bytes"] += b"evil"
    with pytest.raises(CloudArtifactError, match="(metadata|SHA256|size)"):
        publish_cloud_artifact(
            db, aid, local, R2, operator_approved=True, client=fake,
        )
    with pytest.raises(CloudArtifactError):
        restore_cloud_artifact(
            db, saved["id"], R2, tmp_path / "bad",
            operator_approved=True, client=fake,
        )
    assert not (tmp_path / "bad" / saved["object_key"]).exists()


@ffmpeg_required
def test_download_failure_is_not_catalogued_and_retry_is_safe(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    db, _, _, _, local, render = sample_archive(client, tmp_path, "failure")
    aid = render["published_artifact_ids"][-1]
    fake = FakeS3ArtifactClient()
    fake.fail_get = True
    with pytest.raises(Exception, match="InjectedDownloadFailure"):
        publish_cloud_artifact(db, aid, local, R2,
                               operator_approved=True, client=fake)
    assert fake.put_calls == 1
    assert db.many("SELECT * FROM cloud_artifacts") == []
    fake.fail_get = False
    recovered = publish_cloud_artifact(
        db, aid, local, R2, operator_approved=True, client=fake,
    )
    assert recovered["id"]
    assert fake.put_calls == 2  # the second returns 412, then fully verifies existing bytes
    assert fake.get_calls >= 2
    assert len(db.many("SELECT * FROM cloud_artifacts")) == 1


@ffmpeg_required
def test_operator_gate_and_immutable_audit(client, tmp_path, monkeypatch):
    enable(monkeypatch)
    db, _, _, _, local, render = sample_archive(client, tmp_path, "gate")
    aid = render["published_artifact_ids"][-1]
    fake = FakeS3ArtifactClient()
    with pytest.raises(CloudArtifactError, match="disabled"):
        publish_cloud_artifact(db, aid, local, R2, client=fake)
    assert fake.put_calls == 0
    uploaded = publish_cloud_artifact(db, aid, local, R2,
                                      operator_approved=True, client=fake)
    record = db.one("SELECT id FROM cloud_artifact_events WHERE cloud_copy_id=?",
                    (uploaded["id"],))
    assert record is not None
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        db.exec("DELETE FROM cloud_artifact_events WHERE id=?", (record["id"],))
    with pytest.raises(CloudArtifactError, match="disabled"):
        restore_cloud_artifact(db, uploaded["id"], R2, tmp_path / "other", client=fake)


@ffmpeg_required
def test_two_shots_survive_only_in_fake_cloud_and_recompose(client, tmp_path, monkeypatch):
    """Once local asset catalog bytes are gone, fetch stored shots and cut new MP4."""
    enable(monkeypatch)
    fake = FakeS3ArtifactClient()
    db, series, production, work, local, rendered = sample_archive(
        client, tmp_path, "roundtrip",
    )
    cloud_copies = []
    for aid in rendered["published_artifact_ids"]:
        cloud_copies.append(publish_cloud_artifact(
            db, aid, local, R2, operator_approved=True, client=fake,
        ))
    assert len(cloud_copies) == 3
    shutil.rmtree(local)
    shutil.rmtree(work)
    recovered_local = tmp_path / "downloaded-local"
    for item in cloud_copies:
        restored = restore_cloud_artifact(
            db, item["id"], R2, recovered_local,
            operator_approved=True, client=fake,
        )
        assert restored["series_id"] == series
        assert restored["verified"]
    rebuilt = recompose_from_stored_shots(
        db, production, recovered_local, tmp_path / "fresh-work",
    )
    assert rebuilt["new_model_generation_calls"] == 0
    assert rebuilt["supplied_local_clips"] == 2
    assert rebuilt["placeholder_visuals"] is False
    from drama_factory.pipeline.offline_render import inspect_mp4
    assert inspect_mp4(Path(rebuilt["mp4_path"]), 2)["subtitle_codec"] == "mov_text"
    assert len(db.many("SELECT id FROM cloud_artifacts WHERE provider='r2'")) == 3
