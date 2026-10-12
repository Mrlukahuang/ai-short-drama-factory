"""Two independent series: real offline MP4s, job claims, no paid calls."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from drama_factory.jobs.offline_worker import (
    OfflineWorkerError, run_offline_multi_series, run_offline_production,
)
from drama_factory.jobs.shots import (
    ShotJobError, claim_next_job, complete_fake_clip_job, prepare_shot_jobs,
    restore_failed_job,
)
from drama_factory.pipeline.offline_render import PreviewError, inspect_mp4


needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="FFmpeg integration needs binaries",
)


def ready_run(client, label="A", *, approve=True):
    response = client.post("/api/v1/projects", json={
        "title": f"Offline {label}", "premise": "Entirely synthetic motion studies",
    })
    assert response.status_code == 201, response.text
    sid = response.json()["series_id"]
    response = client.post(f"/api/v1/projects/{sid}/episodes", json={
        "title": f"Ep {label}", "episode_number": 1,
        "target_duration_seconds": 2,
        "shots": [
            {"shot_id": "shot_1", "duration_seconds": 1,
             "visual_description": f"{label} first angle", "dialogue": ["Line 1"]},
            {"shot_id": "shot_2", "duration_seconds": 1,
             "visual_description": f"{label} second angle", "dialogue": ["Line 2"]},
        ],
    })
    assert response.status_code == 201, response.text
    eid = response.json()["episode_id"]
    run = client.post(f"/api/v1/episodes/{eid}/productions")
    assert run.status_code == 201, run.text
    pid = run.json()["production_id"]
    if approve:
        assert client.post(f"/api/v1/productions/{pid}/approve-script").status_code == 200
        assert client.post(f"/api/v1/productions/{pid}/approve-characters").status_code == 200
    return sid, pid


@needs_ffmpeg
def test_two_series_complete_in_bounded_parallel_without_provider_calls(client, tmp_path):
    sid_a, prod_a = ready_run(client, "A")
    sid_b, prod_b = ready_run(client, "B")
    db = client.app.state.db
    outputs = run_offline_multi_series(db, [prod_a, prod_b], tmp_path, max_workers=2)
    assert [r["production_id"] for r in outputs] == [prod_a, prod_b]
    assert {r["series_id"] for r in outputs} == {sid_a, sid_b}
    assert all(r["succeeded"] == 2 and r["paid_provider_calls"] == 0 for r in outputs)
    assert all(r["real_ai_video"] is False for r in outputs)
    assert outputs[0]["mp4_path"] != outputs[1]["mp4_path"]
    for result in outputs:
        media = inspect_mp4(Path(result["mp4_path"]), 2)
        assert media["subtitle_codec"] == "mov_text"
        jobs = db.many("SELECT * FROM shot_jobs WHERE production_id=?",
                       (result["production_id"],))
        assert len(jobs) == 2
        assert all(job["provider"] == "fake" and job["status"] == "succeeded"
                   for job in jobs)
        assert all(job["generation_intent_recorded"] == 0
                   and job["actual_vendor_charge_usd"] is None for job in jobs)
        assert {job["series_id"] for job in jobs} == {result["series_id"]}
    assert db.many("SELECT id FROM job_budget_reservations") == []


@needs_ffmpeg
def test_offline_worker_is_idempotent_and_reuses_video_cache(client, tmp_path):
    _, prod = ready_run(client, "Repeat")
    db = client.app.state.db
    initial = run_offline_production(db, prod, tmp_path)
    count = db.many("SELECT id,attempts FROM shot_jobs WHERE production_id=?", (prod,))
    rerun = run_offline_production(db, prod, tmp_path)
    assert rerun["shots_cached"] == 2
    assert rerun["mp4_sha256"] == initial["mp4_sha256"]
    assert db.many("SELECT id,attempts FROM shot_jobs WHERE production_id=?", (prod,)) == count
    assert all(job["attempts"] == 1 for job in db.many(
        "SELECT attempts FROM shot_jobs WHERE production_id=?", (prod,)))


def test_unapproved_production_cannot_start_fake_worker(client, tmp_path):
    _, prod = ready_run(client, "NeedsApproval", approve=False)
    with pytest.raises(ShotJobError, match="approval"):
        run_offline_production(client.app.state.db, prod, tmp_path)
    assert client.app.state.db.many("SELECT id FROM shot_jobs") == []


@needs_ffmpeg
def test_failed_render_is_isolated_and_can_be_manually_requeued(client, tmp_path, monkeypatch):
    _, prod = ready_run(client, "Recoverable")
    db = client.app.state.db
    import drama_factory.jobs.offline_worker as worker
    actual_render = worker.render_approved_preview
    def broken(*args, **kwargs):
        raise PreviewError("Synthetic injected renderer fault")
    monkeypatch.setattr(worker, "render_approved_preview", broken)
    with pytest.raises(PreviewError, match="fault"):
        run_offline_production(db, prod, tmp_path)
    jobs = db.many("SELECT * FROM shot_jobs WHERE production_id=?", (prod,))
    assert len(jobs) == 2
    assert {j["status"] for j in jobs} == {"failed"}
    assert all(j["provider_task_id"] is None
               and j["generation_intent_recorded"] == 0 for j in jobs)
    monkeypatch.setattr(worker, "render_approved_preview", actual_render)
    for job in jobs:
        assert restore_failed_job(db, job["id"], operator_reviewed=True)["status"] == "pending"
    assert run_offline_production(db, prod, tmp_path)["succeeded"] == 2
    assert {j["attempts"] for j in db.many(
        "SELECT attempts FROM shot_jobs WHERE production_id=?", (prod,))} == {2}


@needs_ffmpeg
def test_one_series_failure_does_not_cancel_the_other(client, tmp_path, monkeypatch):
    _, broken_run = ready_run(client, "Broken")
    _, healthy_run = ready_run(client, "Healthy")
    db = client.app.state.db
    import drama_factory.jobs.offline_worker as worker
    actual = worker.render_approved_preview
    def selectively_broken(database, production_id, root):
        if production_id == broken_run:
            raise PreviewError("Injected one-production failure")
        return actual(database, production_id, root)
    monkeypatch.setattr(worker, "render_approved_preview", selectively_broken)
    with pytest.raises(PreviewError, match="one-production"):
        run_offline_multi_series(db, [broken_run, healthy_run], tmp_path, max_workers=2)
    assert {row["status"] for row in db.many(
        "SELECT status FROM shot_jobs WHERE production_id=?", (broken_run,))} == {"failed"}
    assert {row["status"] for row in db.many(
        "SELECT status FROM shot_jobs WHERE production_id=?", (healthy_run,))} == {"succeeded"}


def test_no_fake_completion_of_real_provider_jobs(client, tmp_path):
    _, prod = ready_run(client, "NotFake")
    db = client.app.state.db
    jobs = prepare_shot_jobs(db, prod, provider="google")
    claimed = claim_next_job(db, "worker1", production_id=prod)
    with pytest.raises(ShotJobError, match="Fake-provider"):
        complete_fake_clip_job(db, claimed["id"], worker_id="worker1",
                               clip_path=tmp_path / "not-there.mp4")
    assert claimed["id"] in {j["id"] for j in jobs}


def test_duplicate_productions_or_excess_workers_are_rejected(client, tmp_path):
    _, prod = ready_run(client, "One")
    db = client.app.state.db
    with pytest.raises(OfflineWorkerError, match="unique"):
        run_offline_multi_series(db, [prod, prod], tmp_path)
    with pytest.raises(OfflineWorkerError, match="max_workers"):
        run_offline_multi_series(db, [prod], tmp_path, max_workers=9)
