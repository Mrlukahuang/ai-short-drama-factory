"""Real FFmpeg checks for immutable local delivery outside disposable workspaces."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from drama_factory.jobs.offline_worker import run_offline_production, run_offline_multi_series
from drama_factory.storage.artifacts import (
    ArtifactStoreError, publish_episode_preview, publish_shot_video,
    verify_stored_artifact,
)


ffmpeg_required = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="Real FFmpeg/FFprobe required for stored-media integration",
)


def reviewed_production(client, label):
    project = client.post("/api/v1/projects", json={
        "title": "Archived " + label,
        "premise": "An original offline production for media storage",
    })
    assert project.status_code == 201, project.text
    series = project.json()["series_id"]
    episode = client.post(f"/api/v1/projects/{series}/episodes", json={
        "title": "Pilot " + label,
        "episode_number": 1, "target_duration_seconds": 2,
        "shots": [
            {"shot_id": "shotA", "duration_seconds": 1,
             "visual_description": "A fictional camera tracks a ball",
             "dialogue": ["One"]},
            {"shot_id": "shotB", "duration_seconds": 1,
             "visual_description": "A fictional camera sees a table",
             "dialogue": ["Two"]},
        ],
    })
    assert episode.status_code == 201, episode.text
    run = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
    )
    assert run.status_code == 201, run.text
    production = run.json()["production_id"]
    assert client.post(f"/api/v1/productions/{production}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{production}/approve-characters").status_code == 200
    return series, production


@ffmpeg_required
def test_published_mp4_is_verifiable_after_work_directory_is_removed(client, tmp_path):
    series, production = reviewed_production(client, "Durable")
    work = tmp_path / "temporary-work"
    store = tmp_path / "local-object-store"
    result = run_offline_production(
        client.app.state.db, production, work, store_root=store,
    )
    ids = result["published_artifact_ids"]
    assert len(ids) == 3
    records = client.app.state.db.many(
        "SELECT * FROM stored_artifacts WHERE production_id=? ORDER BY kind,id",
        (production,),
    )
    assert len(records) == 3
    assert sum(r["kind"] == "episode_preview" for r in records) == 1
    assert sum(r["kind"] == "shot_video" for r in records) == 2
    assert {r["series_id"] for r in records} == {series}
    for record in records:
        checked = verify_stored_artifact(client.app.state.db, record["id"], store)
        assert checked["verified"] is True
        assert checked["size_bytes"] > 1000
        assert hashlib.sha256(Path(checked["path"]).read_bytes()).hexdigest() == record["sha256"]
    # Demonstrate object files are independent from disposable FFmpeg workspace.
    shutil.rmtree(work)
    for record in records:
        assert verify_stored_artifact(client.app.state.db, record["id"], store)["verified"]


@ffmpeg_required
def test_repeat_publish_dedupes_and_does_not_change_job_attempts(client, tmp_path):
    _, production = reviewed_production(client, "Repeat")
    db = client.app.state.db
    work = tmp_path / "working"
    store = tmp_path / "permanent"
    first = run_offline_production(db, production, work, store_root=store)
    original = db.many(
        "SELECT id,attempts FROM shot_jobs WHERE production_id=? ORDER BY id",
        (production,),
    )
    again = run_offline_production(db, production, work, store_root=store)
    assert first["published_artifact_ids"] == again["published_artifact_ids"]
    assert first["mp4_sha256"] == again["mp4_sha256"]
    assert db.many("SELECT id FROM stored_artifacts WHERE production_id=?", (production,)) != []
    assert len(db.many("SELECT id FROM stored_artifacts WHERE production_id=?", (production,))) == 3
    assert db.many("SELECT id,attempts FROM shot_jobs WHERE production_id=? ORDER BY id",
                   (production,)) == original


@ffmpeg_required
def test_immutable_object_tampering_detected(client, tmp_path):
    _, production = reviewed_production(client, "Tamper")
    db = client.app.state.db
    work, store = tmp_path / "render", tmp_path / "objects"
    run_offline_production(db, production, work, store_root=store)
    record = db.one(
        "SELECT * FROM stored_artifacts WHERE production_id=? AND kind='episode_preview'",
        (production,),
    )
    path = store / record["object_key"]
    with path.open("ab") as handle:
        handle.write(b"tampered data")
    with pytest.raises(ArtifactStoreError, match="integrity"):
        verify_stored_artifact(db, record["id"], store)
    with pytest.raises(ArtifactStoreError, match="different bytes"):
        publish_episode_preview(db, production, work, store)
    assert len(db.many("SELECT id FROM stored_artifacts")) == 3


@ffmpeg_required
def test_working_source_tampering_and_symlink_are_rejected(client, tmp_path):
    _, production = reviewed_production(client, "Source")
    db = client.app.state.db
    work = tmp_path / "render"
    run_offline_production(db, production, work)
    # Locate the known FFmpeg working file (never treat its manifest as a path).
    actual = next(work.glob("*/" + production + "/preview.mp4"))
    original = actual.read_bytes()
    actual.write_bytes(original + b"altered")
    with pytest.raises(ArtifactStoreError, match="SHA256"):
        publish_episode_preview(db, production, work, tmp_path / "store")
    actual.write_bytes(original)
    external = tmp_path / "outside.mp4"
    external.write_bytes(original)
    actual.unlink()
    actual.symlink_to(external)
    with pytest.raises(ArtifactStoreError, match="symlink"):
        publish_episode_preview(db, production, work, tmp_path / "store")
    assert db.many("SELECT id FROM stored_artifacts") == []


@ffmpeg_required
def test_cross_series_concurrent_object_keys_are_isolated(client, tmp_path):
    s1, p1 = reviewed_production(client, "LineA")
    s2, p2 = reviewed_production(client, "LineB")
    db = client.app.state.db
    store = tmp_path / "store"
    results = run_offline_multi_series(
        db, [p1, p2], tmp_path / "work",
        max_workers=2, store_root=store,
    )
    assert len(results) == 2
    assert all(len(r["published_artifact_ids"]) == 3 for r in results)
    one = db.many("SELECT object_key FROM stored_artifacts WHERE production_id=?", (p1,))
    two = db.many("SELECT object_key FROM stored_artifacts WHERE production_id=?", (p2,))
    assert len(one) == len(two) == 3
    assert all(row["object_key"].startswith(s1 + "/") for row in one)
    assert all(row["object_key"].startswith(s2 + "/") for row in two)
    assert not ({r["object_key"] for r in one} & {r["object_key"] for r in two})
    for result in results:
        for artifact_id in result["published_artifact_ids"]:
            assert verify_stored_artifact(db, artifact_id, store)["verified"] is True


def test_unapproved_or_unknown_objects_cannot_be_published(client, tmp_path):
    _, production = reviewed_production(client, "Unready")
    db = client.app.state.db
    with pytest.raises(ArtifactStoreError, match="not yet finished"):
        publish_episode_preview(db, production, tmp_path / "work", tmp_path / "store")
    with pytest.raises(ArtifactStoreError, match="Only succeeded"):
        publish_shot_video(db, "shotjob_doesnotexist", tmp_path, tmp_path)
    with pytest.raises(ArtifactStoreError, match="does not exist"):
        verify_stored_artifact(db, "artifact_invalid", tmp_path)
