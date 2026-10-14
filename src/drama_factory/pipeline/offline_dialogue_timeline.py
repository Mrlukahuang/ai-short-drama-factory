"""PR-10b: approved per-shot FakeAudio WAVs -> full episode PCM timeline.

The track is audible SYNTHETIC timing tones, not TTS, dialogue, actor voice,
lip-sync evidence or publishing authority. All approved shot/voice/consent
contracts are checked before any local WAV is created. No external requests.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import wave
from pathlib import Path

from drama_factory.db import Database
from drama_factory.models import EpisodeDraft
from drama_factory.providers.dialogue_audio import (
    DialogueGenerationDenied, DialogueGenerationSpec,
    FakeDialogueAudioProvider, _spec_fingerprint, _valid_cached_tone,
    _write_hash_marker, _file_hash,
)

_RATE = 48000
_MAX_SHOTS = 12
_MAX_SECONDS = 90


def build_fake_episode_dialogue_timeline(
    db: Database, production_id: str, voice_asset_id: str,
    output_root: Path, *, operator_confirmed_voice_rights: bool = False,
) -> dict:
    """Fail-closed one-voice local test timeline from approved shot text.

    This is NOT a production multi-actor voice assignment: each shot must
    contain exactly ONE previously approved dialogue line. A future TTS
    provider must support speaker/voice per line and signed consent.
    """
    record = db.one(
        """SELECT p.status,e.body_json,e.project_id
           FROM productions p JOIN episodes e ON e.id=p.episode_id
           WHERE p.id=?""", (production_id,),
    )
    if record is None or record["status"] not in (
        "ready_for_video_generation", "offline_preview_finished",
    ):
        raise DialogueGenerationDenied("Approved production is required")
    draft = EpisodeDraft.model_validate_json(record["body_json"])
    if len(draft.shots) > _MAX_SHOTS or draft.target_duration_seconds > _MAX_SECONDS:
        raise DialogueGenerationDenied("Audio timeline exceeds offline contract")
    if sum(s.duration_seconds for s in draft.shots) != draft.target_duration_seconds:
        raise DialogueGenerationDenied("Approved shot timing does not match episode")
    specs = []
    fingerprints = []
    for shot in draft.shots:
        if len(shot.dialogue) != 1:
            raise DialogueGenerationDenied(
                "Fake voice timeline supports exactly one approved line per shot"
            )
        spec = DialogueGenerationSpec(
            series_id=record["project_id"],
            production_id=production_id,
            shot_id=shot.shot_id,
            voice_asset_id=voice_asset_id,
            dialogue_text=shot.dialogue[0],
            duration_seconds=shot.duration_seconds,
            operator_confirmed_voice_rights=operator_confirmed_voice_rights,
        )
        key, version = _spec_fingerprint(db, spec)
        specs.append(spec)
        fingerprints.append({"shot_id": shot.shot_id, "fingerprint": key,
                             "seconds": shot.duration_seconds, "voice_version": version})

    # The final file fingerprint includes ordered shot-level fingerprints,
    # not path names or user-visible dialogue. Reordered shots invalidate it.
    payload = json.dumps({
        "version": "fake-episode-voice-timeline-v1",
        "production_id": production_id,
        "voice_asset_id": voice_asset_id,
        "shots": fingerprints,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    key = hashlib.sha256(payload.encode()).hexdigest()

    folder = Path(output_root)
    if folder.is_symlink():
        raise DialogueGenerationDenied("Unsafe fake dialogue output directory")
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / ("fake-episode-dialogue-" + key[:32] + ".wav")
    marker = Path(str(dest) + ".sha256")
    cached = _valid_cached_tone(dest, marker, draft.target_duration_seconds)

    if not cached:
        provider = FakeDialogueAudioProvider()
        receipts = [provider.synthesize(db, s, folder / "shots") for s in specs]
        temp = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=folder, prefix=".episode-dialogue-", suffix=".wav",
                delete=False,
            ) as handle:
                temp = Path(handle.name)
            with wave.open(str(temp), "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(_RATE)
                for spec, receipt in zip(specs, receipts, strict=True):
                    file = Path(receipt["local_wav_path"])
                    if file.is_symlink() or _file_hash(file) != receipt["local_wav_sha256"]:
                        raise DialogueGenerationDenied("Fake shot audio changed before assembly")
                    with wave.open(str(file), "rb") as input_wav:
                        if (
                            input_wav.getnchannels() != 1
                            or input_wav.getsampwidth() != 2
                            or input_wav.getframerate() != _RATE
                            or input_wav.getnframes() != _RATE * spec.duration_seconds
                        ):
                            raise DialogueGenerationDenied("Fake shot WAV format inconsistent")
                        while block := input_wav.readframes(4096):
                            out.writeframesraw(block)
                out.writeframes(b"")
            os.replace(temp, dest)
            _write_hash_marker(dest, _file_hash(dest))
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        if not _valid_cached_tone(dest, marker, draft.target_duration_seconds):
            raise DialogueGenerationDenied("Full fake episode WAV verification failed")

    return {
        "provider": "fake-episode-dialogue-timeline-v1",
        "synthetic_tones_only": True,
        "real_spoken_dialogue_generated": False,
        "local_wav_path": str(dest),
        "local_wav_sha256": _file_hash(dest),
        "fingerprint": key,
        "duration_seconds": draft.target_duration_seconds,
        "shots": fingerprints,
        "reused": cached,
        "voice_consent_independently_verified": False,
        "publish_approved": False,
        "paid_provider_calls": 0,
    }
