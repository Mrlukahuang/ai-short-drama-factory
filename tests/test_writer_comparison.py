"""No-key preparation and meaningful rejection checks for G4/R4.1."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "writer_comparison", Path(__file__).resolve().parents[1]
    / "scripts/prepare_writer_comparison.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def candidate():
    return {
        "schema_version": "screenplay.zh.v1", "series_id": "comparison-fixture",
        "story_bible_id": "comparison-bible", "episode_number": 1,
        "episode_title": "测试占位，不是模型生成", "target_duration_seconds": 60,
        "hook": "占位钩子", "ending_cliffhanger": "占位悬念",
        "shots": [{"shot_id": str(i), "duration_seconds": 10,
                   "action": "仅作结构测试", "camera": "固定",
                   "character_ids": ["a-jie", "xiao-yu"], "scene_id": "cafe",
                   "dialogue": [], "continuity_start": "占位状态",
                   "continuity_end": "占位状态"} for i in range(6)],
    }


def test_prepare_has_identical_inputs_per_case_and_no_execution(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("Network forbidden in preparation")
    monkeypatch.setattr(socket, "socket", forbidden)
    packet = module.prepare_packet()
    assert packet == module.prepare_packet()
    assert len(packet["jobs"]) == 18
    assert len({(j["case_id"], j["model"], j["replicate"])
                for j in packet["jobs"]}) == 18
    assert packet["paid_api_calls"] == packet["model_calls"] == 0
    assert packet["budget_authorized"] is False
    assert packet["approval_granted"] is False
    assert {j["case_id"] for j in packet["jobs"]} == {
        c["case_id"] for c in packet["cases"]}


@pytest.mark.parametrize("change", ["timeline", "speaker", "actor", "scene",
                                    "series", "hook", "continuity", "shot_length"])
def test_rejects_invalid_candidates_without_approving(change):
    raw = candidate()
    shot = raw["shots"][0]
    if change == "timeline": shot["duration_seconds"] = 9
    if change == "speaker":
        shot["dialogue"] = [{"speaker_actor_id": "intruder", "text": "你好"}]
    if change == "actor": shot["character_ids"] = ["intruder"]
    if change == "scene": shot["scene_id"] = "other"
    if change == "series": raw["series_id"] = "other"
    if change == "hook": raw["hook"] = " "
    if change == "continuity": shot["continuity_start"] = " "
    if change == "shot_length":
        shot["duration_seconds"] = 11
        raw["shots"][1]["duration_seconds"] = 9
    report = module.check_candidate("misunderstanding", raw)
    assert report["structural_pass"] is False
    assert report["approval_granted"] is False
    assert report["semantic_continuity"] == "not_assessed"


def test_valid_structure_is_not_semantic_or_human_approval():
    report = module.check_candidate("misunderstanding", candidate())
    assert report["structural_pass"] is True
    assert report["semantic_continuity"] == "not_assessed"
    assert report["approval_granted"] is False


def test_cli_create_only_and_local_validation(tmp_path):
    out = tmp_path / "packet.json"
    assert module.main(["--out", str(out)]) == 0
    with pytest.raises(FileExistsError):
        module.main(["--out", str(out)])
    source = tmp_path / "candidate.json"
    source.write_text(json.dumps(candidate()), encoding="utf-8")
    report = tmp_path / "report.json"
    assert module.main(["--out", str(report), "--case", "reversal",
                        "--candidate-json", str(source)]) == 0
    assert json.loads(report.read_text())["approval_granted"] is False
