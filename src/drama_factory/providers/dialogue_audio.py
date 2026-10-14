"""PR-10a: reviewed voice-asset contract + synthetic local WAV FakeTTS.

No Google client, API keys, network, real voice cloning, proprietary TTS or
publication. The fake emits an audible sine tone for media pipeline tests,
never spoken dialogue. Approved text and asset ownership are checked first.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import wave
from array import array
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from drama_factory.db import Database
from drama_factory.models import EpisodeDraft

_FAKE_MODEL = "fake-dialogue-timing-tone-v1"
_RATE = 48000
_LIMIT = 90
_HEX = re.compile(r"[a-f0-9]{64}\Z")


class DialogueGenerationDenied(ValueError):
    """Errors must not include user dialogue, asset spec or source paths."""


class DialogueGenerationSpec(BaseModel):
    series_id: str = Field(min_length=1, max_length=120)
    production_id: str = Field(min_length=1, max_length=120)
    shot_id: str = Field(min_length=1, max_length=80)
    voice_asset_id: str = Field(min_length=1, max_length=120)
    dialogue_text: str = Field(min_length=1, max_length=1000)
    duration_seconds: int = Field(ge=1, le=_LIMIT)
    language: Literal["zh-CN", "en-NZ", "en-US"] = "zh-CN"
    operator_confirmed_voice_rights: bool = False


def _spec_fingerprint(db: Database, spec: DialogueGenerationSpec) -> tuple[str, int]:
    if spec.operator_confirmed_voice_rights is not True:
        raise DialogueGenerationDenied("Explicit operator voice-rights confirmation required")
    production = db.one(
        """SELECT p.status,e.body_json,e.project_id
           FROM productions p JOIN episodes e ON e.id=p.episode_id
           WHERE p.id=?""", (spec.production_id,),
    )
    if production is None or production["project_id"] != spec.series_id:
        raise DialogueGenerationDenied("Production does not belong to selected series")
    if production["status"] not in ("ready_for_video_generation", "offline_preview_finished"):
        raise DialogueGenerationDenied("Approved screenplay and actors required")
    episode = EpisodeDraft.model_validate_json(production["body_json"])
    shot = next((item for item in episode.shots if item.shot_id == spec.shot_id), None)
    if shot is None or spec.dialogue_text not in shot.dialogue:
        raise DialogueGenerationDenied("Dialogue must exactly match an approved shot line")
    if spec.duration_seconds > shot.duration_seconds:
        raise DialogueGenerationDenied("Dialogue tone duration exceeds approved shot")
    voice = db.one(
        """SELECT id,version,specification_json FROM series_assets
           WHERE id=? AND series_id=? AND kind='voice'""",
        (spec.voice_asset_id, spec.series_id),
    )
    if voice is None:
        raise DialogueGenerationDenied("Voice asset not found in the same series")
    try:
        attributes = json.loads(voice["specification_json"])
    except (json.JSONDecodeError, TypeError):
        raise DialogueGenerationDenied("Invalid versioned voice record") from None
    if not isinstance(attributes.get("source_consent_reference"), str) or not attributes["source_consent_reference"].strip():
        raise DialogueGenerationDenied("Voice source consent reference is required")
    # A recorded consent reference is a technical entry, not independently
    # validated real-world likeness/voice/publishing authorization.
    payload = {
        "provider": _FAKE_MODEL,
        "series": spec.series_id, "production": spec.production_id,
        "shot": spec.shot_id, "voice_asset": spec.voice_asset_id,
        "voice_version": voice["version"],
        "voice_spec_sha256": hashlib.sha256(voice["specification_json"].encode()).hexdigest(),
        "dialogue_sha256": hashlib.sha256(spec.dialogue_text.encode()).hexdigest(),
        "language": spec.language, "duration": spec.duration_seconds,
    }
    key = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return key, int(voice["version"])


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for part in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def _valid_cached_tone(path: Path, marker: Path, seconds: int) -> bool:
    if path.is_symlink() or marker.is_symlink() or not path.is_file() or not marker.is_file():
        return False
    try:
        expected = marker.read_text("ascii").strip()
        if not _HEX.fullmatch(expected) or _file_hash(path) != expected:
            return False
        with wave.open(str(path), "rb") as wav:
            return (
                wav.getnchannels() == 1
                and wav.getsampwidth() == 2
                and wav.getframerate() == _RATE
                and wav.getnframes() == seconds * _RATE
                and wav.getcomptype() == "NONE"
            )
    except (OSError, ValueError, EOFError, UnicodeError, wave.Error):
        return False


def _write_timing_tone(path: Path, seconds: int, fingerprint: str) -> None:
    """Write ~0.02-amplitude deterministic audible sine, not voice or speech."""
    hz = 320 + int(fingerprint[:4], 16) % 180
    samples = array(
        "h", (int(680 * math.sin(2 * math.pi * hz * idx / _RATE))
              for idx in range(_RATE)),
    )
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, suffix=".wav", prefix=".fake-audio-",
            delete=False,
        ) as f:
            temp = Path(f.name)
        with wave.open(str(temp), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(_RATE)
            for _ in range(seconds):
                wav.writeframesraw(samples.tobytes())
            wav.writeframes(b"")
        os.replace(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _write_hash_marker(path: Path, hash_value: str) -> None:
    marker = Path(str(path) + ".sha256")
    temp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="ascii", dir=marker.parent,
            prefix=".fake-audio-digest-", delete=False,
        ) as file:
            temp = Path(file.name)
            file.write(hash_value + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, marker)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


class FakeDialogueAudioProvider:
    """Stable, offline WAV placeholder only. No actual TTS service is called."""

    def synthesize(
        self, db: Database, spec: DialogueGenerationSpec, output_root: Path,
    ) -> dict:
        key, voice_version = _spec_fingerprint(db, spec)
        root = Path(output_root)
        if root.is_symlink():
            raise DialogueGenerationDenied("Unsafe audio output directory")
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = root / ("fake-dialogue-" + key[:32] + ".wav")
        marker = Path(str(path) + ".sha256")
        reused = _valid_cached_tone(path, marker, spec.duration_seconds)
        if not reused:
            path.unlink(missing_ok=True)
            marker.unlink(missing_ok=True)
            _write_timing_tone(path, spec.duration_seconds, key)
            _write_hash_marker(path, _file_hash(path))
        return {
            "provider": _FAKE_MODEL,
            "is_fake": True,
            "synthetic_timing_tone_only": True,
            "real_spoken_dialogue_generated": False,
            "local_wav_path": str(path),
            "local_wav_sha256": _file_hash(path),
            "fingerprint": key,
            "voice_asset_version": voice_version,
            "reused": reused,
            "voice_consent_independently_verified": False,
            "operator_review_required": True,
            "publish_approved": False,
            "paid_model_calls": 0,
        }


class GeminiDialogueAudioProvider:
    """Future real adapter is NOT implemented. Always fail closed."""

    def synthesize(self, *_args, **_kwargs):
        raise DialogueGenerationDenied(
            "Real Gemini TTS unavailable: provider/billing/voice-consent review required"
        )
