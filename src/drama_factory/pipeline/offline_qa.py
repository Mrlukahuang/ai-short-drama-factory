"""PR-14a: deterministic, READ-ONLY local episode preview quality gate.

Never invokes a paid provider, edits a production, authorizes publication or
claims that placeholder visuals / synthetic tones are real AI footage.
A successful technical check ALWAYS requires separate operator approval.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from drama_factory.pipeline.offline_render import PreviewError, inspect_mp4

_MAX_BYTES = 200 * 1024 * 1024
_MAX_SHOTS = 12
_MAX_SECONDS = 90
_TIMESTAMP = re.compile(r"([0-9]{2}):([0-9]{2}):([0-9]{2}),([0-9]{3})\Z")
_TIMING = re.compile(r"([^ ]+) --> ([^ ]+)\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")


class OfflineQAError(ValueError):
    """Fixed safe error: no asset paths, subtitle text or private content."""


def _stamp(raw: str) -> int:
    m = _TIMESTAMP.fullmatch(raw)
    if m is None:
        raise OfflineQAError("Invalid subtitle timestamp format")
    hours, minutes, seconds, ms = (int(x) for x in m.groups())
    if minutes > 59 or seconds > 59:
        raise OfflineQAError("Subtitle timestamp out of bounds")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + ms


def _validate_srt(sidecar: Path, durations: list[int]) -> None:
    try:
        if sidecar.is_symlink() or not sidecar.is_file() or sidecar.stat().st_size > 128 * 1024:
            raise OfflineQAError("Missing or unsafe subtitle sidecar")
        source = sidecar.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        raise OfflineQAError("Unreadable subtitle sidecar") from None
    cues = re.split(r"\r?\n\s*\r?\n", source.strip())
    if len(cues) != len(durations):
        raise OfflineQAError("Subtitle cue count mismatch")
    cursor = 0
    for index, (cue, duration) in enumerate(zip(cues, durations, strict=True), start=1):
        lines = cue.splitlines()
        if len(lines) < 3 or lines[0].strip() != str(index):
            raise OfflineQAError("Subtitle cue numbering invalid")
        match = _TIMING.fullmatch(lines[1].strip())
        if match is None:
            raise OfflineQAError("Subtitle timing line invalid")
        begin, finish = (_stamp(match.group(1)), _stamp(match.group(2)))
        if begin != cursor or finish != cursor + duration * 1000 or not any(x.strip() for x in lines[2:]):
            raise OfflineQAError("Subtitle gaps, overlaps or missing text")
        cursor = finish


def _decode_all_streams(path: Path) -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror",
             "-nostdin", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0",
             "-f", "null", "-"],
            check=True, capture_output=True, timeout=90,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        raise OfflineQAError("Video/audio full decode did not pass") from None


def inspect_offline_delivery(manifest: dict, media_path: Path, *,
                             require_real_footage: bool = False) -> dict:
    """Technical quality evidence for the exact file and immutable manifest.

    Does not modify MP4, captions, manifest or database. Return redacted
    booleans; no dialogue text, source paths, character identities or hashes.
    """
    if type(manifest) is not dict:
        raise OfflineQAError("Invalid preview manifest")
    try:
        media = Path(media_path)
        if media.is_symlink():
            raise OfflineQAError("Symlinked video asset not supported")
        file = media.resolve(strict=True)
        if not file.is_file() or file.suffix.lower() != ".mp4":
            raise OfflineQAError("Expected existing MP4 file")
        size = file.stat().st_size
        if not 1000 <= size <= _MAX_BYTES:
            raise OfflineQAError("Video file outside safe byte bounds")
        declared = Path(manifest["mp4_path"]).resolve(strict=True)
        if declared != file:
            raise OfflineQAError("MP4 does not belong to supplied manifest")
        digest = manifest["mp4_sha256"]
        if type(digest) is not str or not _DIGEST.fullmatch(digest):
            raise OfflineQAError("Invalid manifest video hash")
        shots = manifest["shots"]
        if type(shots) is not list or not (1 <= len(shots) <= _MAX_SHOTS):
            raise OfflineQAError("Invalid number of preview shots")
        shot_ids, durations = [], []
        for shot in shots:
            if type(shot) is not dict:
                raise OfflineQAError("Malformed shot metadata")
            shot_id, length = shot["shot_id"], shot["duration_seconds"]
            if type(shot_id) is not str or not shot_id or type(length) is not int or not 1 <= length <= 30:
                raise OfflineQAError("Invalid shot identifier or duration")
            shot_ids.append(shot_id)
            durations.append(length)
            if shot["media_source"] not in ("placeholder", "provided_local_clip"):
                raise OfflineQAError("Unknown preview media source")
            clip_name, clip_digest = shot["clip_name"], shot["clip_sha256"]
            if (
                type(clip_name) is not str
                or re.fullmatch(r"[0-9]{3}_[a-f0-9]{24}\\.mp4", clip_name) is None
                or type(clip_digest) is not str
                or _DIGEST.fullmatch(clip_digest) is None
            ):
                raise OfflineQAError("Missing or unsafe clip integrity metadata")
            local_clip = file.parent / "clips" / clip_name
            if local_clip.is_symlink() or not local_clip.is_file():
                raise OfflineQAError("Missing or symlinked local clip")
            clip_hash = hashlib.sha256()
            with local_clip.open("rb") as clip_data:
                for chunk in iter(lambda: clip_data.read(1024 * 1024), b""):
                    clip_hash.update(chunk)
            if clip_hash.hexdigest() != clip_digest:
                raise OfflineQAError("Local clip no longer matches delivery manifest")
        if len(set(shot_ids)) != len(shot_ids):
            raise OfflineQAError("Duplicate shot identifiers")
        total = sum(durations)
        if total > _MAX_SECONDS:
            raise OfflineQAError("Preview duration outside safe bounds")
        computed = hashlib.sha256()
        with file.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                computed.update(chunk)
        if computed.hexdigest() != digest:
            raise OfflineQAError("Video content hash mismatch")
        info = inspect_mp4(file, total)
        if info["subtitle_codec"] != "mov_text":
            raise OfflineQAError("Expected mov_text subtitle track")
        _validate_srt(file.parent / "captions.srt", durations)
        _decode_all_streams(file)
        placeholder = any(x["media_source"] == "placeholder" for x in shots)
        if type(manifest.get("placeholder_visuals")) is not bool or manifest["placeholder_visuals"] != placeholder:
            raise OfflineQAError("Placeholder disclosure does not match shots")
        if manifest.get("has_subtitle_track") is not True:
            raise OfflineQAError("Manifest subtitle disclosure inconsistent")
        if manifest.get("paid_api_calls") != 0 or manifest.get("spoken_dialogue_generated") is not False:
            raise OfflineQAError("Offline preview metadata misstates provider or voice")
        if require_real_footage:
            # Input clips may also be synthetically rendered; merely swapping
            # all placeholders is not provenance of true AI footage.
            raise OfflineQAError("Human-authenticated original footage needed")
    except OfflineQAError:
        raise
    except (KeyError, TypeError, ValueError, OSError, PreviewError):
        raise OfflineQAError("Offline preview technical QA unavailable") from None

    return {
        "kind": "offline_technical_preview_qa",
        "technical_decode_passed": True,
        "subtitle_sidecar_timing_passed": True,
        "muxed_subtitle_track_present": True,
        "video_sha256_matches_manifest": True,
        "portrait_h264_aac_verified": True,
        "shots_checked": len(shots),
        "duration_seconds": total,
        "placeholder_visuals": placeholder,
        "synthetic_or_unverified_footage": True,
        "genuine_ai_video_verified": False,
        "spoken_dialogue_verified": False,
        "visual_continuity_verified": False,
        "copyright_scope_verified": False,
        "operator_review_required": True,
        "publish_approved": False,
        "production_ready": False,
        "paid_provider_calls": 0,
        "external_write_calls": 0,
    }
