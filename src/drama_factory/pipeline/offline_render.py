"""End-to-end OFFLINE episode rendering: approved Episode -> reusable clips -> MP4.

This deliberately makes text-only placeholder cards and synthetic tones, NOT AI video
or real dialogue. No network access, model keys or paid providers are used.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from drama_factory.db import Database, timestamp
from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.media_ingest import inspect_source, normalize_local_video

WIDTH, HEIGHT, FPS = 360, 640, 15
RENDER_REVISION = "offline-card-v1"
MAX_SHOTS, MAX_SECONDS = 12, 90


class PreviewError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path | None = None) -> str:
    process = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=180)
    if process.returncode:
        raise PreviewError(f"{Path(args[0]).name} failed: {process.stderr[-1400:]}")
    return process.stdout


def inspect_mp4(path: Path, expected_duration: int | None = None) -> dict:
    if not path.is_file() or path.stat().st_size < 1000:
        raise PreviewError("Missing or empty playable MP4")
    info = json.loads(_run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height",
        "-of", "json", str(path),
    ]))
    video = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    audio = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    subtitle = [s for s in info.get("streams", []) if s.get("codec_type") == "subtitle"]
    if len(video) != 1 or len(audio) != 1:
        raise PreviewError("MP4 must have exactly one video and one audio stream")
    if (video[0].get("codec_name") != "h264" or video[0].get("width") != WIDTH
            or video[0].get("height") != HEIGHT or audio[0].get("codec_name") != "aac"):
        raise PreviewError("MP4 codec or resolution mismatch")
    duration = float(info["format"]["duration"])
    if expected_duration is not None and abs(duration - expected_duration) > 0.6:
        raise PreviewError(f"MP4 duration {duration}s != expected {expected_duration}s")
    if subtitle and (len(subtitle) != 1 or subtitle[0].get("codec_name") != "mov_text"):
        raise PreviewError("Unsupported subtitle track")
    return {"duration_seconds": duration, "video_codec": "h264",
            "audio_codec": "aac", "subtitle_codec": "mov_text" if subtitle else None,
            "width": WIDTH, "height": HEIGHT}


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as content:
        for chunk in iter(lambda: content.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clip_digest_path(clip: Path) -> Path:
    return clip.with_name(clip.name + ".sha256")


def _cache_has_expected_content(clip: Path) -> bool:
    """Only reuse a playable clip if our separately recorded content matches.

    This detects accidental edits/replacement, not a malicious attacker who
    can rewrite both the cache and its local digest. Never claim signatures.
    Older clips lacking digests are safely re-rendered once.
    """
    marker = _clip_digest_path(clip)
    if clip.is_symlink() or marker.is_symlink() or not marker.is_file():
        return False
    try:
        expected = marker.read_text(encoding="ascii").strip()
        return bool(re.fullmatch(r"[a-f0-9]{64}", expected)) and _file_sha256(clip) == expected
    except (OSError, UnicodeError, ValueError):
        return False


def _write_clip_digest(clip: Path, digest: str) -> None:
    """Atomically publish a bounded hash marker next to a verified clip."""
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise PreviewError("Invalid local clip content hash")
    marker = _clip_digest_path(clip)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="ascii", dir=clip.parent,
            prefix=".clip-integrity-", suffix=".tmp", delete=False,
        ) as handle:
            tmp = Path(handle.name)
            handle.write(digest + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(marker)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def _card(path: Path, shot, number: int, total: int) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), (16, 25, 40))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 22)
        small = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.rounded_rectangle((18, 24, WIDTH - 18, HEIGHT - 24),
                           radius=18, outline=(58, 111, 164), width=3)
    draw.text((38, 60), "OFFLINE VIDEO PREVIEW", font=small, fill=(115, 201, 255))
    draw.text((38, 110), f"SHOT {number} / {total}", font=font, fill="white")
    draw.line((38, 160, WIDTH - 38, 160), fill=(58, 111, 164), width=2)
    draw.text((38, 190), f"Duration: {shot.duration_seconds}s", font=small, fill="white")
    draw.text((38, 225), f"Actors: {len(shot.character_ids)}", font=small, fill="white")
    draw.text((38, 300), "Text storyboard placeholder", font=small, fill=(212, 223, 234))
    draw.text((38, 330), "Not generated live footage", font=small, fill=(212, 223, 234))
    draw.text((38, HEIGHT - 115), "Synthetic tone / no voice", font=small, fill=(115, 201, 255))
    draw.text((38, HEIGHT - 85), "Paid AI calls: 0", font=small, fill="white")
    image.save(path, "PNG")


def _shot_key(series_id: str, episode_id: str, shot, source_sha256: str | None = None) -> str:
    payload = json.dumps({
        "revision": RENDER_REVISION, "series": series_id, "episode": episode_id,
        "shot": shot.model_dump(mode="json"), "source_sha256": source_sha256,
        "width": WIDTH, "height": HEIGHT,
        "fps": FPS,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _srt_time(seconds: int) -> str:
    hours, remain = divmod(seconds, 3600)
    minutes, secs = divmod(remain, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


def render_approved_preview(db: Database, production_id: str, root: Path, *,
                            source_clips: dict[str, Path] | None = None,
                            dialogue_audio: Path | None = None,
                            music_audio: Path | None = None,
                            operator_confirmed_audio_rights: bool = False) -> dict:
    """Render a playable offline preview only after the existing two approvals."""
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise PreviewError("ffmpeg and ffprobe must be installed")
    record = db.one(
        """SELECT p.id,p.status,e.id AS episode_id,e.project_id,e.body_json
        FROM productions p JOIN episodes e ON p.episode_id=e.id WHERE p.id=?""",
        (production_id,),
    )
    if record is None:
        raise PreviewError("Unknown production ID")
    if record["status"] not in ("ready_for_video_generation", "offline_preview_finished"):
        raise PreviewError("Script and character approvals are required before rendering")
    episode = EpisodeDraft.model_validate_json(record["body_json"])
    if len(episode.shots) > MAX_SHOTS or episode.target_duration_seconds > MAX_SECONDS:
        raise PreviewError("Offline preview limited to 12 shots and 90 seconds")
    if sum(s.duration_seconds for s in episode.shots) != episode.target_duration_seconds:
        raise PreviewError("Shot durations do not match episode target duration")
    series_id = record["project_id"]
    for shot in episode.shots:
        for asset_id, kind in [
            *[(a, "actor") for a in shot.character_ids],
            *([(shot.scene_id, "scene")] if shot.scene_id else []),
        ]:
            if db.one("SELECT id FROM series_assets WHERE id=? AND series_id=? AND kind=?",
                      (asset_id, series_id, kind)) is None:
                raise PreviewError("Foreign actor or scene reference in episode")
    source_clips = source_clips or {}
    unknown_shots = set(source_clips) - {s.shot_id for s in episode.shots}
    if unknown_shots:
        raise PreviewError("Source clips reference unknown shot IDs")
    # Inspect every input before writing output or changing the production status.
    sources = {shot_id: inspect_source(path, next(
        shot.duration_seconds for shot in episode.shots if shot.shot_id == shot_id))
        for shot_id, path in source_clips.items()}
    # Validate local audio stems and explicit self-attested rights BEFORE
    # output writes. An attestation never means legal/voice rights verified.
    dialogue_stem = music_stem = None
    if dialogue_audio is not None or music_audio is not None:
        from drama_factory.pipeline.offline_audio import inspect_local_wav
        if operator_confirmed_audio_rights is not True:
            raise PreviewError("Local audio rights attestation required before mixing")
        if dialogue_audio is not None:
            dialogue_stem = inspect_local_wav(
                dialogue_audio, target_seconds=episode.target_duration_seconds,
                kind="dialogue",
            )
        if music_audio is not None:
            music_stem = inspect_local_wav(
                music_audio, target_seconds=episode.target_duration_seconds,
                kind="music",
            )
    root = Path(root).resolve()
    work = root / series_id / production_id
    clips_dir = work / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips, shot_results, captions = [], [], []
    subtitle_schedule = []
    subtitle_at = 0
    for index, shot in enumerate(episode.shots, start=1):
        media_source = sources.get(shot.shot_id)
        key = _shot_key(series_id, record["episode_id"], shot,
                        media_source["sha256"] if media_source else None)
        name = f"{index:03d}_{key[:24]}.mp4"
        clip = clips_dir / name
        reused = False
        if clip.is_file() and _cache_has_expected_content(clip):
            try:
                inspect_mp4(clip, shot.duration_seconds)
                reused = True
            except (PreviewError, ValueError, KeyError, subprocess.TimeoutExpired):
                reused = False
        if not reused:
            # A cache without its own verified digest is untrusted even if
            # ffprobe reports a playable, correctly timed H.264 clip.
            clip.unlink(missing_ok=True)
            _clip_digest_path(clip).unlink(missing_ok=True)
        if not reused:
            card = clips_dir / f"{index:03d}_{key[:24]}.png"
            temp_clip = clips_dir / f"{name}.tmp.mp4"
            try:
                if media_source:
                    normalize_local_video(media_source, shot.duration_seconds, temp_clip,
                                          width=WIDTH, height=HEIGHT, fps=FPS)
                else:
                    _card(card, shot, index, len(episode.shots))
                    _run([
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-loop", "1", "-framerate", str(FPS), "-i", str(card),
                        "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000",
                        "-t", str(shot.duration_seconds), "-vf", "format=yuv420p",
                        "-c:v", "libx264", "-preset", "ultrafast", "-r", str(FPS),
                        "-c:a", "aac", "-ar", "48000", "-ac", "1", "-af", "volume=0.02",
                        "-movflags", "+faststart", str(temp_clip),
                    ])
                inspect_mp4(temp_clip, shot.duration_seconds)
                temp_clip.replace(clip)
                _write_clip_digest(clip, _file_sha256(clip))
            finally:
                card.unlink(missing_ok=True)
                temp_clip.unlink(missing_ok=True)
        clips.append(clip)
        # Preserve approved SPEAKER cue order and optional director-approved
        # timing. The old one-subtitle-per-shot layout made text appear
        # throughout pauses even after the voice timeline became cue-aware.
        slots = []
        if shot.dialogue_cues:
            count = len(shot.dialogue_cues)
            if shot.dialogue_cues[0].start_second is not None:
                slots = [
                    (line.start_second, line.end_second,
                     f"{line.speaker_actor_id}: {line.text}")
                    for line in shot.dialogue_cues
                ]
            else:
                cursor = 0
                for i, line in enumerate(shot.dialogue_cues):
                    length = shot.duration_seconds // count + (
                        1 if i < shot.duration_seconds % count else 0
                    )
                    slots.append((
                        cursor, cursor + length,
                        f"{line.speaker_actor_id}: {line.text}",
                    ))
                    cursor += length
        else:
            # Legacy v0.1 plain dialogue and silent technical cards remain
            # compatible. No speaker identity is inferred from raw strings.
            subtitle = " / ".join(shot.dialogue) if shot.dialogue else "[OFFLINE PREVIEW: NO SPOKEN DIALOGUE]"
            slots = [(0, shot.duration_seconds, subtitle)]
        for start, end, raw_text in slots:
            subtitle = " ".join(raw_text.split())[:300]
            if not subtitle or end <= start or end > shot.duration_seconds:
                raise PreviewError("Invalid approved subtitle cue schedule")
            absolute_start, absolute_end = subtitle_at + start, subtitle_at + end
            subtitle_schedule.append({
                "start_second": absolute_start,
                "end_second": absolute_end,
                "text_sha256": hashlib.sha256(subtitle.encode("utf-8")).hexdigest(),
            })
            captions.append(
                f"{len(captions) + 1}\n{_srt_time(absolute_start)} --> {_srt_time(absolute_end)}\n"
                f"{subtitle}\n\n"
            )
        subtitle_at += shot.duration_seconds
        shot_results.append({"shot_id": shot.shot_id, "fingerprint": key,
                             "cached": reused, "clip_name": name,
                             "clip_sha256": _file_sha256(clip),
                             "media_source": "provided_local_clip" if media_source else "placeholder",
                             "source_sha256": media_source["sha256"] if media_source else None,
                             "duration_seconds": shot.duration_seconds})
    # The concat list is constructed ONLY from our deterministic hash-based filenames.
    playlist = work / "clips.txt"
    playlist.write_text("".join(f"file 'clips/{p.name}'\n" for p in clips), encoding="utf-8")
    subtitles_path = work / "captions.srt"
    subtitles_path.write_text("".join(captions), encoding="utf-8")
    final = work / "preview.mp4"
    temp_final = work / "preview.part.mp4"
    temp_mixed = work / "preview.audio.part.mp4"
    audio_mix = None
    try:
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
              "-f", "concat", "-safe", "0", "-i", str(playlist),
              "-i", str(subtitles_path),
              "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
              "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
              "-movflags", "+faststart", str(temp_final)])
        media = inspect_mp4(temp_final, episode.target_duration_seconds)
        if media["subtitle_codec"] != "mov_text":
            raise PreviewError("Final MP4 missing dialogue subtitle track")
        if dialogue_stem is not None or music_stem is not None:
            from drama_factory.pipeline.offline_audio import mix_local_stems
            audio_mix = mix_local_stems(
                temp_final, temp_mixed,
                duration_seconds=episode.target_duration_seconds,
                dialogue=dialogue_stem, music=music_stem,
            )
            # The mixed file has the same verified subtitle and H264 layout;
            # replacing only the final output keeps shot cache keys intact.
            temp_mixed.replace(temp_final)
            media = inspect_mp4(temp_final, episode.target_duration_seconds)
        temp_final.replace(final)
    finally:
        temp_final.unlink(missing_ok=True)
        temp_mixed.unlink(missing_ok=True)
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    manifest = {
        "production_id": production_id, "series_id": series_id,
        "episode_id": record["episode_id"], "status": "offline_preview_finished",
        "placeholder_visuals": any(s["media_source"] == "placeholder" for s in shot_results),
        "supplied_local_clips": len(sources),
        "spoken_dialogue_generated": False,
        "synthetic_tone_audio": (dialogue_stem is None and
                                 any(s["media_source"] == "placeholder" for s in shot_results)),
        "local_dialogue_audio_supplied": dialogue_stem is not None,
        "local_music_audio_supplied": music_stem is not None,
        "audio_rights_self_attested": (
            operator_confirmed_audio_rights is True
            and (dialogue_stem is not None or music_stem is not None)
        ),
        "voice_license_independently_verified": False,
        "offline_audio_mix": audio_mix,
        "has_subtitle_track": True,
        "subtitle_schedule": subtitle_schedule,
        "paid_api_calls": 0,
        "mp4_path": str(final), "mp4_sha256": digest, "media": media,
        "shots": shot_results,
    }
    # Fail closed: independent READ-ONLY technical QA must pass BEFORE any
    # production state or delivery manifest is marked preview-finished. This
    # verifies full audio/video decode, SHA256 and shot-aligned SRT timing.
    # Import locally to avoid a module import cycle: QA reuses inspect_mp4.
    from drama_factory.pipeline.offline_qa import (
        OfflineQAError, inspect_offline_delivery,
    )
    try:
        manifest["technical_qa"] = inspect_offline_delivery(manifest, final)
    except OfflineQAError:
        raise PreviewError(
            "Generated MP4 failed technical QA; production status unchanged"
        ) from None
    # A passing technical preview is NEVER a production or publication approval.
    assert manifest["technical_qa"]["publish_approved"] is False
    assert manifest["technical_qa"]["production_ready"] is False
    # Metadata is saved only after a real decoded MP4 and subtitle QA pass.
    db.exec(
        """UPDATE productions SET status=?,result_json=?,updated_at=? WHERE id=?""",
        ("offline_preview_finished", json.dumps(manifest, ensure_ascii=False),
         timestamp(), production_id),
    )
    (work / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return manifest
