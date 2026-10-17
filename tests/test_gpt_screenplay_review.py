"""Synthetic GPT responses through real SQLite and existing human review gate."""
import json
import socket

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from drama_factory.db import Database
from drama_factory.pipeline.gpt_screenplay_review import GPTScreenplayImport, prepare_gpt_review
from drama_factory.pipeline.screenplay_routes import router
from drama_factory.pipeline.text import ScriptContext
from test_writer_execution_prep import prepared, response


@pytest.fixture
def review_client(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External network forbidden")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    req = prepared()
    context = ScriptContext.model_validate_json(req.context_json)
    db = Database(tmp_path / "review.sqlite")
    db.exec("INSERT INTO projects VALUES (?,?,?,?,?,?,?)",
            (context.series_id, "合成测试", "原创", "felt", "9:16", "now", "col_default"))
    db.exec("INSERT INTO story_bibles VALUES (?,?,?,?,?)", (context.story_bible_id,
            context.series_id, 1, json.dumps(context.story_bible_json), "now"))
    for asset, kind in [(a, "actor") for a in context.allowed_actor_ids] + [(context.allowed_scene_id, "scene")]:
        db.exec("INSERT INTO series_assets VALUES (?,?,?,?,?,?,?)",
                (asset, context.series_id, kind, asset, 1, "{}", "now"))
    app = FastAPI()
    app.state.db = db
    app.include_router(router)
    with TestClient(app) as client:
        yield client, db, context


def body(model="gpt-6.1-sol"):
    return {"model": model, "request": json.loads(prepared(model).request_json),
            "response": response(model), "response_date": "2026-10-17"}


@pytest.mark.parametrize("model", ["gpt-6.1-sol", "gpt-6-luna"])
def test_import_preview_requires_existing_explicit_commit(review_client, model):
    client, db, context = review_client
    url = f"/api/v1/series/{context.series_id}/screenplays"
    result = client.post(url + "/from-openai-response/validate", json=body(model))
    assert result.status_code == 200, result.text
    packet = result.json()
    assert packet["status"] == "pending_human_review"
    assert packet["approval_granted"] is False and packet["paid_api_calls"] == 0
    assert packet["response_authenticity_verified"] is False
    assert packet["original_request_binding_verified"] is False
    assert packet["estimated_usd"] is None and packet["actual_invoice_verified"] is False
    assert packet["episode_draft"]["target_duration_seconds"] == 60
    assert db.many("SELECT * FROM episodes") == []
    assert db.many("SELECT * FROM productions") == []
    commit = {"screenplay": packet["screenplay"], "reviewed_by_operator": False}
    assert client.post(url + "/commit", json=commit).status_code == 422
    commit["reviewed_by_operator"] = True
    assert client.post(url + "/commit", json=commit).status_code == 201
    assert len(db.many("SELECT * FROM episodes")) == 1
    assert db.many("SELECT * FROM productions") == []


@pytest.mark.parametrize("fault", ["truncated", "refused", "model", "foreign_asset", "bible", "series"])
def test_bad_imports_do_not_create_episodes(review_client, fault):
    client, db, context = review_client
    payload = body()
    sid = context.series_id
    if fault == "truncated":
        payload["response"]["status"] = "incomplete"
    elif fault == "refused":
        payload["response"]["output"][0]["content"] = [{"type": "refusal", "refusal": "private"}]
    elif fault == "model":
        payload["response"]["model"] = "gemini-3.8-flash"
    elif fault == "foreign_asset":
        db.exec("DELETE FROM series_assets WHERE id=?", (context.allowed_actor_ids[0],))
    elif fault == "bible":
        payload["request"]["story_bible_id"] = "foreign-bible"
    else:
        sid = "foreign-series"
    result = client.post(f"/api/v1/series/{sid}/screenplays/from-openai-response/validate", json=payload)
    assert result.status_code in (404, 422)
    assert db.many("SELECT * FROM episodes") == []


def test_import_model_allowlist_and_approval_fields(review_client):
    client, db, context = review_client
    url = f"/api/v1/series/{context.series_id}/screenplays/from-openai-response/validate"
    for changes in ({"model": "gemini-3.8-flash"}, {"approval_granted": True}):
        assert client.post(url, json={**body(), **changes}).status_code == 422


def test_unknown_usage_stays_unknown_not_free(review_client):
    _, _, context = review_client
    supplied = body()
    del supplied["response"]["usage"]
    packet = prepare_gpt_review(GPTScreenplayImport.model_validate(supplied), context)
    assert packet["usage_tokens"] is None and packet["estimated_usd"] is None
