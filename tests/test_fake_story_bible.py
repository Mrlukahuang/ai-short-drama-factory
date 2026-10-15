"""P1 independent offline contracts; no API keys, DB changes or model calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from drama_factory.models import StoryBible
from drama_factory.pipeline.fake_story_bible import (
    MAX_BRIEF_BYTES,
    FakeSynopsisError,
    build_fake_story_bible,
    main,
    write_fake_story_bible,
)


def _synopsis(tmp_path, data="雨夜的两个朋友在空荡火车站发现一封信。\n他们决定查清信的来历。"):
    path = tmp_path / "synopsis.txt"
    path.write_text(data, encoding="utf-8")
    return path


def test_bible_uses_existing_schema_and_is_deterministic_without_model(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    text = "雨夜的两个朋友在空荡火车站发现一封信。\n他们决定查清信的来历。"
    path = _synopsis(tmp_path, text)
    before = path.read_bytes()
    first = build_fake_story_bible(path)
    second = build_fake_story_bible(path)
    assert first == second
    assert first["source_sha256"] == hashlib.sha256(before).hexdigest()
    assert first["source_bytes"] == len(before)
    assert first["schema_version"] == "fake-story-bible.zh.v1"
    assert first["step"] == "01_story_bible"
    assert first["fake_only"] and first["status"] == "fake_only"
    assert first["approval_granted"] is False
    assert first["ready_for_approval"] is False
    assert first["paid_api_calls"] == first["model_calls"] == 0
    assert first["actual_fee_usd"] is None
    bible = StoryBible.model_validate(first["story_bible"])
    assert bible.logline.startswith("雨夜的两个朋友")
    assert "Fake" in bible.genre
    assert path.read_bytes() == before


def test_cli_writes_valid_json_without_touching_input(tmp_path):
    source = _synopsis(tmp_path)
    output = tmp_path / "bible.json"
    assert main([str(source), "--output", str(output)]) == 0
    assert json.loads(output.read_text("utf-8")) == build_fake_story_bible(source)
    assert source.is_file()
    with pytest.raises(FakeSynopsisError, match="already|new"):
        write_fake_story_bible(build_fake_story_bible(source), output)


def test_different_source_bytes_have_different_provenance(tmp_path):
    a = _synopsis(tmp_path, "两个朋友在车站重逢，疑惑地查看地图。")
    first = build_fake_story_bible(a)
    a.write_text("两个朋友在车站重逢，疑惑地查看地图！", encoding="utf-8")
    second = build_fake_story_bible(a)
    assert first["source_sha256"] != second["source_sha256"]
    assert first["story_bible"]["logline"] != second["story_bible"]["logline"]


@pytest.mark.parametrize("payload", [
    b"",
    b"\xff" * 100,
    b"\x00" + "两个朋友决定寻找真相。".encode(),
    b"a" * (MAX_BRIEF_BYTES + 1),
    b"\n \n",
    b"too short",
])
def test_invalid_inputs_are_rejected_before_output(tmp_path, payload):
    file = tmp_path / "test.txt"
    file.write_bytes(payload)
    with pytest.raises(FakeSynopsisError):
        build_fake_story_bible(file)


def test_unsupported_extension_and_linked_input_refused(tmp_path):
    source = _synopsis(tmp_path)
    wrong = tmp_path / "story.md"
    wrong.write_bytes(source.read_bytes())
    with pytest.raises(FakeSynopsisError, match="regular"):
        build_fake_story_bible(wrong)
    linked = tmp_path / "linked.txt"
    linked.symlink_to(source)
    with pytest.raises(FakeSynopsisError, match="symlink"):
        build_fake_story_bible(linked)


def test_output_symlink_and_invalid_parent_refused(tmp_path):
    source = _synopsis(tmp_path)
    result = build_fake_story_bible(source)
    target = tmp_path / "existing.json"
    target.write_text("protected")
    linked = tmp_path / "linked.json"
    linked.symlink_to(target)
    with pytest.raises(FakeSynopsisError):
        write_fake_story_bible(result, linked)
    with pytest.raises(FakeSynopsisError, match="existing"):
        write_fake_story_bible(result, target)
    with pytest.raises(FakeSynopsisError, match="directory"):
        write_fake_story_bible(result, tmp_path / "missing-dir" / "bible.json")
    assert target.read_text() == "protected"


def test_empty_output_is_not_created_on_input_error(tmp_path):
    source = tmp_path / "too_large.txt"
    source.write_bytes(b"A" * (MAX_BRIEF_BYTES + 1))
    target = tmp_path / "not_written.json"
    with pytest.raises(SystemExit) as exc:
        main([str(source), "--output", str(target)])
    assert exc.value.code == 2
    assert not target.exists()
