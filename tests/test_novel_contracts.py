"""Rights-independent local schema validation; never uploads novel text to a model."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from drama_factory.novels.contracts import (
    NovelAdaptationBlueprint, NovelIndexMismatch,
    validate_blueprint_against_index,
)


def make_uploaded_source(client):
    source_text = "第一章 初遇\n她在书店遇到他。\n第二章 转折\n两人发现秘密。"
    resp = client.post(
        "/api/v1/novels/upload",
        data={"title": "自己写的小说", "rights_status": "pending"},
        files={"file": ("book.txt", source_text.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 201
    source_id = resp.json()["source_id"]
    chapters = client.get(f"/api/v1/novels/{source_id}/chapters").json()
    assert len(chapters) >= 2
    return resp.json(), chapters


def make_plan(source, chapters):
    ch1, ch2 = chapters[:2]
    span1 = {
        "source_id": source["source_id"], "chapter_ordinal": ch1["ordinal"],
        "start_offset": ch1["start_offset"], "end_offset": ch1["end_offset"],
    }
    span2 = {
        "source_id": source["source_id"], "chapter_ordinal": ch2["ordinal"],
        "start_offset": ch2["start_offset"], "end_offset": ch2["end_offset"],
    }
    return {
        "source": {
            "source_id": source["source_id"], "source_sha256": source["source_sha256"],
            "chapter_count": source["chapter_count"],
        },
        "characters": [
            {"mention_id": "m1", "name_in_source": "她", "source_spans": [span1]},
        ],
        "events": [
            {"event_id": "e1", "order": 1, "summary": "书店相遇",
             "character_mention_ids": ["m1"], "source_spans": [span1]},
            {"event_id": "e2", "order": 2, "summary": "发现秘密",
             "character_mention_ids": ["m1"], "source_spans": [span2],
             "caused_by_event_ids": ["e1"], "dramatic_function": "reversal"},
        ],
        "season": {
            "target_episode_count": 2,
            "episodes": [
                {"episode_number": 1, "working_title": "相遇", "target_seconds": 60,
                 "plot_event_ids": ["e1"], "hook": "神秘男子", "cliffhanger": "遗落的纸条"},
                {"episode_number": 2, "working_title": "秘密", "target_seconds": 60,
                 "plot_event_ids": ["e2"], "hook": "纸条曝光", "cliffhanger": "更大秘密"},
            ],
        },
    }


def test_valid_blueprint_matches_actual_index(client):
    source, chapters = make_uploaded_source(client)
    blueprint = NovelAdaptationBlueprint.model_validate(make_plan(source, chapters))
    validate_blueprint_against_index(client.app.state.db, blueprint)
    assert blueprint.season.episodes[0].plot_event_ids == ["e1"]
    assert blueprint.events[1].caused_by_event_ids == ["e1"]
    # The contract is a local in-memory schema, not a production permission or AI run.
    assert client.get(f"/api/v1/novels/{source['source_id']}").json()["rights_status"] == "pending"


@pytest.mark.parametrize("mode", [
    "unknown_event", "unknown_character", "bad_causality", "bad_count",
    "noncontiguous_episode", "bad_source", "duplicate_character", "reversed_span",
    "missing_event_order",
])
def test_blueprint_rejects_inconsistent_relations(client, mode):
    source, chapters = make_uploaded_source(client)
    raw = make_plan(source, chapters)
    if mode == "unknown_event":
        raw["season"]["episodes"][0]["plot_event_ids"] = ["missing"]
    elif mode == "unknown_character":
        raw["events"][0]["character_mention_ids"] = ["missing"]
    elif mode == "bad_causality":
        raw["events"][0]["caused_by_event_ids"] = ["e2"]
    elif mode == "bad_count":
        raw["season"]["target_episode_count"] = 3
    elif mode == "noncontiguous_episode":
        raw["season"]["episodes"][0]["episode_number"] = 9
    elif mode == "bad_source":
        raw["events"][0]["source_spans"][0]["source_id"] = "another_book"
    elif mode == "duplicate_character":
        raw["characters"].append(deepcopy(raw["characters"][0]))
    elif mode == "reversed_span":
        raw["events"][0]["source_spans"][0]["end_offset"] = 0
    else:
        raw["events"][1]["order"] = 5
    with pytest.raises(ValidationError):
        NovelAdaptationBlueprint.model_validate(raw)


def test_source_hash_and_offsets_are_verified(client):
    source, chapters = make_uploaded_source(client)
    raw = make_plan(source, chapters)
    raw["source"]["source_sha256"] = "f" * 64
    with pytest.raises(NovelIndexMismatch):
        validate_blueprint_against_index(client.app.state.db, NovelAdaptationBlueprint.model_validate(raw))
    raw = make_plan(source, chapters)
    raw["events"][0]["source_spans"][0]["end_offset"] = chapters[0]["end_offset"] + 1
    with pytest.raises(NovelIndexMismatch):
        validate_blueprint_against_index(client.app.state.db, NovelAdaptationBlueprint.model_validate(raw))
