"""Screenplay schema, human review and strict series asset boundaries."""
from copy import deepcopy


def setup_series(client, title):
    response = client.post("/api/v1/projects", json={"title": title, "premise": "原创剧情"})
    assert response.status_code == 201
    sid = response.json()["series_id"]
    bible = client.post(f"/api/v1/series/{sid}/story-bibles", json={
        "title": title, "logline": "主人公重逢", "genre": "都市情感",
    }).json()["story_bible_id"]
    actor = client.post(f"/api/v1/series/{sid}/assets", json={
        "kind": "actor", "key": "female", "specification": {
            "name": "女主", "appearance": "黑色短发", "identity_anchors": ["眼角有痣"],
        },
    }).json()["asset_id"]
    scene = client.post(f"/api/v1/series/{sid}/assets", json={
        "kind": "scene", "key": "home", "specification": {
            "name": "客厅", "location": "公寓", "layout": "桌子靠墙",
        },
    }).json()["asset_id"]
    return sid, bible, actor, scene


def screenplay(sid, bible, actor, scene):
    return {
        "series_id": sid, "story_bible_id": bible, "episode_number": 1,
        "episode_title": "雨夜", "target_duration_seconds": 8,
        "hook": "女主听见敲门", "ending_cliffhanger": "门后是谁",
        "shots": [
            {
                "shot_id": "s1", "duration_seconds": 4, "action": "女主走到门边",
                "camera": "中景平推", "character_ids": [actor], "scene_id": scene,
                "dialogue": [{"speaker_actor_id": actor, "text": "谁在外面？"}],
                "continuity_start": "右手空着", "continuity_end": "右手握住门把手",
            },
            {
                "shot_id": "s2", "duration_seconds": 4, "action": "女主打开门",
                "camera": "近景", "character_ids": [actor], "scene_id": scene,
                "dialogue": [], "continuity_start": "握住门把手",
                "continuity_end": "门半开",
            },
        ],
    }


def test_validate_then_review_commit(client):
    sid, bible, actor, scene = setup_series(client, "故事A")
    src = screenplay(sid, bible, actor, scene)
    validate = client.post(f"/api/v1/series/{sid}/screenplays/validate", json=src)
    assert validate.status_code == 200, validate.text
    assert validate.json()["review_required"] is True
    assert validate.json()["shot_count"] == 2
    assert validate.json()["episode_draft"]["shots"][0]["dialogue"] == [f"{actor}: 谁在外面？"]
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []
    url = f"/api/v1/series/{sid}/screenplays/commit"
    assert client.post(url, json={"screenplay": src, "reviewed_by_operator": False}).status_code == 422
    committed = client.post(url, json={"screenplay": src, "reviewed_by_operator": True})
    assert committed.status_code == 201, committed.text
    assert committed.json()["production_created"] is False
    assert len(client.get(f"/api/v1/projects/{sid}/episodes").json()) == 1
    assert client.post(url, json={"screenplay": src, "reviewed_by_operator": True}).status_code == 409


def test_cross_series_references_are_rejected(client):
    sid, bible, actor, scene = setup_series(client, "故事A")
    other, other_bible, other_actor, other_scene = setup_series(client, "故事B")
    good = screenplay(sid, bible, actor, scene)
    for field, foreign in [
        ("story_bible_id", other_bible),
        ("series_id", other),
    ]:
        altered = deepcopy(good)
        altered[field] = foreign
        assert client.post(f"/api/v1/series/{sid}/screenplays/validate", json=altered).status_code == 422
    bad_actor = deepcopy(good)
    bad_actor["shots"][0]["character_ids"] = [other_actor]
    bad_actor["shots"][0]["dialogue"][0]["speaker_actor_id"] = other_actor
    assert client.post(f"/api/v1/series/{sid}/screenplays/validate", json=bad_actor).status_code == 422
    bad_scene = deepcopy(good)
    bad_scene["shots"][0]["scene_id"] = other_scene
    assert client.post(f"/api/v1/series/{sid}/screenplays/validate", json=bad_scene).status_code == 422


def test_bad_timeline_ids_and_dialogue_are_rejected(client):
    sid, bible, actor, scene = setup_series(client, "故事A")
    url = f"/api/v1/series/{sid}/screenplays/validate"
    good = screenplay(sid, bible, actor, scene)
    for variant in ("duration", "duplicate", "speaker", "missing_continuity"):
        altered = deepcopy(good)
        if variant == "duration":
            altered["target_duration_seconds"] = 7
        elif variant == "duplicate":
            altered["shots"][1]["shot_id"] = "s1"
        elif variant == "speaker":
            altered["shots"][0]["dialogue"][0]["speaker_actor_id"] = "someone-else"
        elif variant == "missing_continuity":
            altered["shots"][0]["continuity_start"] = ""
        assert client.post(url, json=altered).status_code == 422


def test_manual_screenplay_does_not_interfere_with_fake_drafts(client):
    sid, bible, actor, scene = setup_series(client, "故事A")
    fake = client.post(f"/api/v1/series/{sid}/script-drafts", json={
        "story_bible_id": bible, "episode_number": 1, "target_duration_seconds": 60,
        "creative_brief": "剧本模拟", "actor_asset_ids": [actor], "scene_asset_id": scene,
    })
    assert fake.status_code == 201
    assert fake.json()["draft"]["ready_for_approval"] is False
    assert client.get(f"/api/v1/projects/{sid}/episodes").json() == []
    manual = client.post(f"/api/v1/series/{sid}/screenplays/commit", json={
        "screenplay": screenplay(sid, bible, actor, scene), "reviewed_by_operator": True,
    })
    assert manual.status_code == 201
