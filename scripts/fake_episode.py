"""AMEND-005 P6: ONE local Fake synopsis→MP4 CLI with stage JSON/hash resume.

No AI request; no real voice; no publication. The required explicit flag
permits only synthetic Fake records through the existing API approval gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from drama_factory.api import create_app
from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.fake_story_bible import build_fake_story_bible
from drama_factory.pipeline.fake_episode_screenplay import build_fake_episode_screenplay
from drama_factory.pipeline.fake_cast_assets import bind_fake_cast_assets
from drama_factory.pipeline.fake_shot_manifest import build_fake_shot_manifest
from drama_factory.pipeline.fake_episode_audio import build_fake_episode_audio
from drama_factory.pipeline.offline_render import inspect_mp4
from drama_factory.pipeline.offline_qa import inspect_offline_delivery, _verify_muxed_subtitles

STEPS = (
    "00_input", "01_story_bible", "02_episode_script", "03_screenplay",
    "04_assets", "05_shots", "06_dialogue", "07_subtitles", "08_music",
    "09_render", "10_qa",
)
SCHEMA = "fake-pipeline-stage.v1"


class FakePipelineError(ValueError):
    pass


def _hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha(path: Path) -> str:
    with path.open("rb") as f:
        h = hashlib.sha256()
        for part in iter(lambda: f.read(1024 * 1024), b""):
            h.update(part)
        return h.hexdigest()


def _json_bytes(obj: dict) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def _stage_file(folder: Path, name: str) -> Path:
    return folder / (name + ".json")


def _read_stage(folder: Path, step: str, source_sha: str,
                input_sha: str) -> dict | None:
    path = _stage_file(folder, step)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        return None
    try:
        doc = json.loads(path.read_text("utf-8"))
        if (doc.get("schema_version") != SCHEMA
                or doc.get("step") != step
                or doc.get("source_sha256") != source_sha
                or doc.get("input_sha256") != input_sha
                or doc.get("fake_only") is not True
                or doc.get("paid_provider_calls") != 0):
            return None
        payload = doc["payload"]
        if _hex(_json_bytes(payload)) != doc["payload_sha256"]:
            return None
        return payload
    except (ValueError, TypeError, KeyError, OSError, UnicodeError):
        return None


def _save_stage(folder: Path, step: str, source_sha: str,
                input_sha: str, payload: dict) -> None:
    path = _stage_file(folder, step)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise FakePipelineError("Unsafe stage JSON target")
    doc = {
        "schema_version": SCHEMA, "step": step,
        "source_sha256": source_sha, "input_sha256": input_sha,
        "payload_sha256": _hex(_json_bytes(payload)), "payload": payload,
        "fake_only": True, "paid_provider_calls": 0,
    }
    target = path.with_name("." + path.name + ".part")
    if target.is_symlink():
        raise FakePipelineError("Unsafe stage temporary target")
    target.write_bytes(_json_bytes(doc))
    target.replace(path)


def _response_json(response, *, expected: int) -> dict:
    if response.status_code != expected:
        raise FakePipelineError("Existing Fake API approval/commit path rejected request")
    return response.json()


def _local_demo_production(client: TestClient, db, series: str,
                           draft: EpisodeDraft, *, allow: bool) -> str:
    """Use existing TWO API approval transitions; never SQL-flip state."""
    if allow is not True:
        raise FakePipelineError("Explicit --acknowledge-fake-approvals required")
    row = db.one(
        "SELECT * FROM episodes WHERE project_id=? AND episode_number=?",
        (series, draft.episode_number),
    )
    if row is None:
        payload = _response_json(
            client.post(f"/api/v1/projects/{series}/episodes",
                        json=draft.model_dump(mode="json")), expected=201,
        )
        episode_id = payload["episode_id"]
    else:
        if EpisodeDraft.model_validate_json(row["body_json"]) != draft:
            raise FakePipelineError("Existing episode differs from Fake stage")
        episode_id = row["id"]
    productions = db.many(
        "SELECT id,status FROM productions WHERE episode_id=? ORDER BY id",
        (episode_id,),
    )
    if len(productions) > 1:
        raise FakePipelineError("Multiple local Fake Productions require inspection")
    if productions:
        pid, status = productions[0]["id"], productions[0]["status"]
    else:
        p = _response_json(
            client.post(f"/api/v1/episodes/{episode_id}/productions"),
            expected=201,
        )
        pid, status = p["production_id"], p["status"]
    if status == "script_review_pending":
        p = _response_json(
            client.post(f"/api/v1/productions/{pid}/approve-script"), expected=200,
        )
        status = p["status"]
    if status == "character_review_pending":
        p = _response_json(
            client.post(f"/api/v1/productions/{pid}/approve-characters"),
            expected=200,
        )
        status = p["status"]
    if status not in ("ready_for_video_generation", "offline_preview_finished"):
        raise FakePipelineError("Production not in approved Fake state")
    return pid


def run_fake_episode(source: Path, output_root: Path, *,
                     target_seconds: int = 60,
                     acknowledge_fake_approvals: bool = False,
                     rerun_from: str | None = None) -> dict:
    """Return final Fake QA manifest; write stages 00..10 to isolated directory.

    Re-running with identical source reuses hash-checked P4/P5 media. Explicit
    --rerun-from invalidates that stage and downstream; P4 may run existing
    worker again (its individual shot cache remains hash-gated).
    """
    if rerun_from is not None and rerun_from not in STEPS:
        raise FakePipelineError("Unknown stage name")
    if type(target_seconds) is not int or not 60 <= target_seconds <= 90:
        raise FakePipelineError("Fake episode must be 60–90 seconds")
    if acknowledge_fake_approvals is not True:
        raise FakePipelineError("Explicit Fake-only approval confirmation required")
    source = Path(source)
    if source.is_symlink() or not source.is_file():
        raise FakePipelineError("A regular local synopsis .txt is required")
    root = Path(output_root)
    if root.is_symlink():
        raise FakePipelineError("Linked Fake output directory denied")
    root.mkdir(parents=True, exist_ok=True)
    bible = build_fake_story_bible(source)  # validates UTF-8/size/rights boundary
    source_sha = bible["source_sha256"]
    run_id = f"fake-{source_sha[:20]}-{target_seconds}"
    folder = root / run_id
    if folder.is_symlink():
        raise FakePipelineError("Linked Fake run directory denied")
    folder.mkdir(parents=True, exist_ok=True)
    refresh = STEPS.index(rerun_from) if rerun_from else len(STEPS)

    # Stage 00–04: deterministic, no need for new persistence framework.
    zero = {
        "step": "00_input", "input_sha256": source_sha,
        "source_bytes": bible["source_bytes"],
        "fake_only": True, "paid_provider_calls": 0,
    }
    _save_stage(folder, "00_input", source_sha, source_sha, zero)
    _save_stage(folder, "01_story_bible", source_sha, source_sha, bible)
    script = build_fake_episode_screenplay(
        bible, target_duration_seconds=target_seconds,
    )
    _save_stage(folder, "02_episode_script", source_sha,
                _hex(_json_bytes(bible)), {
                    "step": "02_episode_script",
                    "script_outline": script["script_outline"],
                    "fake_only": True,
                })
    _save_stage(folder, "03_screenplay", source_sha,
                _hex(_json_bytes(script)), script)
    api_dir = root / "fake-api-local"
    # Offline HTTPX TestClient runs IN PROCESS; no port/network or Provider.
    with TestClient(create_app(api_dir)) as client:
        db = client.app.state.db
        assets = bind_fake_cast_assets(db, bible, script)
        _save_stage(folder, "04_assets", source_sha,
                    _hex(_json_bytes(script)), assets)
        draft = EpisodeDraft.model_validate(
            # use the same scoped/provisioned Screenplay schema
            __import__("drama_factory.pipeline.screenplay", fromlist=["Screenplay"])
            .Screenplay.model_validate(assets["screenplay"]).to_episode_draft()
        )
        pid = _local_demo_production(
            client, db, assets["series_id"], draft,
            allow=acknowledge_fake_approvals,
        )
        stage4_sha = _hex(_json_bytes(assets))
        media = root / "fake-renders"
        stage5 = None if refresh <= 5 else _read_stage(
            folder, "05_shots", source_sha, stage4_sha,
        )
        if stage5 is not None:
            p4mp4 = media / assets["series_id"] / pid / "preview.mp4"
            if (stage5.get("production_id") != pid or not p4mp4.is_file()
                    or p4mp4.is_symlink()
                    or _sha(p4mp4) != stage5.get("technical_episode_mp4_sha256")):
                stage5 = None
        if stage5 is None:
            stage5 = build_fake_shot_manifest(
                db, assets["series_id"], pid, media,
            )
        _save_stage(folder, "05_shots", source_sha, stage4_sha, stage5)

        stage5_sha = _hex(_json_bytes(stage5))
        arts = [None, None, None] if refresh <= 8 else [
            _read_stage(folder, step, source_sha, stage5_sha)
            for step in STEPS[6:9]
        ]
        audio_dir = folder / "audio"
        if all(x is not None for x in arts):
            a, s, m = arts
            checks = [
                (a["wav_name"], a["wav_sha256"]),
                (m["wav_name"], m["wav_sha256"]),
                (m["mixed_mp4_name"], m["mixed_mp4_sha256"]),
            ]
            if (any((audio_dir / name).is_symlink()
                    or not (audio_dir / name).is_file()
                    or _sha(audio_dir / name) != digest
                    for name, digest in checks)
                    or s["srt_sha256"] != _sha(
                        media / assets["series_id"] / pid / "captions.srt"
                    )):
                arts = [None, None, None]
        if any(x is None for x in arts):
            arts = list(build_fake_episode_audio(
                db, assets["series_id"], pid, stage5, media, audio_dir,
            ))
        for step, data in zip(STEPS[6:9], arts, strict=True):
            _save_stage(folder, step, source_sha, stage5_sha, data)

    a, s, m = arts
    music_sha = _hex(_json_bytes(m))
    final = folder / "episode.fake.mp4"
    previous = None if refresh <= 9 else _read_stage(
        folder, "09_render", source_sha, music_sha,
    )
    if (previous is None or final.is_symlink() or not final.is_file()
            or _sha(final) != previous.get("mp4_sha256")):
        if final.is_symlink():
            raise FakePipelineError("Unsafe output MP4 link")
        # P-final: bake a persistent, high-contrast disclosure into EVERY
        # video frame. A filename or JSON flag alone is not visible to viewers.
        # Reuse the existing audio+subtitle muxed file; no new AI/render model.
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-y", "-i", str(audio_dir / m["mixed_mp4_name"]),
            "-filter:v",
            "drawtext=text=FAKE ONLY - OFFLINE TECHNICAL PREVIEW:"
            "fontcolor=white:fontsize=20:box=1:boxcolor=black@0.72:"
            "boxborderw=10:x=10:y=h-th-16",
            "-map", "0:v:0", "-map", "0:a:0", "-map", "0:s:0",
            "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-c:s", "copy",
            "-movflags", "+faststart", str(final),
        ], check=True, capture_output=True, timeout=180)
        previous = {
            "step": "09_render", "fake_only": True, "video_source": "offline_placeholder_not_ai",
            "mp4_name": final.name, "mp4_sha256": _sha(final),
            "persistent_fake_watermark": "FAKE ONLY - OFFLINE TECHNICAL PREVIEW",
            "source_audio_sha256": m["mixed_mp4_sha256"],
            "duration_seconds": target_seconds,
            "paid_provider_calls": 0, "publish_approved": False,
        }
    _save_stage(folder, "09_render", source_sha, music_sha, previous)
    media_meta = inspect_mp4(final, target_seconds)
    if media_meta["subtitle_codec"] != "mov_text":
        raise FakePipelineError("Fake final MP4 lost subtitles")
    # Original reviewer+sidecar QA was already run inside P5; verify that
    # muxed captions in the final audio remix STILL match that same sidecar.
    original_srt = media / assets["series_id"] / pid / "captions.srt"
    if _verify_muxed_subtitles(final, original_srt) != len(s["subtitle_cues"]):
        raise FakePipelineError("Final muxed Fake subtitles do not match original")
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-xerror",
         "-i", str(final), "-map", "0:v:0", "-map", "0:a:0",
         "-f", "null", "-"],
        check=True, capture_output=True, timeout=90,
    )
    qa = {
        "step": "10_qa", "fake_only": True,
        "full_decode_passed": True, "subtitle_track_verified": True,
        "subtitle_cue_count": len(s["subtitle_cues"]),
        "duration_seconds": target_seconds,
        "mp4_sha256": _sha(final), "run_id": run_id,
        "paid_provider_calls": 0, "actual_fee_usd": None,
        "real_ai_video_verified": False, "real_speech_generated": False,
        "persistent_fake_watermark": previous["persistent_fake_watermark"],
        "human_review_required": True, "publish_approved": False,
    }
    _save_stage(folder, "10_qa", source_sha,
                _hex(_json_bytes(previous)), qa)
    return {"run_dir": str(folder), "mp4_path": str(final), **qa}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AMEND-005: offline FAKE synopsis to episode MP4")
    parser.add_argument("synopsis", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=60, choices=range(60, 91))
    parser.add_argument("--acknowledge-fake-approvals", action="store_true",
                        help="Use existing API review transitions for synthetic Fake demo only")
    parser.add_argument("--rerun-from", choices=STEPS, default=None)
    args = parser.parse_args(argv)
    try:
        result = run_fake_episode(
            args.synopsis, args.output_dir, target_seconds=args.duration,
            acknowledge_fake_approvals=args.acknowledge_fake_approvals,
            rerun_from=args.rerun_from,
        )
    except (FakePipelineError, ValueError, OSError, subprocess.SubprocessError) as e:
        parser.exit(2, f"FAKE pipeline stopped: {type(e).__name__}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
