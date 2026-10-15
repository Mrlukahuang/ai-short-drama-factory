"""P2: stage-to-stage Fake contracts (never paid model, DB write, approval)."""
from __future__ import annotations

from copy import deepcopy

import pytest

from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.fake_story_bible import build_fake_story_bible
from drama_factory.pipeline.fake_episode_screenplay import (
    FakeScreenplayError, build_fake_episode_screenplay,
)
from drama_factory.pipeline.screenplay import Screenplay
from drama_factory.pipeline.text import ScriptOutline


def _bible(tmp_path):
    p = tmp_path / "synthetic.txt"
    p.write_text(
        "某位虚构人物在旧火车站发现一张地图。\n"
        "另一位虚构朋友决定一起寻找答案，故事不会引用真人。",
        encoding="utf-8",
    )
    return build_fake_story_bible(p)


def test_p1_to_p2_two_typed_artifacts_and_exact_timeline(tmp_path):
    bible = _bible(tmp_path)
    data = build_fake_episode_screenplay(bible)
    again = build_fake_episode_screenplay(bible)
    assert data == again
    assert data["input_sha256"] == again["input_sha256"]
    assert data["fake_only"] and data["status"] == "fake_only"
    assert data["scope_validated_against_database"] is False
    assert data["provisional_asset_ids"] is True
    assert data["approval_granted"] is False
    assert data["publish_approved"] is False
    assert data["model_calls"] == data["paid_api_calls"] == 0
    assert data["actual_fee_usd"] is None
    outline = ScriptOutline.model_validate(data["script_outline"])
    screenplay = Screenplay.model_validate(data["screenplay"])
    assert outline.is_mock and not outline.ready_for_approval
    assert outline.source_fingerprint
    assert len(outline.scenes) == 1
    assert screenplay.schema_version == "screenplay.zh.v1"
    assert len(screenplay.shots) == 6
    assert sum(s.duration_seconds for s in screenplay.shots) == 60
    assert [s.shot_id for s in screenplay.shots] == [
        "S001", "S002", "S003", "S004", "S005", "S006",
    ]
    assert all(s.dialogue for s in screenplay.shots)
    assert all(line.text.startswith("FAKE") for s in screenplay.shots for line in s.dialogue)
    for prev, curr in zip(screenplay.shots, screenplay.shots[1:]):
        assert prev.continuity_end == curr.continuity_start
    assert set(data["provisional_refs"]) == {"actor_a", "actor_b", "scene"}
    draft = screenplay.to_episode_draft()
    assert isinstance(draft, EpisodeDraft)
    assert draft.target_duration_seconds == 60
    assert all(s.audio_mode == "locked_voice" for s in draft.shots)


@pytest.mark.parametrize("duration", [60, 61, 75, 89, 90])
def test_duration_distribution_is_exact_and_bounded(tmp_path, duration):
    result = build_fake_episode_screenplay(
        _bible(tmp_path), episode_number=12, target_duration_seconds=duration,
    )
    s = Screenplay.model_validate(result["screenplay"])
    assert s.episode_number == 12
    assert s.target_duration_seconds == duration
    assert len(s.shots) == 6
    assert all(1 <= shot.duration_seconds <= 30 for shot in s.shots)


def test_series_ids_are_stable_but_distinct_for_unrelated_ideas(tmp_path):
    original = _bible(tmp_path)
    one = build_fake_episode_screenplay(original)
    source = tmp_path / "synthetic.txt"
    source.write_text("两个人在森林里面看见一块蓝色的标记，开始寻找它的源头。", encoding="utf-8")
    other = build_fake_episode_screenplay(build_fake_story_bible(source))
    assert one["source_sha256"] != other["source_sha256"]
    assert one["screenplay"]["series_id"] != other["screenplay"]["series_id"]
    assert set(one["provisional_refs"].values()).isdisjoint(
        set(other["provisional_refs"].values())
    )


@pytest.mark.parametrize("bad", [
    {"fake_only": False},
    {"approval_granted": True},
    {"model_calls": 1},
    {"schema_version": "claimed-real"},
    {"source_sha256": "tampered"},
])
def test_reject_nonfake_or_untrusted_p1_envelope(tmp_path, bad):
    raw = deepcopy(_bible(tmp_path))
    raw.update(bad)
    with pytest.raises(FakeScreenplayError, match="Unverified"):
        build_fake_episode_screenplay(raw)


def test_reject_bible_schema_corruption_or_duration_mismatch(tmp_path):
    original = _bible(tmp_path)
    altered = deepcopy(original)
    altered["story_bible"]["title"] = ""
    with pytest.raises(FakeScreenplayError, match="canonical"):
        build_fake_episode_screenplay(altered)
    with pytest.raises(FakeScreenplayError, match="duration"):
        build_fake_episode_screenplay(original, target_duration_seconds=59)
    with pytest.raises(FakeScreenplayError, match="duration"):
        build_fake_episode_screenplay(original, target_duration_seconds=91)
    with pytest.raises(FakeScreenplayError, match="episode"):
        build_fake_episode_screenplay(original, episode_number=0)


def test_no_db_episode_commit_or_real_approval(client, tmp_path):
    raw = _bible(tmp_path)
    result = build_fake_episode_screenplay(raw)
    assert result["approval_granted"] is False
    # Synthetic provisional IDs are never inserted into scoped DB.
    sid = result["screenplay"]["series_id"]
    assert client.app.state.db.one("SELECT id FROM projects WHERE id=?", (sid,)) is None
    assert client.app.state.db.one(
        "SELECT id FROM story_bibles WHERE id=?",
        (result["screenplay"]["story_bible_id"],),
    ) is None
    assert client.get("/api/v1/projects").status_code == 200
