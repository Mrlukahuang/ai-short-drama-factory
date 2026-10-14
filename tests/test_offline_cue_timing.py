"""PR-10d: user-reviewed exact dialogue cue timing and real PCM silence gaps."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import wave

import pytest
from pydantic import ValidationError

from drama_factory.models import EpisodeDraft, ShotDraft
from drama_factory.pipeline.screenplay import ScreenplayShot
from drama_factory.pipeline.offline_cast_timeline import build_fake_cast_dialogue_timeline
from test_offline_cast_timeline import create_reviewed_cast


def _shot_lines():
    return [
        {"speaker_actor_id": "actor-a", "text": "First",
         "start_second": 1, "end_second": 2},
        {"speaker_actor_id": "actor-b", "text": "Second",
         "start_second": 3, "end_second": 4},
    ]


def _screenplay_shot(lines):
    return ScreenplayShot.model_validate({
        "shot_id": "talk", "duration_seconds": 4, "action": "Two fictional people",
        "camera": "medium", "character_ids": ["actor-a", "actor-b"],
        "dialogue": lines, "continuity_start": "Together", "continuity_end": "Apart",
    })


@pytest.mark.parametrize("field,value", [
    ("start_second", 2),  # line 1 would start at its own end
    ("end_second", 1),    # reverse duration
    ("end_second", 5),    # exceeds shot
    ("start_second", None),
    ("end_second", None),
    ("start_second", True),  # boolean is not timestamp
])
def test_review_rejects_invalid_or_partial_cue_time(field, value):
    lines = _shot_lines()
    lines[0][field] = value
    with pytest.raises(ValidationError):
        _screenplay_shot(lines)


def test_review_rejects_overlapping_and_mixed_timed_untimed_cues():
    lines = _shot_lines()
    lines[1]["start_second"] = 1
    with pytest.raises(ValidationError, match="overlaps"):
        _screenplay_shot(lines)
    lines = _shot_lines()
    lines[1].pop("start_second")
    lines[1].pop("end_second")
    with pytest.raises(ValidationError, match="timed or untimed"):
        _screenplay_shot(lines)


def test_approved_episode_storage_rejects_tampered_timing():
    base = {
        "shot_id": "talk", "duration_seconds": 4,
        "visual_description": "Two people discussing",
        "character_ids": ["actor-a","actor-b"],
        "dialogue": ["actor-a: First", "actor-b: Second"],
        "dialogue_cues": _shot_lines(),
    }
    assert ShotDraft.model_validate(base).dialogue_cues[0].start_second == 1
    for field, value in (("start_second", 2), ("end_second", 5)):
        broken = deepcopy(base)
        broken["dialogue_cues"][0][field] = value
        with pytest.raises(ValidationError):
            ShotDraft.model_validate(broken)
    broken = deepcopy(base)
    broken["dialogue_cues"][1]["start_second"] = 1
    with pytest.raises(ValidationError, match="overlaps"):
        ShotDraft.model_validate(broken)


def _frame_bytes(path):
    with wave.open(str(path), "rb") as stream:
        assert stream.getnchannels() == 1
        assert stream.getframerate() == 48000
        assert stream.getsampwidth() == 2
        return stream.readframes(stream.getnframes())


def test_two_reviewed_actor_lines_obey_exact_slots_and_verified_silence(client, tmp_path):
    production, mapping, _ = create_reviewed_cast(client, explicit_timing=True)
    db = client.app.state.db
    row = db.one(
        """SELECT e.body_json FROM productions p
           JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
        (production,),
    )
    stored = EpisodeDraft.model_validate_json(row["body_json"])
    cues = stored.shots[0].dialogue_cues
    assert [(c.start_second, c.end_second) for c in cues] == [(1,2),(3,4)]
    folder = tmp_path / "reviewed-exact-times"
    report = build_fake_cast_dialogue_timeline(
        db, production, mapping, folder, operator_confirmed_voice_rights=True,
    )
    payload = _frame_bytes(Path(report["local_wav_path"]))
    assert len(payload) == 6 * 48000 * 2
    def interval(start, finish):
        return payload[start * 48000 * 2: finish * 48000 * 2]
    assert interval(0,1) == b"\x00" * (48000 * 2)
    assert any(interval(1,2))
    assert interval(2,3) == b"\x00" * (48000 * 2)
    assert any(interval(3,4))
    assert interval(4,6) == b"\x00" * (2 * 48000 * 2)
    assert report["shot_receipts"][0]["cue_slots"] == [
        {"start_second":1,"end_second":2},
        {"start_second":3,"end_second":4},
    ]
    assert report["cue_count"] == 2
    assert report["real_spoken_dialogue_generated"] is False
    assert report["voice_consent_independently_verified"] is False
    assert report["publish_approved"] is False
    assert report["paid_provider_calls"] == 0
    replay = build_fake_cast_dialogue_timeline(
        db, production, mapping, folder, operator_confirmed_voice_rights=True,
    )
    assert replay["reused"] is True
    assert replay["local_wav_sha256"] == report["local_wav_sha256"]


def test_untimed_approved_cues_keep_deterministic_legacy_slots(client, tmp_path):
    production, mapping, _ = create_reviewed_cast(client)
    report = build_fake_cast_dialogue_timeline(
        client.app.state.db, production, mapping, tmp_path / "legacy",
        operator_confirmed_voice_rights=True,
    )
    assert report["shot_receipts"][0]["cue_slots"] == [
        {"start_second":0,"end_second":2},
        {"start_second":2,"end_second":4},
    ]
    assert report["shot_receipts"][1]["cue_slots"] == []
