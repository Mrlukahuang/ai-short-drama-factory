"""PR-10c: ordered multi-actor approved fake dialogue and silent-shot PCM.

Only generates deterministic NON-SPEECH timing tones; never external TTS,
real actor voices, paid APIs, or permission to publish. A human-reviewed
screenplay stores cue identities with each EpisodeDraft shot.
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
    DialogueGenerationDenied, DialogueGenerationSpec, FakeDialogueAudioProvider,
    _file_hash, _spec_fingerprint, _valid_cached_tone, _write_hash_marker,
)

_RATE = 48000


def build_fake_cast_dialogue_timeline(
    db: Database, production_id: str, voice_assets_by_actor: dict[str, str],
    output_root: Path, *, operator_confirmed_voice_rights: bool = False,
) -> dict:
    """One cohesive WAV: multiple speaker cues per shot, silent gaps as needed.

    Explicit reviewed start/end seconds are used verbatim, with real silent
    gaps. Untimed legacy approved cues retain deterministic equal divisions.
    Neither mode constitutes speech duration or lip synchronization.
    """
    if operator_confirmed_voice_rights is not True:
        raise DialogueGenerationDenied("Explicit voice-rights attestation required")
    if (
        type(voice_assets_by_actor) is not dict
        or not voice_assets_by_actor
        or any(
            type(actor) is not str or not actor or type(voice) is not str or not voice
            for actor, voice in voice_assets_by_actor.items()
        )
    ):
        raise DialogueGenerationDenied("Invalid explicit actor-to-voice mapping")
    row = db.one(
        """SELECT p.status,e.body_json,e.project_id
           FROM productions p JOIN episodes e ON e.id=p.episode_id
           WHERE p.id=?""",
        (production_id,),
    )
    if row is None or row["status"] not in (
        "ready_for_video_generation", "offline_preview_finished",
    ):
        raise DialogueGenerationDenied("Both production approvals are required")
    draft = EpisodeDraft.model_validate_json(row["body_json"])
    if len(draft.shots) > 12 or draft.target_duration_seconds > 90:
        raise DialogueGenerationDenied("Offline multi-voice timeline exceeds limit")
    if sum(s.duration_seconds for s in draft.shots) != draft.target_duration_seconds:
        raise DialogueGenerationDenied("Approved shot lengths disagree with episode")

    # Fully preflight every speaker, cue, consent record and voice assignment
    # BEFORE filesystem mutation or generating a single fake audio file.
    plans = []
    required = set()
    for shot in draft.shots:
        if not shot.dialogue_cues and shot.dialogue:
            raise DialogueGenerationDenied("Legacy dialogue has no approved speaker metadata")
        if len(shot.dialogue_cues) > 8 or len(shot.dialogue_cues) > shot.duration_seconds:
            raise DialogueGenerationDenied("Not enough integer-second slots for approved cues")
        seconds = shot.duration_seconds
        count = len(shot.dialogue_cues)
        if count and shot.dialogue_cues[0].start_second is not None:
            slots = [
                (cue.start_second, cue.end_second)
                for cue in shot.dialogue_cues
            ]
        else:
            parts = [seconds // count + (1 if i < seconds % count else 0)
                     for i in range(count)] if count else []
            offset = 0
            slots = []
            for length in parts:
                slots.append((offset, offset + length))
                offset += length
        cues = []
        for index, (cue, slot) in enumerate(zip(shot.dialogue_cues, slots, strict=True)):
            start_second, end_second = slot
            duration = end_second - start_second
            required.add(cue.speaker_actor_id)
            voice_id = voice_assets_by_actor.get(cue.speaker_actor_id)
            if not voice_id:
                raise DialogueGenerationDenied("No explicitly assigned voice for approved speaker")
            spec = DialogueGenerationSpec(
                series_id=row["project_id"], production_id=production_id,
                shot_id=shot.shot_id,
                speaker_actor_id=cue.speaker_actor_id, cue_index=index,
                voice_asset_id=voice_id,
                dialogue_text=f"{cue.speaker_actor_id}: {cue.text}",
                duration_seconds=duration,
                operator_confirmed_voice_rights=True,
            )
            key, version = _spec_fingerprint(db, spec)
            cues.append((spec, key, version, start_second, end_second))
        plans.append((shot.shot_id, seconds, cues))
    if not required or required != set(voice_assets_by_actor):
        raise DialogueGenerationDenied("Voice mapping must cover exact approved speaking cast")

    anonymous = [{
        "shot_id": shot_id,
        "seconds": seconds,
        "cue_count": len(cues),
        "cue_keys": [item[1] for item in cues],
        "cue_slots": [
            {"start_second": item[3], "end_second": item[4]}
            for item in cues
        ],
    } for shot_id, seconds, cues in plans]
    key = hashlib.sha256(json.dumps({
        "version": "fake-structured-cast-timeline-v2-timed",
        "production": production_id, "shots": anonymous,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    directory = Path(output_root)
    if directory.is_symlink():
        raise DialogueGenerationDenied("Unsafe fake audio folder")
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / ("fake-structured-cast-" + key[:32] + ".wav")
    marker = Path(str(destination) + ".sha256")
    cached = _valid_cached_tone(destination, marker, draft.target_duration_seconds)
    if not cached:
        provider = FakeDialogueAudioProvider()
        # Preflight above prevents unknown speakers or consent errors from
        # causing half-rendered full-episode outputs.
        receipts = [
            provider.synthesize(db, spec, directory / "cues")
            for _, _, cues in plans for spec, _, _, _, _ in cues
        ]
        by_key = {receipt["fingerprint"]: receipt for receipt in receipts}
        temp = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=directory, prefix=".fake-cast-", suffix=".wav", delete=False,
            ) as output_file:
                temp = Path(output_file.name)
            with wave.open(str(temp), "wb") as dest_wav:
                dest_wav.setnchannels(1)
                dest_wav.setsampwidth(2)
                dest_wav.setframerate(_RATE)
                for _, seconds, cues in plans:
                    at_frames = 0
                    for spec, part_key, _, start_second, end_second in cues:
                        # Preserve explicitly approved pauses, including
                        # silence before the first line and between speakers.
                        while at_frames < start_second * _RATE:
                            frames = min(start_second * _RATE - at_frames, 4096)
                            dest_wav.writeframesraw(b"\x00\x00" * frames)
                            at_frames += frames
                        receipt = by_key[part_key]
                        source = Path(receipt["local_wav_path"])
                        if source.is_symlink() or _file_hash(source) != receipt["local_wav_sha256"]:
                            raise DialogueGenerationDenied("Synthetic cue changed before assembly")
                        with wave.open(str(source), "rb") as wav:
                            if (
                                wav.getnchannels() != 1
                                or wav.getsampwidth() != 2
                                or wav.getframerate() != _RATE
                                or wav.getnframes() != spec.duration_seconds * _RATE
                            ):
                                raise DialogueGenerationDenied("Invalid approved cue audio timing")
                            while data := wav.readframes(4096):
                                dest_wav.writeframesraw(data)
                        at_frames = end_second * _RATE
                    while at_frames < seconds * _RATE:
                        frames = min(seconds * _RATE - at_frames, 4096)
                        dest_wav.writeframesraw(b"\x00\x00" * frames)
                        at_frames += frames
                dest_wav.writeframes(b"")
            os.replace(temp, destination)
            _write_hash_marker(destination, _file_hash(destination))
        finally:
            if temp:
                temp.unlink(missing_ok=True)
        if not _valid_cached_tone(destination, marker, draft.target_duration_seconds):
            raise DialogueGenerationDenied("Complete multi-actor fake WAV did not verify")

    return {
        "provider": "fake-structured-cast-timeline-v2-timed",
        "synthetic_tones_only": True,
        "real_spoken_dialogue_generated": False,
        "local_wav_path": str(destination),
        "local_wav_sha256": _file_hash(destination),
        "fingerprint": key,
        "duration_seconds": draft.target_duration_seconds,
        "shot_count": len(plans),
        "cue_count": sum(len(cues) for _, _, cues in plans),
        "speaking_actor_count": len(required),
        "shot_receipts": anonymous,  # only opaque fingerprints, no text
        "reused": cached,
        "voice_consent_independently_verified": False,
        "publish_approved": False,
        "paid_provider_calls": 0,
    }
