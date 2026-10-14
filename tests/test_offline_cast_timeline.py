"""PR-10c: two reviewed voices, multiple lines, silence and exact WAV timing."""
from __future__ import annotations

import hashlib
import json
import shutil
import struct
import wave
from pathlib import Path

import pytest
from pydantic import ValidationError

from drama_factory.models import EpisodeDraft, ShotDraft, ApprovedDialogueCue
from drama_factory.pipeline.offline_cast_timeline import build_fake_cast_dialogue_timeline
from drama_factory.pipeline.offline_demo import build_offline_demo
from drama_factory.providers.dialogue_audio import DialogueGenerationDenied


def _post(client, url, body=None):
    response = client.post(url, json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


def create_reviewed_cast(client, *, duplicate_line=False, explicit_timing=False):
    series = _post(client, "/api/v1/projects", {
        "title": "Two fictional speakers", "premise": "A scripted conversation",
    })["series_id"]
    bible = _post(client, f"/api/v1/series/{series}/story-bibles", {
        "title": "Consent test", "logline": "Two speakers and one silent shot",
        "genre": "test",
    })["story_bible_id"]
    voices, actors = [], []
    for i in range(2):
        voice = _post(client, f"/api/v1/series/{series}/assets", {
            "kind": "voice", "key": f"voice_{i}", "specification": {
                "name": f"Original tone {i}",
                "voice_description": "Original non-speech sine for test only",
                "source_consent_reference": f"original-synthetic-only-{i}",
            },
        })["asset_id"]
        actor = _post(client, f"/api/v1/series/{series}/assets", {
            "kind": "actor", "key": f"actor_{i}", "specification": {
                "name": f"Fictional actor {i}",
                "appearance": "Fictional adult", "identity_anchors": [f"scarf-{i}"],
                "voice_asset_id": voice,
            },
        })["asset_id"]
        voices.append(voice)
        actors.append(actor)
    lines = [
        {"speaker_actor_id": actors[0], "text": "Repeat" if duplicate_line else "Hello"},
        {"speaker_actor_id": actors[1], "text": "Repeat" if duplicate_line else "Welcome"},
    ]
    if explicit_timing:
        lines[0]["start_second"] = 1
        lines[0]["end_second"] = 2
        lines[1]["start_second"] = 3
        lines[1]["end_second"] = 4
    shots = [
        {"shot_id": "talk", "duration_seconds": 4, "action": "Two people talking",
         "camera": "medium", "character_ids": actors, "dialogue": lines,
         "continuity_start": "Together", "continuity_end": "Together"},
        {"shot_id": "silence", "duration_seconds": 2, "action": "Silent reaction",
         "camera": "closeup", "character_ids": [actors[0]], "dialogue": [],
         "continuity_start": "Together", "continuity_end": "Quiet"},
    ]
    script = {
        "series_id": series, "story_bible_id": bible, "episode_number": 1,
        "episode_title": "Approved dialogue", "target_duration_seconds": 6,
        "shots": shots,
    }
    v = _post(client, f"/api/v1/series/{series}/screenplays/validate", script)
    assert v["review_required"] is True
    for stored, line in zip(v["episode_draft"]["shots"][0]["dialogue_cues"], lines, strict=True):
        assert stored["speaker_actor_id"] == line["speaker_actor_id"]
        assert stored["text"] == line["text"]
        assert stored.get("start_second") == line.get("start_second")
        assert stored.get("end_second") == line.get("end_second")
    commit = _post(client, f"/api/v1/series/{series}/screenplays/commit", {
        "screenplay": script, "reviewed_by_operator": True,
    })
    run = _post(client, f"/api/v1/episodes/{commit['episode_id']}/productions")["production_id"]
    _post(client, f"/api/v1/productions/{run}/approve-script")
    _post(client, f"/api/v1/productions/{run}/approve-characters")
    return run, dict(zip(actors, voices)), actors


def _frames(file):
    with wave.open(str(file), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 48000
        return wav.readframes(wav.getnframes())


def test_reviewed_two_actor_cues_allocate_slots_silent_shot_and_cache(client, tmp_path):
    production, voice_map, actors = create_reviewed_cast(client)
    out = tmp_path / "approved-cast-wav"
    db = client.app.state.db
    first = build_fake_cast_dialogue_timeline(
        db, production, voice_map, out, operator_confirmed_voice_rights=True,
    )
    file = Path(first["local_wav_path"])
    frames = _frames(file)
    assert len(frames) == 6 * 48000 * 2
    assert any(frames[0:4 * 48000 * 2])
    assert frames[4 * 48000 * 2:] == b"\x00" * (2 * 48000 * 2)
    assert first["shot_count"] == 2
    assert first["cue_count"] == 2
    assert first["speaking_actor_count"] == 2
    assert first["shot_receipts"][0]["cue_count"] == 2
    assert first["shot_receipts"][1]["cue_count"] == 0
    assert first["reused"] is False
    assert first["real_spoken_dialogue_generated"] is False
    assert first["voice_consent_independently_verified"] is False
    assert first["publish_approved"] is False
    assert first["paid_provider_calls"] == 0
    assert "Hello" not in str(first) and "Welcome" not in str(first)
    again = build_fake_cast_dialogue_timeline(
        db, production, voice_map, out, operator_confirmed_voice_rights=True,
    )
    assert again["reused"] is True
    assert again["fingerprint"] == first["fingerprint"]
    file.write_bytes(b"synthetic corruption" * 100)
    fixed = build_fake_cast_dialogue_timeline(
        db, production, voice_map, out, operator_confirmed_voice_rights=True,
    )
    assert fixed["reused"] is False
    assert fixed["local_wav_sha256"] == first["local_wav_sha256"]


def test_duplicate_text_different_speakers_get_different_cue_hashes(client, tmp_path):
    production, mapping, _ = create_reviewed_cast(client, duplicate_line=True)
    report = build_fake_cast_dialogue_timeline(
        client.app.state.db, production, mapping, tmp_path / "same-text",
        operator_confirmed_voice_rights=True,
    )
    first, second = report["shot_receipts"][0]["cue_keys"]
    assert first != second
    assert report["cue_count"] == 2


@pytest.mark.parametrize("change", ["swapped_voices","missing_voice","extra_voice","wrong_rights"])
def test_wrong_or_unapproved_voice_mapping_leaves_no_outputs(client, tmp_path, change):
    production, mapping, actors = create_reviewed_cast(client)
    if change == "swapped_voices":
        mapping = {actors[0]: mapping[actors[1]], actors[1]: mapping[actors[0]]}
    elif change == "missing_voice":
        mapping.pop(actors[1])
    elif change == "extra_voice":
        mapping["unknown-actor"] = "unknown-voice"
    consent = change != "wrong_rights"
    output = tmp_path / "never"
    with pytest.raises(DialogueGenerationDenied):
        build_fake_cast_dialogue_timeline(
            client.app.state.db, production, mapping, output,
            operator_confirmed_voice_rights=consent,
        )
    assert not output.exists()


def test_structured_cue_tampering_fails_model_validation_without_db(client):
    a = "actor-a"
    base = {
        "shot_id": "x", "duration_seconds": 5,
        "visual_description": "Approved placeholder", "character_ids": [a],
        "dialogue": [f"{a}: Approved line"],
        "dialogue_cues": [{"speaker_actor_id": a, "text": "Approved line"}],
    }
    assert ShotDraft.model_validate(base).dialogue_cues[0].speaker_actor_id == a
    for corrupt in (
        {**base, "dialogue": ["Forged text"]},
        {**base, "dialogue_cues": [{"speaker_actor_id": "foreign", "text": "Approved line"}]},
    ):
        with pytest.raises(ValidationError):
            ShotDraft.model_validate(corrupt)


def test_legacy_manual_shot_without_structured_cues_remains_compatible():
    shot = ShotDraft(shot_id="old", duration_seconds=1,
                     visual_description="Legacy", dialogue=["legacy text"])
    assert shot.dialogue_cues == []


ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Mandatory offline-video CI runs actual FFmpeg integration",
)


@ffmpeg_required
def test_six_second_reviewed_two_actor_fake_cast_mix_creates_real_mp4(tmp_path):
    report = build_offline_demo(tmp_path / "cast", duration_seconds=6,
                                with_fake_cast_timeline=True)
    assert report["fake_cast_timeline"] is True
    assert report["fake_cast_actors"] == 2
    assert report["fake_cast_cues"] == 3
    assert report["local_dialogue_audio_supplied"] is True
    assert report["local_music_audio_supplied"] is True
    assert report["offline_audio_mix"]["subtitle_track_preserved"] is True
    assert report["technical_qa"]["technical_decode_passed"] is True
    assert report["technical_qa"]["subtitle_sidecar_timing_passed"] is True
    assert report["technical_qa"]["publish_approved"] is False
    assert report["voice_license_independently_verified"] is False
    assert report["real_tts_generated"] is False
    assert report["paid_api_calls"] == 0
    assert (tmp_path / "cast" / "demo.mp4").is_file()


@pytest.mark.parametrize("bad", ["yes", 1, 0, None, []])
def test_cast_demo_rejects_non_boolean_before_io(tmp_path, bad):
    out = tmp_path / "no-write"
    with pytest.raises(ValueError, match="Fake cast timeline flag"):
        build_offline_demo(out, with_fake_cast_timeline=bad)
    assert not out.exists()


def test_cast_demo_rejects_overlapping_modes_before_io(tmp_path):
    out = tmp_path / "never"
    with pytest.raises(ValueError, match="Select only one"):
        build_offline_demo(out, with_fake_voice_timeline=True,
                           with_fake_cast_timeline=True)
    assert not out.exists()
