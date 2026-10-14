"""Offline screenplay-to-playable-MP4 demo; run with: python -m drama_factory.pipeline.offline_demo."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from drama_factory.api import create_app
from drama_factory.pipeline.offline_render import render_approved_preview


def _post(client, path, body=None):
    response = client.post(path, json=body)
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Demo API rejected {path}: {response.status_code} {response.text}")
    return response.json()


def build_offline_demo(out: Path, *, source_override: Path | None = None,
                       duration_seconds: int = 6) -> dict:
    """Approved-offline full pipeline: 6s smoke or 60s vertical technical sample.

    Both variants use synthetic tones/text placeholders, never paid AI media.
    """
    if type(duration_seconds) is not int or duration_seconds not in (6, 60):
        raise ValueError("Offline technical demo supports only 6s or 60s")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    with TestClient(create_app(out / "data")) as client:
        col = _post(client, "/api/v1/columns", {
            "slug": "e2e-test", "name": "Offline end-to-end",
        })["column_id"]
        series = _post(client, f"/api/v1/columns/{col}/series", {
            "title": "One Minute Factory (test)",
            "premise": "Fictional characters meet at an apartment door.",
        })["series_id"]
        bible = _post(client, f"/api/v1/series/{series}/story-bibles", {
            "title": "Prototype test", "logline": "A mysterious knock changes a quiet evening.",
            "genre": "urban mystery",
        })["story_bible_id"]
        actor = _post(client, f"/api/v1/series/{series}/assets", {
            "kind": "actor", "key": "lead", "specification": {
                "name": "Fictional lead", "appearance": "Adult human",
                "identity_anchors": ["short dark hair"],
            },
        })["asset_id"]
        scene = _post(client, f"/api/v1/series/{series}/assets", {
            "kind": "scene", "key": "flat", "specification": {
                "name": "Apartment hallway", "location": "Apartment",
                "layout": "Front door opposite kitchen",
            },
        })["asset_id"]
        per_shot = duration_seconds // 3
        shots = [
            ("S001", per_shot, "The lead hears a knock.", "Who is there?"),
            ("S002", per_shot, "The lead walks to the door.", "Please wait."),
            ("S003", per_shot, "The door opens into darkness.", "What is this?"),
        ]
        script = {
            "series_id": series, "story_bible_id": bible, "episode_number": 1,
            "episode_title": "The Knock", "target_duration_seconds": duration_seconds,
            "hook": "A knock in the night", "ending_cliffhanger": "Who waits outside?",
            "shots": [{
                "shot_id": shot_id, "duration_seconds": seconds, "action": action,
                "camera": "medium", "character_ids": [actor], "scene_id": scene,
                "dialogue": [{"speaker_actor_id": actor, "text": line}],
                "continuity_start": "Lead facing hall",
                "continuity_end": "Lead near door",
            } for shot_id, seconds, action, line in shots],
        }
        validation = _post(client, f"/api/v1/series/{series}/screenplays/validate", script)
        if not validation["valid"] or not validation["review_required"]:
            raise RuntimeError("Expected screenplay review gate")
        approved = _post(client, f"/api/v1/series/{series}/screenplays/commit", {
            "screenplay": script, "reviewed_by_operator": True,
        })
        episode_id = approved["episode_id"]
        production = _post(client, f"/api/v1/episodes/{episode_id}/productions")["production_id"]
        _post(client, f"/api/v1/productions/{production}/approve-script")
        _post(client, f"/api/v1/productions/{production}/approve-characters")
        # A moving, locally generated clip stands in for a future Google/Kling/Seedance
        # download. No model is used; this deliberately tests external-media ingress.
        test_footage = Path(source_override) if source_override else out / "synthetic-moving-input.mp4"
        if source_override is None:
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24",
                "-t", str(per_shot), "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", str(test_footage),
            ], capture_output=True, text=True, timeout=90, check=True)
        result = render_approved_preview(
            client.app.state.db, production, out / "working",
            source_clips={"S002": test_footage},
        )
    shutil.copyfile(result["mp4_path"], out / "demo.mp4")
    (out / "manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Full offline MP4 demo (no AI video)")
    parser.add_argument("--out", type=Path, default=Path("artifacts/offline-demo"))
    parser.add_argument("--seconds", type=int, choices=(6, 60), default=6,
                        help="Build a 6-second smoke test or full 60-second vertical sample")
    args = parser.parse_args(argv)
    manifest = build_offline_demo(args.out, duration_seconds=args.seconds)
    print(json.dumps({
        "success": True, "preview_file": str(args.out / "demo.mp4"),
        "duration": manifest["media"]["duration_seconds"],
        "shots": len(manifest["shots"]), "paid_api_calls": 0,
        "placeholder_visuals": manifest["placeholder_visuals"],
        "supplied_local_clips": manifest["supplied_local_clips"],
    }))


if __name__ == "__main__":
    main()
