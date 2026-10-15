"""P3 fake asset scopes: real local SQLite transactions, no model or media."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from drama_factory.pipeline.fake_story_bible import build_fake_story_bible
from drama_factory.pipeline.fake_episode_screenplay import build_fake_episode_screenplay
from drama_factory.pipeline.fake_cast_assets import (
    FakeAssetBindingError, bind_fake_cast_assets,
)
from drama_factory.pipeline.screenplay import Screenplay, check_screenplay_scope


def _stages(tmp_path):
    p = tmp_path / "original.txt"
    p.write_text(
        "两个虚构朋友在深夜的旧车站找到一个写着数字的木盒。\n"
        "他们在没人使用的候车室研究这个谜题。",
        encoding="utf-8",
    )
    first = build_fake_story_bible(p)
    second = build_fake_episode_screenplay(first)
    return first, second


def test_insert_scoped_fake_asset_versions_and_validate_real_db_refs(client, tmp_path):
    db = client.app.state.db
    p1, p2 = _stages(tmp_path)
    b = bind_fake_cast_assets(db, p1, p2)
    assert b["fake_only"] and b["database_scope_verified"]
    assert b["approval_granted"] is False
    assert b["publish_approved"] is False
    assert b["paid_api_calls"] == 0 and b["actual_fee_usd"] is None
    assert b["series_id"] == p2["screenplay"]["series_id"]
    assert b["story_bible_id"] == p2["screenplay"]["story_bible_id"]
    assert len(b["assets"]) == 5
    assert sorted(x["kind"] for x in b["assets"]) == [
        "actor", "actor", "scene", "voice", "voice",
    ]
    assert all(len(x["specification_sha256"]) == 64 for x in b["assets"])
    screenplay = Screenplay.model_validate(b["screenplay"])
    check_screenplay_scope(db, screenplay)
    assert all(shot.scene_id is not None for shot in screenplay.shots)
    for key, voice_id in b["voice_refs"].items():
        actor_id = p2["provisional_refs"][key]
        actor = db.one(
            "SELECT specification_json FROM series_assets WHERE id=?", (actor_id,),
        )
        assert json.loads(actor["specification_json"])["voice_asset_id"] == voice_id
    assert db.one("SELECT COUNT(*) AS n FROM episodes")["n"] == 0
    assert db.one("SELECT COUNT(*) AS n FROM productions")["n"] == 0


def test_idempotent_same_source_does_not_duplicate_versions(client, tmp_path):
    db = client.app.state.db
    p1, p2 = _stages(tmp_path)
    first = bind_fake_cast_assets(db, p1, p2)
    rows1 = db.many("SELECT id,series_id,kind,asset_key,version,specification_json FROM series_assets")
    second = bind_fake_cast_assets(db, p1, p2)
    rows2 = db.many("SELECT id,series_id,kind,asset_key,version,specification_json FROM series_assets")
    assert first == second
    assert rows1 == rows2
    assert len(rows2) == 5
    assert db.one("SELECT COUNT(*) AS n FROM story_bibles")["n"] == 1


def test_conflicting_preexisting_asset_is_rejected_without_mutation(client, tmp_path):
    db = client.app.state.db
    p1, p2 = _stages(tmp_path)
    bind_fake_cast_assets(db, p1, p2)
    actor = p2["provisional_refs"]["actor_a"]
    db.exec(
        "UPDATE series_assets SET specification_json=? WHERE id=?",
        ('{"name":"unexpected"}', actor),
    )
    before = db.many("SELECT id,specification_json FROM series_assets ORDER BY id")
    with pytest.raises(FakeAssetBindingError, match="Conflicting"):
        bind_fake_cast_assets(db, p1, p2)
    assert db.many("SELECT id,specification_json FROM series_assets ORDER BY id") == before


def test_mismatched_p1_p2_binding_denied_before_db_insert(client, tmp_path):
    db = client.app.state.db
    p1, p2 = _stages(tmp_path)
    forged = deepcopy(p2)
    forged["provisional_refs"]["actor_a"] = "asset_" + "0" * 14
    with pytest.raises(FakeAssetBindingError, match="provenance"):
        bind_fake_cast_assets(db, p1, forged)
    changed_bible = deepcopy(p1)
    changed_bible["story_bible"]["title"] = "有人修改了故事来源"
    with pytest.raises(FakeAssetBindingError, match="provenance"):
        bind_fake_cast_assets(db, changed_bible, p2)
    assert db.one("SELECT COUNT(*) AS n FROM projects")["n"] == 0
    assert db.one("SELECT COUNT(*) AS n FROM series_assets")["n"] == 0


def test_two_fake_series_never_share_asset_ids(client, tmp_path):
    db = client.app.state.db
    a1, a2 = _stages(tmp_path)
    first = bind_fake_cast_assets(db, a1, a2)
    path = tmp_path / "original.txt"
    path.write_text("另一组完全虚构人物在森林里找到一张古老地图。", encoding="utf-8")
    from drama_factory.pipeline.fake_story_bible import build_fake_story_bible
    b1 = build_fake_story_bible(path)
    b2 = build_fake_episode_screenplay(b1)
    second = bind_fake_cast_assets(db, b1, b2)
    assert first["series_id"] != second["series_id"]
    assert {x["asset_id"] for x in first["assets"]}.isdisjoint(
        {x["asset_id"] for x in second["assets"]}
    )
    assert db.one("SELECT COUNT(*) AS n FROM story_bibles")["n"] == 2
    for state in (first, second):
        check_screenplay_scope(db, Screenplay.model_validate(state["screenplay"]))
