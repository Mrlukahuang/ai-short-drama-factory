"""G4/R4.1 offline comparison packet. No SDK, network, database or approvals."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from drama_factory.pipeline.screenplay import Screenplay
from drama_factory.pipeline.writer_execution_prep import prepare_request
from drama_factory.pipeline.text import (
    DRAMA_PROMPT_VERSION, ScriptContext, ScriptPlanRequest, build_drama_writer_prompt,
)

MODELS = ("gpt-6.1-sol", "gpt-6-luna", "gemini-3.8-flash")
CASES = (
    ("misunderstanding", "误会喜剧：阿杰把小雨留在桌上的空杯误认作差评暗号。"
     "用可见行动逐步升级误会，再用此前已露出的线索解开；结尾留下新问题。"),
    ("reversal", "伏笔反转：小雨发现阿杰藏起了写有今天日期的信封，以为店要关闭。"
     "信封实际与阿杰为咖啡店准备的小惊喜有关。开场铺公平线索，"
     "不靠第三人或突然出现的信息解决冲突，结尾留下下一集悬念。"),
    ("prop_continuity", "道具接续：开场阿杰在画面左侧，右手持唯一的奶油色空杯；"
     "小雨在右侧，双手空着。杯子必须经一次清楚可见的桌面放置与拿取交给小雨。"
     "围绕杯底藏着的短留言产生冲突和反转；不瞬移、不增杯，不变服装。"),
)


def case_inputs(case_id: str) -> tuple[ScriptPlanRequest, ScriptContext]:
    brief = dict(CASES)[case_id]
    context = ScriptContext(
        series_id="comparison-fixture", story_bible_id="comparison-bible",
        story_bible_json={
            "title": "雨棚下的两个人",
            "canon": "原创测试资料。奥克兰绿色雨棚咖啡店内，两位非真人毛毡玩偶；"
                     "只有阿杰和小雨出场，不新增角色、地点或超自然能力。",
            "characters": {
                "a-jie": "阿杰：森林绿围裙、米色上衣，热心但怕丢脸，常用短句掩饰紧张。",
                "xiao-yu": "小雨：淡黄外套，观察细致、直接，轻微调侃，不替观众解释一切。",
            },
            "relationship": "两人共同经营小店，互相关心但都不愿先承认。",
            "scene": "唯一场景 cafe：暖光，桌在中央，不越过两人的对话轴线。",
        },
        allowed_actor_ids=["a-jie", "xiao-yu"], allowed_scene_id="cafe",
    )
    request = ScriptPlanRequest(
        story_bible_id=context.story_bible_id, episode_number=1,
        target_duration_seconds=60, creative_brief=brief,
        actor_asset_ids=context.allowed_actor_ids, scene_asset_id="cafe",
        prompt_version=DRAMA_PROMPT_VERSION,
    )
    return request, context


def prepare_packet() -> dict:
    """Prepare common semantic inputs, not vendor-specific API requests."""
    cases = []
    for case_id, _ in CASES:
        request, context = case_inputs(case_id)
        cases.append({"case_id": case_id, "request": request.model_dump(mode="json"),
                      "context": context.model_dump(mode="json"),
                      **build_drama_writer_prompt(request, context)})
    schema = Screenplay.model_json_schema()
    schema_json = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    return {
        "status": "plan_only", "model_calls": 0, "paid_api_calls": 0,
        "approval_granted": False, "production_assets_verified": False,
        "models_are_candidates_only": True,
        "proposed_total_budget_usd": "2.00", "budget_authorized": False,
        "schema": schema,
        "schema_sha256": hashlib.sha256(schema_json.encode()).hexdigest(),
        "cases": cases,
        "jobs": [{"case_id": case_id, "model": model, "thinking": "medium",
                  "replicate": repeat, "status": "pending_authorization"}
                 for case_id, _ in CASES for model in MODELS for repeat in (1, 2)],
    }


def check_candidate(case_id: str, raw: dict) -> dict:
    """Local structural checks only; never approves or invokes a model.

    Pydantic covers timeline, cue slots and visible speakers. These extra
    comparisons bind fixture IDs and the narrower R4.2 prompt constraints.
    Natural-language continuity remains explicitly unassessed.
    """
    request, context = case_inputs(case_id)
    errors = []
    try:
        screenplay = Screenplay.model_validate(raw)
    except ValueError as exc:
        return {"structural_pass": False, "errors": [str(exc)],
                "semantic_continuity": "not_assessed", "approval_granted": False}
    expected = {"series_id": context.series_id, "story_bible_id": context.story_bible_id,
                "episode_number": request.episode_number,
                "target_duration_seconds": request.target_duration_seconds}
    for key, value in expected.items():
        if getattr(screenplay, key) != value:
            errors.append(f"{key}: fixture mismatch")
    for key in ("hook", "ending_cliffhanger"):
        if not getattr(screenplay, key).strip():
            errors.append(f"{key}: blank")
    visible = set()
    for shot in screenplay.shots:
        visible.update(shot.character_ids)
        if not set(shot.character_ids).issubset(set(request.actor_asset_ids)):
            errors.append(f"{shot.shot_id}: unknown actor")
        if shot.scene_id != request.scene_asset_id:
            errors.append(f"{shot.shot_id}: scene mismatch")
        if not 3 <= shot.duration_seconds <= 10:
            errors.append(f"{shot.shot_id}: duration outside 3-10 seconds")
        if not shot.continuity_start.strip() or not shot.continuity_end.strip():
            errors.append(f"{shot.shot_id}: blank continuity")
    if visible != set(request.actor_asset_ids):
        errors.append("Both selected leads must appear in the episode")
    return {"structural_pass": not errors, "errors": errors,
            "semantic_continuity": "not_assessed", "approval_granted": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--candidate-json", type=Path)
    parser.add_argument("--case", choices=[key for key, _ in CASES])
    parser.add_argument("--wire-requests", action="store_true",
                        help="Export offline vendor payloads; never sends requests")
    args = parser.parse_args(argv)
    if bool(args.candidate_json) != bool(args.case):
        parser.error("--candidate-json and --case are required together")
    if args.wire_requests and args.candidate_json:
        parser.error("--wire-requests cannot be combined with candidate validation")
    if args.candidate_json:
        source = args.candidate_json
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 1048576:
            raise ValueError("Candidate must be a regular local JSON file <=1 MiB")
        raw = json.loads(source.read_text(encoding="utf-8"))
        result = check_candidate(args.case, raw)
    else:
        result = prepare_packet()
        if args.wire_requests:
            result["wire_requests"] = []
            for job in result["jobs"]:
                prepared = prepare_request(job["model"], *case_inputs(job["case_id"]))
                result["wire_requests"].append({
                    "job_id": f'{job["case_id"]}/{job["model"]}/{job["replicate"]}',
                    "endpoint": prepared.endpoint, "payload": json.loads(prepared.payload_json),
                    "request_sha256": prepared.fingerprint,
                    "budget_bound_status": "missing_verified_evidence",
                })
            result["execution_authorized"] = False
            result["transport_available"] = False
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return 1 if result.get("structural_pass") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
