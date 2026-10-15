"""AMEND-005 P4: one Fake shot-job result manifest from existing worker.

NO new renderer/provider/retry framework: reuse the existing approved offline
worker, shot ledger and FFmpeg. This adapter merely binds each completed Fake
clip to its immutable asset versions and existing result digests.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from drama_factory.db import Database
from drama_factory.jobs.offline_worker import run_offline_production
from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.offline_render import inspect_mp4


class FakeShotManifestError(ValueError):
    pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_fake_shot_manifest(
    db: Database, series_id: str, production_id: str, media_root: Path,
) -> dict:
    """Render with the existing Fake worker, then verify each scoped shot.

    Requires the existing two normal production approvals. This method never
    approves anyone or calls a paid model.
    """
    production = db.one(
        """SELECT e.project_id,e.body_json,e.id AS episode_id
           FROM productions p JOIN episodes e ON p.episode_id=e.id WHERE p.id=?""",
        (production_id,),
    )
    if production is None or production["project_id"] != series_id:
        raise FakeShotManifestError("Production does not belong to this series")
    draft = EpisodeDraft.model_validate_json(production["body_json"])
    expected = {shot.shot_id: shot for shot in draft.shots}
    if not 1 <= len(expected) <= 12 or not 1 <= draft.target_duration_seconds <= 90:
        raise FakeShotManifestError("Fake preview exceeds local shot/time limits")
    # Worker refuses unapproved Productions, non-Fake jobs, mismatched provider
    # sources and every implicit retry. No second worker is introduced.
    result = run_offline_production(db, production_id, media_root)
    rows = db.many(
        "SELECT * FROM shot_jobs WHERE production_id=? ORDER BY shot_id",
        (production_id,),
    )
    if len(rows) != len(expected) or {x["shot_id"] for x in rows} != set(expected):
        raise FakeShotManifestError("Completed Fake shot jobs do not match episode")
    clips: list[dict] = []
    for job in rows:
        if (
            job["status"] != "succeeded" or job["provider"] != "fake"
            or job["generation_intent_recorded"] != 0
            or job["actual_vendor_charge_usd"] is not None
            or not job["result_path"] or not job["result_sha256"]
        ):
            raise FakeShotManifestError("Only completed zero-cost Fake jobs are eligible")
        path = Path(job["result_path"])
        if (
            path.is_symlink() or not path.is_file() or path.suffix.lower() != ".mp4"
            or path.parent.name != "clips"
            or path.parents[1].name != production_id
            or path.parents[2].name != series_id
        ):
            raise FakeShotManifestError("Fake clip is missing from its scope directory")
        if _sha(path) != job["result_sha256"]:
            raise FakeShotManifestError("Fake shot clip digest changed")
        shot = expected[job["shot_id"]]
        inspect_mp4(path, shot.duration_seconds)
        refs: list[dict] = []
        pairs = [(actor, "actor") for actor in shot.character_ids]
        if shot.scene_id:
            pairs.append((shot.scene_id, "scene"))
        for aid, kind in pairs:
            asset = db.one(
                """SELECT version,specification_json FROM series_assets
                   WHERE id=? AND series_id=? AND kind=?""",
                (aid, series_id, kind),
            )
            if asset is None:
                raise FakeShotManifestError("A shot lost its scoped Fake asset version")
            refs.append({
                "asset_id": aid,
                "kind": kind,
                "version": asset["version"],
                "specification_sha256": hashlib.sha256(
                    asset["specification_json"].encode("utf-8")
                ).hexdigest(),
            })
        clips.append({
            "shot_id": shot.shot_id,
            "duration_seconds": shot.duration_seconds,
            "input_sha256": job["input_sha256"],
            "idempotency_key": job["idempotency_key"],
            "result_sha256": job["result_sha256"],
            "clip_name": path.name,
            "video_source": "offline_placeholder_not_ai",
            "provider": "fake",
            "model_calls": 0,
            "asset_versions": refs,
        })
    mp4 = Path(result["mp4_path"])
    if mp4.is_symlink() or not mp4.is_file() or _sha(mp4) != result["mp4_sha256"]:
        raise FakeShotManifestError("Episode technical MP4 missing or tampered")
    return {
        "schema_version": "fake-shot-results.zh.v1",
        "step": "05_shots",
        "series_id": series_id,
        "production_id": production_id,
        "episode_id": production["episode_id"],
        "fake_only": True,
        "approved_real_content": False,
        "real_ai_video": False,
        "paid_provider_calls": 0,
        "actual_fee_usd": None,
        "shots_cached": result["shots_cached"],
        "shot_count": len(clips),
        "shots": clips,
        "technical_episode_mp4_sha256": result["mp4_sha256"],
    }
