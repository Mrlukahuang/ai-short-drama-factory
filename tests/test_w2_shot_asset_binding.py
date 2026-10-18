"""W2 pinned manifest and no-provider contract tests; synthetic scoped SQLite only."""
from copy import deepcopy
import hashlib
import json
import socket

import pytest

from drama_factory.db import Database, DEFAULT_COLUMN_ID, timestamp
from drama_factory.models import ActorBible, SceneBible, StoryBible, VoiceBible
from drama_factory.pipeline.screenplay import Screenplay
from drama_factory.pipeline.shot_asset_binding import (
    ShotAssetBindingError, build_bound_screenplay_video_plan, canonical_json,
)
from drama_factory.pipeline.text import ScriptContext
from test_writer_execution_prep import prepared, screenplay


SOURCE = "c5665e198eb3d30110a0bb6dc30d5f2cfadf74979eb5e6e0596d64751ff1a6f9"


@pytest.fixture
def sample(tmp_path):
    db = Database(tmp_path / "w2.sqlite")
    context = ScriptContext.model_validate_json(prepared().context_json)
    draft = Screenplay.model_validate(screenplay())
    bible = StoryBible(title="测试集", logline="无真实人像的毛毡双人镜头", genre="测试")
    db.exec(
        """INSERT INTO projects
           (id,title,premise,visual_style,ratio,created_at,column_id)
           VALUES (?,?,?,?,?,?,?)""",
        (context.series_id, "测试", "本地测试", "felt_diorama",
         "9:16", timestamp(), DEFAULT_COLUMN_ID),
    )
    db.exec(
        "INSERT INTO story_bibles (id,series_id,version,body_json,created_at) VALUES (?,?,?,?,?)",
        (context.story_bible_id, context.series_id, 2, bible.model_dump_json(), timestamp()),
    )
    specifications = {
        "a-jie": ("actor", ActorBible(
            name="阿杰", appearance="年轻绿围裙毛毡玩偶",
            identity_anchors=["棕短发", "圆脸"], costume_notes="森林绿围裙",
            voice_asset_id="voice-ajie",
        )),
        "xiao-yu": ("actor", ActorBible(
            name="小雨", appearance="黄色外套毛毡玩偶",
            identity_anchors=["黑色长发"], costume_notes="淡黄外套",
        )),
        "cafe": ("scene", SceneBible(name="咖啡店", location="雨棚下",
                                      layout="木桌在正中")),
        "voice-ajie": ("voice", VoiceBible(name="阿杰音色",
                                           voice_description="尚未经真人音轨验证")),
    }
    locks = {}
    for aid, (kind, model) in specifications.items():
        spec = model.model_dump_json()
        db.exec(
            """INSERT INTO series_assets
               (id,series_id,kind,asset_key,version,specification_json,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (aid, context.series_id, kind, aid, 3, spec, timestamp()),
        )
        locks[aid] = {
            "version": 3,
            "specification_sha256": hashlib.sha256(spec.encode()).hexdigest(),
        }
    return db, draft, context, locks


def bound(sample, *, draft=None, locks=None, **overrides):
    db, original, context, versions = sample
    kw = {
        "style_prompt": "Handmade needle-felted miniature diorama",
        "style_version": "felt_diorama@v1",
        "source_response_sha256": SOURCE,
        "locked_assets": locks if locks is not None else versions,
    }
    kw.update(overrides)
    return build_bound_screenplay_video_plan(
        db, draft if draft is not None else original, context, **kw,
    )


def test_repeated_canonical_manifest_and_prompts_are_identical_offline(sample, monkeypatch):
    def network_denied(*args, **kwargs):
        raise AssertionError("No network or paid generation allowed")
    monkeypatch.setattr(socket, "socket", network_denied)
    one, two = bound(sample), bound(sample)
    assert canonical_json(one["manifest"]) == canonical_json(two["manifest"])
    assert one["manifest_sha256"] == two["manifest_sha256"]
    assert [x["prompt_sha256"] for x in one["plan"]["shots"]] == [
        x["prompt_sha256"] for x in two["plan"]["shots"]
    ]
    assert len(one["manifest"]["shots"]) == 6
    assert one["manifest"]["story_bible_version"] == 2
    assert one["manifest"]["source_response_sha256"] == SOURCE
    assert one["manifest"]["production_assets_verified"] is False
    assert one["manifest"]["provider_reference_applied"] is False
    assert one["manifest"]["reference_images_supported"] is False
    assert one["manifest"]["audio_reference_supported"] is False
    assert one["plan"]["paid_api_calls"] == 0
    assert one["plan"]["paid_execution_authorized"] is False
    assert one["manifest"]["new_paid_model_calls"] == 0
    assert one["manifest"]["publish_approved"] is False
    for record, shot in zip(one["manifest"]["shots"], one["plan"]["shots"]):
        assert record["character_ids"] == ["a-jie", "xiao-yu"]
        assert record["scene_asset"]["version"] == 3
        assert record["characters"][0]["costume_version"] == 3
        assert record["characters"][0]["voice_asset"]["asset_id"] == "voice-ajie"
        assert record["speaker_cues"][0]["expected_dialogue"] == "你好"
        assert shot["asset_binding"] == record
        assert shot["prior_prompt_sha256"] != shot["prompt_sha256"]
        assert hashlib.sha256(shot["prompt"].encode()).hexdigest() == shot["prompt_sha256"]
        assert shot["request_preview"]["input"] == shot["prompt"]


def test_only_visible_cast_enters_shot_prompt(sample):
    raw = deepcopy(screenplay())
    raw["shots"][0]["character_ids"] = ["a-jie"]
    result = bound(sample, draft=Screenplay.model_validate(raw))
    first = result["plan"]["shots"][0]["prompt"]
    second = result["plan"]["shots"][1]["prompt"]
    assert "xiao-yu" not in first and "小雨" not in first
    assert "xiao-yu" in second
    assert len(result["manifest"]["shots"][0]["characters"]) == 1


def test_version_style_story_or_source_changes_manifest_digest(sample):
    original = bound(sample)
    assert original["manifest_sha256"] != bound(
        sample, style_version="felt_diorama@v2",
    )["manifest_sha256"]
    assert original["manifest_sha256"] != bound(
        sample, source_response_sha256="1" * 64,
    )["manifest_sha256"]
    db, _, context, locks = sample
    db.exec(
        "UPDATE series_assets SET version=4 WHERE id=? AND series_id=?",
        ("a-jie", context.series_id),
    )
    bumped = deepcopy(locks)
    bumped["a-jie"]["version"] = 4
    updated = bound(sample, locks=bumped)
    assert updated["manifest_sha256"] != original["manifest_sha256"]
    assert original["manifest"]["shots"][0]["characters"][0]["version"] == 3
    db.exec(
        "UPDATE story_bibles SET version=3 WHERE id=? AND series_id=?",
        (context.story_bible_id, context.series_id),
    )
    assert bound(sample, locks=bumped)["manifest_sha256"] != updated["manifest_sha256"]


@pytest.mark.parametrize("kind", [
    "missing_pin", "missing_sha", "bad_sha", "wrong_version", "extra_asset",
    "actor_foreign_series", "scene_foreign_series", "spec_changed",
    "missing_costume", "foreign_actor", "foreign_scene", "speaker",
    "story_bible_foreign", "conflicting_appearance", "unlisted_appearance",
    "missing_source_sha", "wrong_voice_kind",
])
def test_invalid_identity_scope_or_version_fails_closed(sample, kind):
    db, original, context, locks = sample
    pins = deepcopy(locks)
    raw = original.model_dump(mode="json")
    extra = {}
    if kind == "missing_pin": pins.pop("a-jie")
    elif kind == "missing_sha": pins["a-jie"].pop("specification_sha256")
    elif kind == "bad_sha": pins["a-jie"]["specification_sha256"] = "z" * 64
    elif kind == "wrong_version": pins["a-jie"]["version"] += 1
    elif kind == "extra_asset": pins["other"] = pins["a-jie"].copy()
    elif kind == "actor_foreign_series":
        db.exec("UPDATE series_assets SET series_id='other' WHERE id='a-jie'")
    elif kind == "scene_foreign_series":
        db.exec("UPDATE series_assets SET series_id='other' WHERE id='cafe'")
    elif kind == "spec_changed":
        db.exec("UPDATE series_assets SET specification_json='{}' WHERE id='a-jie'")
    elif kind == "missing_costume":
        model = ActorBible(name="阿杰", appearance="绿围裙", identity_anchors=["圆脸"])
        spec = model.model_dump_json()
        db.exec("UPDATE series_assets SET specification_json=? WHERE id='a-jie'", (spec,))
        pins["a-jie"]["specification_sha256"] = hashlib.sha256(spec.encode()).hexdigest()
    elif kind == "foreign_actor": raw["shots"][0]["character_ids"].append("not-in-series")
    elif kind == "foreign_scene": raw["shots"][0]["scene_id"] = "not-in-series"
    elif kind == "speaker": raw["shots"][0]["dialogue"][0]["speaker_actor_id"] = "x"
    elif kind == "story_bible_foreign":
        db.exec("UPDATE story_bibles SET series_id='other' WHERE id=?", (context.story_bible_id,))
    elif kind == "conflicting_appearance":
        extra["shot_appearance_anchors"] = {
            s.shot_id: {a: ("老年阿杰" if s.shot_id == "1" and a == "a-jie"
                            else ("年轻绿围裙毛毡玩偶" if a == "a-jie"
                                  else "黄色外套毛毡玩偶"))
                        for a in s.character_ids} for s in original.shots
        }
    elif kind == "unlisted_appearance":
        extra["shot_appearance_anchors"] = {"0": {"a-jie": "fake"}}
    elif kind == "missing_source_sha": extra["source_response_sha256"] = ""
    elif kind == "wrong_voice_kind":
        db.exec("UPDATE series_assets SET kind='prop' WHERE id='voice-ajie'")
    with pytest.raises(ValueError):
        bound(sample, draft=Screenplay.model_validate(raw), locks=pins, **extra)


def test_selected_shot_retains_legacy_plan_and_rejects_noncontiguous(sample):
    result = bound(sample, shot_ids=["1", "2"])
    assert result["manifest"]["selected_shot_ids"] == ["1", "2"]
    assert [x["shot_id"] for x in result["manifest"]["shots"]] == ["1", "2"]
    assert len(result["plan"]["shots"]) == 2
    with pytest.raises(ValueError, match="contiguous"):
        bound(sample, shot_ids=["0", "2"])
