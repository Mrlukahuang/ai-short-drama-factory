"""Existing Google result -> bound shot -> verified local MP4 -> episode.

No model generation requests; the injected provider exposes recovery only.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
import subprocess

import pytest

from drama_factory.jobs.budgets import configure_policy, reserve_job_budget
from drama_factory.jobs.shots import (
    prepare_shot_jobs, claim_next_job, record_submission_intent,
    record_submission, list_job_events,
)
from drama_factory.jobs.google_recovery import (
    ExistingVideoRecoveryError, bind_existing_google_file,
    recover_existing_google_shot, unlock_stale_google_recovery,
    compose_recovered_google_shots,
)
from drama_factory.pipeline.media_ingest import inspect_source
from drama_factory.pipeline.offline_render import inspect_mp4


requires_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="Real FFmpeg needed to verify source and finished MP4",
)


def make_submitted(client, label="Test", *, provider="google"):
    project = client.post("/api/v1/projects", json={
        "title": "Recovery " + label,
        "premise": "Fully fictional independent test scene",
    })
    assert project.status_code == 201
    series_id = project.json()["series_id"]
    episode = client.post(f"/api/v1/projects/{series_id}/episodes", json={
        "title": "Pilot", "episode_number": 1,
        "target_duration_seconds": 4,
        "shots": [
            {"shot_id": "S1", "duration_seconds": 2,
             "visual_description": "A small ball rolls across a wooden table",
             "video_model": "gemini-omni-1.1-flash"},
            {"shot_id": "S2", "duration_seconds": 2,
             "visual_description": "A silent empty room",
             "video_model": "gemini-omni-1.1-flash"},
        ],
    })
    assert episode.status_code == 201, episode.text
    run = client.post(
        f"/api/v1/episodes/{episode.json()['episode_id']}/productions"
    )
    assert run.status_code == 201
    production_id = run.json()["production_id"]
    assert client.post(f"/api/v1/productions/{production_id}/approve-script").status_code == 200
    assert client.post(f"/api/v1/productions/{production_id}/approve-characters").status_code == 200
    db = client.app.state.db
    prepare_shot_jobs(db, production_id, provider=provider)
    job = claim_next_job(db, "recovery-worker", production_id=production_id)
    assert job["status"] == "leased"
    if provider == "google":
        col = db.one("SELECT column_id FROM projects WHERE id=?", (series_id,))["column_id"]
        for kind, identifier in (
            ("column", col), ("series", series_id), ("provider", provider),
        ):
            configure_policy(db, kind, identifier,
                             daily_limit_usd="5.00", max_active_jobs=2)
        reserve_job_budget(db, job["id"], estimated_charge_usd="0.50")
        record_submission_intent(db, job["id"], "recovery-worker")
        record_submission(db, job["id"], "recovery-worker",
                          "tasks/" + job["id"])
    return db, series_id, production_id, job["id"]


def make_video(path: Path, *, seconds=3):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=15",
        "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(path),
    ], capture_output=True, text=True, check=True, timeout=90)
    return path


class RecoveryOnlyStub:
    def __init__(self, media):
        self.media = media
        self.downloads = 0
        self.generations = 0

    def recover_existing(self, file_id, destination, *,
                         operator_approved, min_duration_seconds):
        assert file_id.startswith("generated")
        assert operator_approved is True
        assert min_duration_seconds == 2
        self.downloads += 1
        Path(destination).write_bytes(self.media.read_bytes())
        return {
            "model_calls": 0, "is_mock": False, "recovered_existing": True,
            "media_path": str(destination),
            "source_sha256": hashlib.sha256(self.media.read_bytes()).hexdigest(),
        }

    def generate(self, *a, **kw):
        self.generations += 1
        raise AssertionError("Paid generation must NEVER be called")


@requires_ffmpeg
def test_existing_google_file_recovered_once_then_composed(client, tmp_path, monkeypatch):
    monkeypatch.delenv("DRAMA_ENABLE_PAID_GENERATION", raising=False)
    db, series, run, job_id = make_submitted(client)
    source = make_video(tmp_path / "provider.mp4")
    stub = RecoveryOnlyStub(source)
    binding = bind_existing_google_file(
        db, job_id, "generated123", operator_reviewed=True,
    )
    assert binding["file_id"] == "generated123"
    root = tmp_path / "media"
    first = recover_existing_google_shot(
        db, job_id, root, operator_reviewed=True, provider=stub,
    )
    assert first["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert first["new_model_generation_calls"] == 0
    assert first["vendor_charge_usd"] is None
    assert stub.downloads == 1 and stub.generations == 0
    assert db.one("SELECT status FROM shot_jobs WHERE id=?", (job_id,))["status"] == "succeeded"
    second = recover_existing_google_shot(
        db, job_id, root, operator_reviewed=True, provider=stub,
    )
    assert second["cached"] is True
    assert stub.downloads == 1
    result = compose_recovered_google_shots(db, run, root)
    assert result["reused_existing_google_shots"] == 1
    assert result["new_model_generation_calls"] == 0
    assert result["supplied_local_clips"] == 1
    assert result["placeholder_visuals"] is True
    assert inspect_mp4(Path(result["mp4_path"]), 4)["subtitle_codec"] == "mov_text"
    assert any(e["action"] == "existing_google_file_bound"
               for e in list_job_events(db, job_id))


@requires_ffmpeg
def test_crash_after_download_reuses_local_mp4_without_second_provider_call(client, tmp_path):
    db, _, _, job_id = make_submitted(client)
    bind_existing_google_file(db, job_id, "generated123", operator_reviewed=True)
    root = tmp_path / "local"
    row = db.one("SELECT * FROM shot_jobs WHERE id=?", (job_id,))
    target = root / row["series_id"] / row["production_id"] / job_id / "source.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = make_video(target)
    stub = RecoveryOnlyStub(source)
    result = recover_existing_google_shot(
        db, job_id, root, operator_reviewed=True, provider=stub,
    )
    assert result["cached"] is False  # Completed from crash residue, not prior job result.
    assert stub.downloads == 0
    assert db.one("SELECT result_sha256 FROM shot_jobs WHERE id=?",
                  (job_id,))["result_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_binding_requires_existing_paid_task_and_operator(client, tmp_path):
    db, _, _, job_id = make_submitted(client)
    with pytest.raises(ExistingVideoRecoveryError, match="operator"):
        bind_existing_google_file(db, job_id, "generated123")
    with pytest.raises(Exception, match="Invalid Google file ID"):
        bind_existing_google_file(db, job_id, "../bad", operator_reviewed=True)
    bind_existing_google_file(db, job_id, "generated123", operator_reviewed=True)
    assert bind_existing_google_file(
        db, job_id, "generated123", operator_reviewed=True,
    )["file_id"] == "generated123"
    with pytest.raises(ExistingVideoRecoveryError, match="immutable"):
        bind_existing_google_file(db, job_id, "generated456", operator_reviewed=True)
    with pytest.raises(ExistingVideoRecoveryError, match="operator"):
        recover_existing_google_shot(db, job_id, tmp_path)
    with pytest.raises(ExistingVideoRecoveryError, match="lock"):
        unlock_stale_google_recovery(db, job_id, operator_reviewed=True)


def test_fake_provider_cannot_recover_google_video(client):
    db, _, _, job_id = make_submitted(client, provider="fake")
    with pytest.raises(ExistingVideoRecoveryError, match="Google"):
        bind_existing_google_file(db, job_id, "generated123", operator_reviewed=True)
    assert db.many("SELECT * FROM google_existing_files") == []


@requires_ffmpeg
def test_provider_receipt_must_match_actual_download(client, tmp_path):
    db, _, _, job_id = make_submitted(client)
    bind_existing_google_file(db, job_id, "generated123", operator_reviewed=True)
    source = make_video(tmp_path / "source.mp4")
    class TamperedReceipt(RecoveryOnlyStub):
        def recover_existing(self, *a, **k):
            result = super().recover_existing(*a, **k)
            result["source_sha256"] = "0" * 64
            return result
    stub = TamperedReceipt(source)
    with pytest.raises(ExistingVideoRecoveryError, match="hash"):
        recover_existing_google_shot(
            db, job_id, tmp_path / "files", operator_reviewed=True, provider=stub,
        )
    assert stub.generations == 0
    assert db.one("SELECT status FROM shot_jobs WHERE id=?", (job_id,))["status"] == "submitted"
    assert db.one("SELECT recovery_active FROM google_existing_files WHERE job_id=?",
                  (job_id,))["recovery_active"] == 0


@requires_ffmpeg
def test_tampered_completed_clip_refuses_recomposition(client, tmp_path):
    db, _, run, job_id = make_submitted(client)
    source = make_video(tmp_path / "source.mp4")
    bind_existing_google_file(db, job_id, "generated123", operator_reviewed=True)
    receipt = recover_existing_google_shot(
        db, job_id, tmp_path / "work", operator_reviewed=True,
        provider=RecoveryOnlyStub(source),
    )
    recovered = Path(receipt["mp4_path"])
    recovered.write_bytes(b"not the source" * 300)
    with pytest.raises(Exception):
        compose_recovered_google_shots(db, run, tmp_path / "work")
    assert db.one("SELECT status FROM shot_jobs WHERE id=?", (job_id,))["status"] == "succeeded"


@requires_ffmpeg
def test_parallel_series_boundaries_do_not_cross(client, tmp_path):
    db, sid1, run1, job1 = make_submitted(client, "SeriesA")
    _, sid2, run2, job2 = make_submitted(client, "SeriesB")
    clip = make_video(tmp_path / "original.mp4")
    for job, file_id in ((job1, "generated111"), (job2, "generated222")):
        bind_existing_google_file(db, job, file_id, operator_reviewed=True)
        recover_existing_google_shot(
            db, job, tmp_path / "outputs", operator_reviewed=True,
            provider=RecoveryOnlyStub(clip),
        )
    first = compose_recovered_google_shots(db, run1, tmp_path / "outputs")
    second = compose_recovered_google_shots(db, run2, tmp_path / "outputs")
    assert first["series_id"] == sid1 and second["series_id"] == sid2
    assert first["mp4_path"] != second["mp4_path"]
    assert db.one("SELECT series_id FROM shot_jobs WHERE id=?", (job1,))["series_id"] == sid1
    assert db.one("SELECT series_id FROM shot_jobs WHERE id=?", (job2,))["series_id"] == sid2
