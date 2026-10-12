"""Offline script provider tests; no model credentials or network access."""
from drama_factory.pipeline.text import (
    FakeTextProvider, PROMPT_TEMPLATES, PROMPT_VERSION,
    ScriptContext, ScriptOutline, ScriptPlanRequest, source_fingerprint,
)
import pytest
from pydantic import ValidationError


def create_series(client, title):
    result = client.post("/api/v1/projects", json={"title": title, "premise": "关于信任的故事"})
    assert result.status_code == 201
    return result.json()["series_id"]


def create_bible(client, series):
    result = client.post(f"/api/v1/series/{series}/story-bibles", json={
        "title": "测试剧", "logline": "男女主在雨夜重逢", "genre": "都市情感",
    })
    assert result.status_code == 201
    return result.json()["story_bible_id"]


def create_asset(client, series, kind):
    if kind == "actor":
        specification = {"name": "女主", "appearance": "短发", "identity_anchors": ["眼角痣"]}
    else:
        specification = {"name": "客厅", "location": "公寓", "layout": "一张桌子"}
    response = client.post(f"/api/v1/series/{series}/assets", json={
        "kind": kind, "key": kind + "_primary", "specification": specification,
    })
    assert response.status_code == 201
    return response.json()["asset_id"]


def body(bible, actors=None, scene=None):
    return {
        "story_bible_id": bible,
        "episode_number": 1,
        "target_duration_seconds": 60,
        "creative_brief": "雨夜重逢，保持设定。",
        "actor_asset_ids": actors or [],
        "scene_asset_id": scene,
    }


def test_fake_draft_scoped_and_persisted(client):
    series = create_series(client, "剧一")
    bible = create_bible(client, series)
    actor = create_asset(client, series, "actor")
    scene = create_asset(client, series, "scene")
    endpoint = f"/api/v1/series/{series}/script-drafts"
    first = client.post(endpoint, json=body(bible, [actor], scene))
    assert first.status_code == 201, first.text
    response = first.json()
    assert response["status"] == "mock_only"
    assert response["paid_api_calls"] == 0
    assert response["episodes_created"] == 0
    assert response["draft"]["is_mock"] is True
    assert response["draft"]["ready_for_approval"] is False
    assert response["draft"]["scenes"][0]["actor_asset_ids"] == [actor]
    assert response["draft"]["scenes"][0]["scene_asset_id"] == scene
    assert client.get(endpoint).json()[0]["id"] == response["draft_id"]
    assert client.get(endpoint + "/" + response["draft_id"]).json()["draft"] == response["draft"]
    second = client.post(endpoint, json=body(bible, [actor], scene)).json()
    assert second["draft"]["source_fingerprint"] == response["draft"]["source_fingerprint"]
    assert second["draft_id"] != response["draft_id"]
    assert client.get(f"/api/v1/projects/{series}/episodes").json() == []


def test_cross_series_references_rejected(client):
    first, second = create_series(client, "剧A"), create_series(client, "剧B")
    own_bible = create_bible(client, first)
    other_bible = create_bible(client, second)
    foreign_actor = create_asset(client, second, "actor")
    foreign_scene = create_asset(client, second, "scene")
    url = f"/api/v1/series/{first}/script-drafts"
    assert client.post(url, json=body(other_bible)).status_code == 422
    assert client.post(url, json=body(own_bible, [foreign_actor])).status_code == 422
    assert client.post(url, json=body(own_bible, scene=foreign_scene)).status_code == 422
    assert client.get(f"/api/v1/series/{second}/script-drafts").json() == []


def test_missing_series_and_bible(client):
    assert client.post("/api/v1/series/missing/script-drafts", json=body("none")).status_code == 404
    series = create_series(client, "剧A")
    assert client.post(f"/api/v1/series/{series}/script-drafts", json=body("none")).status_code == 422


def test_prompt_validation_and_duplicates(client):
    series = create_series(client, "剧A")
    bible = create_bible(client, series)
    actor = create_asset(client, series, "actor")
    url = f"/api/v1/series/{series}/script-drafts"
    assert client.post(url, json={**body(bible), "prompt_version": "unknown.v8"}).status_code == 422
    assert client.post(url, json=body(bible, [actor, actor])).status_code == 422


def test_fake_contract_and_input_versioning():
    request = ScriptPlanRequest(**body("bible_one"))
    context = ScriptContext(
        series_id="s1", story_bible_id="bible_one",
        story_bible_json={"title": "剧一", "canon": "事件不能穿越时间"},
        allowed_actor_ids=[],
    )
    assert PROMPT_VERSION in PROMPT_TEMPLATES
    draft = FakeTextProvider().generate(request, context)
    assert isinstance(draft, ScriptOutline)
    assert len(draft.source_fingerprint) == 64
    assert draft.source_fingerprint == source_fingerprint(request, context)
    other_context = context.model_copy(update={"story_bible_json": {"title": "剧一", "canon": "不同设定"}})
    assert source_fingerprint(request, other_context) != draft.source_fingerprint
    with pytest.raises(ValidationError):
        ScriptOutline.model_validate({
            **draft.model_dump(), "scenes": [{"order": 2, "summary": "缺少第一场"}],
        })
