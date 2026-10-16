"""P-final artifact verifier: independent, read-only, fully local QA.

Checks the *actual* uploaded files, not a self-declared CI log.
No network access, secrets, data mutation, providers, or real model checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from drama_factory.pipeline.offline_render import inspect_mp4

STEPS = (
    "00_input", "01_story_bible", "02_episode_script", "03_screenplay",
    "04_assets", "05_shots", "06_dialogue", "07_subtitles", "08_music",
    "09_render", "10_qa",
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_artifact(folder: Path) -> dict:
    folder = Path(folder)
    media = folder / "episode.fake.mp4"
    marker = folder / "episode.sha256"
    stages = folder / "stages"
    if (folder.is_symlink() or media.is_symlink() or marker.is_symlink()
            or stages.is_symlink() or not stages.is_dir()):
        raise ValueError("Linked or missing Fake artifact")
    if not media.is_file() or not marker.is_file() or media.stat().st_size < 1000:
        raise ValueError("Fake artifact MP4 or SHA marker missing")
    digest = _sha(media)
    if marker.read_text("ascii").split()[0] != digest:
        raise ValueError("Fake artifact content SHA mismatch")
    documents = {}
    input_sha = None
    for step in STEPS:
        source = stages / (step + ".json")
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 1024 * 1024:
            raise ValueError("Missing or oversized Fake stage document")
        doc = json.loads(source.read_text("utf-8"))
        if (doc.get("schema_version") != "fake-pipeline-stage.v1"
                or doc.get("step") != step or doc.get("fake_only") is not True
                or doc.get("paid_provider_calls") != 0):
            raise ValueError("Invalid Fake stage envelope")
        payload = doc["payload"]
        canonical = (json.dumps(
            payload, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n").encode("utf-8")
        if hashlib.sha256(canonical).hexdigest() != doc["payload_sha256"]:
            raise ValueError("Fake stage payload has been modified")
        if input_sha is None:
            input_sha = doc["source_sha256"]
        elif input_sha != doc["source_sha256"]:
            raise ValueError("Cross-input stage files not permitted")
        documents[step] = payload
    output = documents["09_render"]
    qa = documents["10_qa"]
    if (output.get("mp4_sha256") != digest
            or output.get("persistent_fake_watermark")
            != "FAKE ONLY - OFFLINE TECHNICAL PREVIEW"
            or output.get("publish_approved") is not False
            or qa.get("mp4_sha256") != digest
            or qa.get("persistent_fake_watermark")
            != "FAKE ONLY - OFFLINE TECHNICAL PREVIEW"
            or qa.get("full_decode_passed") is not True
            or qa.get("subtitle_track_verified") is not True
            or qa.get("real_ai_video_verified") is not False
            or qa.get("real_speech_generated") is not False
            or qa.get("publish_approved") is not False
            or qa.get("paid_provider_calls") != 0):
        raise ValueError("Fake-only media/QA contract is not satisfied")
    metadata = inspect_mp4(media, 60)
    if (not 59.4 <= metadata["duration_seconds"] <= 60.6
            or metadata["width"] != 360 or metadata["height"] != 640
            or metadata["video_codec"] != "h264"
            or metadata["audio_codec"] != "aac"
            or metadata["subtitle_codec"] != "mov_text"):
        raise ValueError("Fake MP4 playback, duration, or codec contract failed")
    return {
        "fake_only": True, "mp4_sha256": digest, "stages_checked": len(STEPS),
        "duration_seconds": metadata["duration_seconds"],
        "technical_codec_qa_passed": True,
        "real_ai_video_verified": False, "paid_provider_calls": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify synthetic Fake MP4 CI artifact")
    parser.add_argument("artifact_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        proof = verify_artifact(args.artifact_dir)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        parser.exit(2, "Fake artifact verification failed\n")
    print(json.dumps(proof, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
