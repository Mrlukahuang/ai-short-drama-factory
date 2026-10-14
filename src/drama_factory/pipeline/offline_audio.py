"""PR-15b: bounded, local-only dialogue/music mix for an approved MP4.

Never downloads media, never calls TTS/video providers and NEVER grants voice
rights or permission to publish. Input PCM/WAV stems must be local regular
files. All errors are fixed messages without personal filenames or dialogue.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

_MAX_AUDIO_BYTES = 32 * 1024 * 1024
_PCM_CODECS = frozenset({"pcm_s16le", "pcm_s24le", "pcm_f32le"})


class OfflineAudioError(ValueError):
    """Fail closed, without leaking user audio paths or ffmpeg output."""


def inspect_local_wav(path: Path, *, target_seconds: int, kind: str) -> dict:
    if kind not in ("dialogue", "music") or type(target_seconds) is not int or not 1 <= target_seconds <= 90:
        raise OfflineAudioError("Invalid audio stem contract")
    try:
        file = Path(path)
        if file.is_symlink() or file.suffix.lower() != ".wav":
            raise OfflineAudioError("Only local regular WAV stems are allowed")
        source = file.resolve(strict=True)
        if not source.is_file() or not 44 <= source.stat().st_size <= _MAX_AUDIO_BYTES:
            raise OfflineAudioError("Audio stem outside size limit")
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,sample_rate,channels",
             "-of", "json", str(source)],
            check=True, capture_output=True, text=True, timeout=20,
        )
        meta = json.loads(probe.stdout)
        streams = meta["streams"]
        if len(streams) != 1 or streams[0]["codec_type"] != "audio":
            raise OfflineAudioError("Audio stem must have exactly one audio stream")
        stream = streams[0]
        if (
            stream.get("codec_name") not in _PCM_CODECS
            or not 16000 <= int(stream["sample_rate"]) <= 96000
            or int(stream["channels"]) not in (1, 2)
        ):
            raise OfflineAudioError("Unsupported WAV audio layout")
        seconds = float(meta["format"]["duration"])
        if not (0.1 <= seconds <= 600):
            raise OfflineAudioError("Audio duration outside safe range")
        if kind == "dialogue" and seconds > target_seconds + 0.25:
            raise OfflineAudioError("Dialogue exceeds episode duration")
        if kind == "music" and seconds < target_seconds - 0.15:
            raise OfflineAudioError("Music must cover episode duration")
        sha = hashlib.sha256()
        with source.open("rb") as stream_file:
            for block in iter(lambda: stream_file.read(1024 * 1024), b""):
                sha.update(block)
        return {
            "path": source,
            "sha256": sha.hexdigest(),
            "duration_seconds": seconds,
            "kind": kind,
        }
    except OfflineAudioError:
        raise
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError):
        raise OfflineAudioError("Local WAV stem validation failed") from None


def mix_local_stems(
    source_mp4: Path, output_mp4: Path, *,
    duration_seconds: int,
    dialogue: dict | None = None,
    music: dict | None = None,
) -> dict:
    """Create a single AAC mix while copying original H.264 and mov_text.

    When dialogue is supplied, it replaces the source track (prevents mixing
    a potentially already-voiced Provider clip twice). Music is attenuated
    underneath dialogue; absent dialogue the original source audio is kept.
    The caller is responsible for QA and publishing the result atomically.
    """
    if type(duration_seconds) is not int or not 1 <= duration_seconds <= 90:
        raise OfflineAudioError("Invalid episode audio duration")
    if dialogue is None and music is None:
        raise OfflineAudioError("At least one local WAV stem is required")
    try:
        source = Path(source_mp4).resolve(strict=True)
        target = Path(output_mp4)
        if target.is_symlink() or source == target.resolve():
            raise OfflineAudioError("Audio mix must use a separate output file")
        from drama_factory.pipeline.offline_render import inspect_mp4

        inspected = inspect_mp4(source, duration_seconds)
        if inspected["subtitle_codec"] != "mov_text":
            raise OfflineAudioError("Source MP4 has no approved subtitle track")
        for entry, kind in ((dialogue, "dialogue"), (music, "music")):
            if entry is not None:
                if type(entry) is not dict or entry.get("kind") != kind:
                    raise OfflineAudioError("Invalid prepared audio stem")
                reread = inspect_local_wav(
                    entry["path"], target_seconds=duration_seconds, kind=kind
                )
                if reread["sha256"] != entry.get("sha256"):
                    raise OfflineAudioError("Audio stem changed after inspection")

        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
               "-nostdin", "-y", "-i", str(source)]
        if dialogue is not None:
            cmd += ["-i", str(dialogue["path"])]
        if music is not None:
            cmd += ["-i", str(music["path"])]
        speech_input = "1:a:0" if dialogue is not None else "0:a:0"
        nodes = [
            f"[{speech_input}]aresample=48000,apad,atrim=0:{duration_seconds},volume=1.0[speech]"
        ]
        if music is not None:
            idx = 2 if dialogue is not None else 1
            nodes.append(
                f"[{idx}:a:0]aresample=48000,atrim=0:{duration_seconds},volume=0.16[music]"
            )
            nodes.append(
                "[speech][music]amix=inputs=2:duration=first:"
                "dropout_transition=0,alimiter=limit=0.92[mixed]"
            )
        else:
            nodes.append("[speech]anull[mixed]")
        cmd += [
            "-filter_complex", ";".join(nodes),
            "-map", "0:v:0", "-map", "[mixed]", "-map", "0:s:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-c:s", "copy", "-t", str(duration_seconds),
            "-movflags", "+faststart", str(target),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        result = inspect_mp4(target, duration_seconds)
        if result["subtitle_codec"] != "mov_text":
            raise OfflineAudioError("Mixed MP4 lost subtitle track")
        return {
            "locally_supplied_dialogue": dialogue is not None,
            "locally_supplied_music": music is not None,
            "dialogue_sha256": dialogue["sha256"] if dialogue else None,
            "music_sha256": music["sha256"] if music else None,
            "output_audio_codec": "aac",
            "subtitle_track_preserved": True,
            "voice_license_independently_verified": False,
            "real_tts_generated": False,
            "published": False,
            "paid_provider_calls": 0,
        }
    except OfflineAudioError:
        raise
    except (OSError, KeyError, ValueError, TypeError, subprocess.SubprocessError):
        raise OfflineAudioError("Local audio mixing failed; no delivery authorized") from None
