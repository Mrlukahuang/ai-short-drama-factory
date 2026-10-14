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
                       duration_seconds: int = 6,
                       with_synthetic_audio_mix: bool = False,
                       with_fake_voice_timeline: bool = False,
                       with_fake_cast_timeline: bool = False) -> dict:
    """Approved-offline full pipeline: 6s smoke or 60s vertical technical sample.

    Both variants use synthetic tones/text placeholders, never paid AI media.
    """
    if type(duration_seconds) is not int or duration_seconds not in (6, 60):
        raise ValueError("Offline technical demo supports only 6s or 60s")
    if type(with_synthetic_audio_mix) is not bool:
        raise ValueError("Synthetic audio mix flag must be boolean")
    if type(with_fake_voice_timeline) is not bool:
        raise ValueError("Fake voice timeline flag must be boolean")
    if type(with_fake_cast_timeline) is not bool:
        raise ValueError("Fake cast timeline flag must be boolean")
    if sum((with_synthetic_audio_mix, with_fake_voice_timeline, with_fake_cast_timeline)) > 1:
        raise ValueError("Select only one synthetic audio demo mode")
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
        voice_asset_id = None
        if with_fake_voice_timeline or with_fake_cast_timeline:
            voice_asset_id = _post(client, f"/api/v1/series/{series}/assets", {
                "kind": "voice", "key": "test_lead_voice", "specification": {
                    "name": "Synthetic voice timeline test",
                    "voice_description": "Original non-speech sine-tone test only",
                    "source_consent_reference": "original-synthetic-test-tone-only",
                },
            })["asset_id"]
        actor_spec = {
            "name": "Fictional lead", "appearance": "Adult human",
            "identity_anchors": ["short dark hair"],
        }
        if voice_asset_id:
            actor_spec["voice_asset_id"] = voice_asset_id
        actor = _post(client, f"/api/v1/series/{series}/assets", {
            "kind": "actor", "key": "lead", "specification": actor_spec,
        })["asset_id"]
        other_actor = other_voice = None
        if with_fake_cast_timeline:
            other_voice = _post(client, f"/api/v1/series/{series}/assets", {
                "kind": "voice", "key": "test_second_voice", "specification": {
                    "name": "Original second synthetic test voice",
                    "voice_description": "Second non-speech sine timing tone",
                    "source_consent_reference": "original-second-synthetic-test-tone",
                },
            })["asset_id"]
            other_actor = _post(client, f"/api/v1/series/{series}/assets", {
                "kind": "actor", "key": "second_lead", "specification": {
                    "name": "Second fictional lead", "appearance": "Fictional adult",
                    "identity_anchors": ["long red scarf"], "voice_asset_id": other_voice,
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
                "camera": "medium",
                "character_ids": (
                    [actor, other_actor] if with_fake_cast_timeline and shot_id == "S001"
                    else [other_actor] if with_fake_cast_timeline and shot_id == "S002"
                    else [actor]
                ),
                "scene_id": scene,
                "dialogue": (
                    [
                        {"speaker_actor_id": actor, "text": line,
                         "start_second": 1 if seconds >= 4 else 0,
                         "end_second": seconds // 2},
                        {"speaker_actor_id": other_actor, "text": "You found me.",
                         "start_second": seconds // 2 + (1 if seconds >= 4 else 0),
                         "end_second": seconds - 1 if seconds >= 4 else seconds},
                    ]
                    if with_fake_cast_timeline and shot_id == "S001"
                    else [{
                        "speaker_actor_id": other_actor, "text": line,
                        "start_second": 2 if seconds >= 4 else 0,
                        "end_second": seconds - 1 if seconds >= 4 else 1,
                    }]
                    if with_fake_cast_timeline and shot_id == "S002"
                    else [] if with_fake_cast_timeline and shot_id == "S003"
                    else [{"speaker_actor_id": actor, "text": line}]
                ),
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
        # These waves are synthetic TIMING TEST TONES, not spoken voice,
        # licensed music, human likeness or a real TTS result.
        audio_args = {}
        if with_synthetic_audio_mix:
            stems = (
                ("dialogue_audio", "synthetic-dialogue-timing-tone.wav", 540),
                ("music_audio", "synthetic-background-timing-tone.wav", 180),
            )
            for label, filename, frequency in stems:
                wav = out / filename
                subprocess.run([
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i",
                    f"sine=frequency={frequency}:duration={duration_seconds}:sample_rate=48000",
                    "-ac", "1", "-c:a", "pcm_s16le", str(wav),
                ], capture_output=True, text=True, timeout=90, check=True)
                audio_args[label] = wav
            audio_args["operator_confirmed_audio_rights"] = True  # original synthetic tones only
        fake_timeline = None
        if with_fake_voice_timeline:
            from drama_factory.pipeline.offline_dialogue_timeline import (
                build_fake_episode_dialogue_timeline,
            )
            fake_timeline = build_fake_episode_dialogue_timeline(
                client.app.state.db, production, voice_asset_id,
                out / "fake-voice", operator_confirmed_voice_rights=True,
            )
            audio_args["dialogue_audio"] = Path(fake_timeline["local_wav_path"])
            background = out / "fake-voice-background-test-tone.wav"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"sine=frequency=180:duration={duration_seconds}:sample_rate=48000",
                "-ac", "1", "-c:a", "pcm_s16le", str(background),
            ], capture_output=True, text=True, timeout=90, check=True)
            audio_args["music_audio"] = background
            audio_args["operator_confirmed_audio_rights"] = True
        fake_cast = None
        if with_fake_cast_timeline:
            from drama_factory.pipeline.offline_cast_timeline import (
                build_fake_cast_dialogue_timeline,
            )
            fake_cast = build_fake_cast_dialogue_timeline(
                client.app.state.db, production,
                {actor: voice_asset_id, other_actor: other_voice},
                out / "fake-cast", operator_confirmed_voice_rights=True,
            )
            audio_args["dialogue_audio"] = Path(fake_cast["local_wav_path"])
            background = out / "fake-cast-background-test-tone.wav"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"sine=frequency=165:duration={duration_seconds}:sample_rate=48000",
                "-ac", "1", "-c:a", "pcm_s16le", str(background),
            ], capture_output=True, text=True, timeout=90, check=True)
            audio_args["music_audio"] = background
            audio_args["operator_confirmed_audio_rights"] = True
        result = render_approved_preview(
            client.app.state.db, production, out / "working",
            source_clips={"S002": test_footage}, **audio_args,
        )
        result["synthetic_test_tone_stems"] = bool(with_synthetic_audio_mix)
        result["fake_voice_timeline"] = bool(with_fake_voice_timeline)
        result["fake_voice_shots"] = len(fake_timeline["shots"]) if fake_timeline else 0
        result["fake_cast_timeline"] = bool(with_fake_cast_timeline)
        result["fake_cast_cues"] = fake_cast["cue_count"] if fake_cast else 0
        result["fake_cast_actors"] = fake_cast["speaking_actor_count"] if fake_cast else 0
        result["real_tts_generated"] = False
    shutil.copyfile(result["mp4_path"], out / "demo.mp4")
    (out / "manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Full offline MP4 demo (no AI video)")
    parser.add_argument("--out", type=Path, default=Path("artifacts/offline-demo"))
    parser.add_argument("--seconds", type=int, choices=(6, 60), default=6,
                        help="Build a 6-second smoke test or full 60-second vertical sample")
    parser.add_argument("--synthetic-audio-mix", action="store_true",
                        help="Add two original PCM timing TONES (not human voice or licensed music)")
    parser.add_argument("--fake-voice-timeline", action="store_true",
                        help="Compose individually approved FakeAudioProvider WAVs across all shots")
    parser.add_argument("--fake-cast-timeline", action="store_true",
                        help="Approved multi-actor, multi-cue original timing tones (NOT speech)")
    args = parser.parse_args(argv)
    manifest = build_offline_demo(
        args.out, duration_seconds=args.seconds,
        with_synthetic_audio_mix=args.synthetic_audio_mix,
        with_fake_voice_timeline=args.fake_voice_timeline,
        with_fake_cast_timeline=args.fake_cast_timeline,
    )
    print(json.dumps({
        "success": True, "preview_file": str(args.out / "demo.mp4"),
        "duration": manifest["media"]["duration_seconds"],
        "shots": len(manifest["shots"]), "paid_api_calls": 0,
        "placeholder_visuals": manifest["placeholder_visuals"],
        "supplied_local_clips": manifest["supplied_local_clips"],
        "synthetic_test_tone_stems": manifest["synthetic_test_tone_stems"],
        "fake_voice_timeline": manifest["fake_voice_timeline"],
        "fake_voice_shots": manifest["fake_voice_shots"],
        "fake_cast_timeline": manifest["fake_cast_timeline"],
        "fake_cast_cues": manifest["fake_cast_cues"],
        "fake_cast_actors": manifest["fake_cast_actors"],
        "real_tts_generated": False, "publish_approved": False,
    }))


if __name__ == "__main__":
    main()
