"""AMEND-005 P5: offline, NON-SPEECH cue tones, SRT index, synthetic music.

Explicitly not TTS, actual music, voice authorization or publication rights.
P3 Fake voices have NO consent reference, so we deliberately do not call
the existing consent-gated FakeDialogueAudioProvider. The original SRT and
mixing mechanisms are reused, but no voice consent is invented.
"""
from __future__ import annotations

from array import array
import hashlib
import json
import math
from pathlib import Path
import wave

from drama_factory.db import Database
from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.offline_audio import inspect_local_wav, mix_local_stems
from drama_factory.pipeline.offline_render import inspect_mp4

RATE = 48000
SCHEMA = "fake-audio-stage.zh.v1"


class FakeAudioStageError(ValueError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _write_pcm(path: Path, *, seconds: int, intervals: list[tuple[int,int,int]],
               music: bool) -> None:
    """Exactly 48kHz mono PCM; generated from math, never a real actor."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        silent = b"\x00\x00" * RATE
        for second in range(seconds):
            active = next((speaker for start, end, speaker in intervals
                           if start <= second < end), None)
            if active is None and not music:
                f.writeframesraw(silent)
                continue
            frequency = 186 if music else (330 if active == 0 else 440)
            amplitude = 210 if music else 750
            # 1s per bounded block avoids buffering any copyrighted media.
            tone = array("h", (
                int(amplitude * math.sin(2 * math.pi * frequency * i / RATE))
                for i in range(RATE)
            ))
            f.writeframesraw(tone.tobytes())
        f.writeframes(b"")


def build_fake_episode_audio(
    db: Database, series_id: str, production_id: str,
    shot_manifest: dict, media_root: Path, output_root: Path,
) -> tuple[dict, dict, dict]:
    """Bind P4 finished Fake shot clips to 06/07/08, with local mixed MP4.

    Calls no provider. Must be invoked only on the P4 approved Fake production;
    all inputs, captions, and receipts are inspected before any output.
    """
    if (type(shot_manifest) is not dict
            or shot_manifest.get("step") != "05_shots"
            or shot_manifest.get("fake_only") is not True
            or shot_manifest.get("approved_real_content") is not False
            or shot_manifest.get("paid_provider_calls") != 0
            or shot_manifest.get("actual_fee_usd") is not None
            or shot_manifest.get("series_id") != series_id
            or shot_manifest.get("production_id") != production_id):
        raise FakeAudioStageError("Verified P4 Fake shot manifest required")
    row = db.one(
        """SELECT p.status,e.project_id,e.body_json
           FROM productions p JOIN episodes e ON p.episode_id=e.id WHERE p.id=?""",
        (production_id,),
    )
    if (row is None or row["project_id"] != series_id
            or row["status"] != "offline_preview_finished"):
        raise FakeAudioStageError("Completed, scoped P4 Fake preview required")
    episode = EpisodeDraft.model_validate_json(row["body_json"])
    seconds = episode.target_duration_seconds
    if not 60 <= seconds <= 90 or len(episode.shots) != shot_manifest.get("shot_count"):
        raise FakeAudioStageError("Invalid Fake episode duration or shot count")
    shots = shot_manifest.get("shots")
    if type(shots) is not list or [x.get("shot_id") for x in shots] != [
        s.shot_id for s in episode.shots
    ] or any(x.get("provider") != "fake" or x.get("model_calls") != 0
             or x.get("video_source") != "offline_placeholder_not_ai" for x in shots):
        raise FakeAudioStageError("Non-Fake shot result denied")
    folder = Path(media_root) / series_id / production_id
    mp4 = folder / "preview.mp4"
    srt = folder / "captions.srt"
    receipt = folder / "manifest.json"
    if any(p.is_symlink() or not p.is_file() for p in (mp4, srt, receipt)):
        raise FakeAudioStageError("Missing or linked P4 preview artifacts")
    if _sha(mp4) != shot_manifest.get("technical_episode_mp4_sha256"):
        raise FakeAudioStageError("P4 episode MP4 hash mismatch")
    inspected = inspect_mp4(mp4, seconds)
    if inspected["subtitle_codec"] != "mov_text":
        raise FakeAudioStageError("No embedded P4 subtitle track")
    render = json.loads(receipt.read_text("utf-8"))
    if (render.get("mp4_sha256") != _sha(mp4)
            or render.get("production_id") != production_id
            or render.get("series_id") != series_id
            or render.get("paid_api_calls") != 0
            or render.get("spoken_dialogue_generated") is not False
            or render.get("offline_audio_mix") is not None):
        raise FakeAudioStageError("P4 manifest changed or contains non-Fake audio")

    # The same cue division contract is used by offline_render and QA.
    intervals: list[tuple[int,int,int]] = []
    cue_index = []
    cursor = 0
    for shot in episode.shots:
        count = len(shot.dialogue_cues)
        if count == 0 and shot.dialogue:
            raise FakeAudioStageError("No approved speaker metadata for Fake dialogue")
        for i, cue in enumerate(shot.dialogue_cues):
            if cue.speaker_actor_id not in shot.character_ids:
                raise FakeAudioStageError("Foreign speaker in approved Fake shot")
            if cue.start_second is None:
                start = sum(shot.duration_seconds // count + (
                    1 if j < shot.duration_seconds % count else 0)
                    for j in range(i))
                end = start + shot.duration_seconds // count + (
                    1 if i < shot.duration_seconds % count else 0)
            else:
                start, end = cue.start_second, cue.end_second
            if not 0 <= start < end <= shot.duration_seconds:
                raise FakeAudioStageError("Invalid approved cue slot")
            speaker_order = shot.character_ids.index(cue.speaker_actor_id) % 2
            intervals.append((cursor + start, cursor + end, speaker_order))
            cue_index.append({
                "shot_id": shot.shot_id,
                "start_second": cursor + start, "end_second": cursor + end,
                "speaker_asset_id": cue.speaker_actor_id,
                "text_sha256": hashlib.sha256(
                    (" ".join(f"{cue.speaker_actor_id}: {cue.text}".split())[:300])
                    .encode("utf-8")
                ).hexdigest(),
            })
        cursor += shot.duration_seconds
    if not cue_index or cursor != seconds:
        raise FakeAudioStageError("No Fake cue timeline")
    expected_schedule = [{
        "start_second": x["start_second"],
        "end_second": x["end_second"],
        "text_sha256": x["text_sha256"],
    } for x in cue_index]
    if expected_schedule != render.get("subtitle_schedule"):
        raise FakeAudioStageError("P4 SRT does not match approved cue timing")
    from drama_factory.pipeline.offline_qa import inspect_offline_delivery
    qa = inspect_offline_delivery(render, mp4)
    if qa.get("technical_qa_passed") is not True:
        raise FakeAudioStageError("P4 subtitle or MP4 QA failed")

    output = Path(output_root)
    if output.is_symlink():
        raise FakeAudioStageError("Linked audio output directory denied")
    output.mkdir(parents=True, exist_ok=True)
    # stage files live under the caller's dedicated local run directory.
    dialogue_wav = output / "06_dialogue.fake.wav"
    music_wav = output / "08_music.fake.wav"
    _write_pcm(dialogue_wav, seconds=seconds, intervals=intervals, music=False)
    _write_pcm(music_wav, seconds=seconds, intervals=[], music=True)
    dialogue = inspect_local_wav(dialogue_wav, target_seconds=seconds, kind="dialogue")
    music = inspect_local_wav(music_wav, target_seconds=seconds, kind="music")
    mixed = output / "09_audio_mixed.fake.mp4"
    mix = mix_local_stems(
        mp4, mixed, duration_seconds=seconds, dialogue=dialogue, music=music,
    )
    if not mix["subtitle_track_preserved"]:
        raise FakeAudioStageError("P5 mixed MP4 lost subtitles")
    inspect_mp4(mixed, seconds)
    common = {
        "schema_version": SCHEMA, "series_id": series_id,
        "production_id": production_id, "fake_only": True,
        "actual_fee_usd": None, "paid_provider_calls": 0,
        "publish_approved": False, "real_speech_generated": False,
    }
    return (
        {**common, "step": "06_dialogue", "synthetic_non_speech": True,
         "wav_name": dialogue_wav.name, "wav_sha256": dialogue["sha256"],
         "cue_count": len(cue_index), "duration_seconds": seconds},
        {**common, "step": "07_subtitles", "srt_name": srt.name,
         "srt_sha256": _sha(srt), "subtitle_cues": cue_index,
         "subtitle_track_preserved": True},
        {**common, "step": "08_music", "synthetic_music_only": True,
         "wav_name": music_wav.name, "wav_sha256": music["sha256"],
         "duration_seconds": seconds, "mixed_mp4_name": mixed.name,
         "mixed_mp4_sha256": _sha(mixed), "mix": mix},
    )
