"""Read-only, bounded director timeline for LOCAL original screenplay review.

A deterministic timeline and textual continuity heuristics are not a human
sign-off, production readiness check, provider execution, or commercial QA.
Never change, write, approve or automatically correct a screenplay.
"""
from __future__ import annotations

from drama_factory.pipeline.screenplay import Screenplay


class DirectorTimelineError(ValueError):
    pass


def _same_note(left: str, right: str) -> bool:
    """Ignore harmless whitespace/case, not semantic content."""
    return " ".join(left.split()).casefold() == " ".join(right.split()).casefold()


def director_timeline(
    raw: dict, *, actor_names: dict[str, str] | None = None,
    scene_names: dict[str, str] | None = None,
) -> dict:
    """Return ordered visual spans, cue spans, and NON-BLOCKING review prompts.

    All times are integer seconds relative to the original full episode.
    Untimed dialogue is displayed using the same deterministic integer-second
    allocation as the offline renderer; these slots are NOT director-approved.
    """
    if type(raw) is not dict:
        raise DirectorTimelineError("Invalid local storyboard")
    if actor_names is not None and (
        type(actor_names) is not dict or
        any(type(k) is not str or type(v) is not str for k, v in actor_names.items())
    ):
        raise DirectorTimelineError("Invalid actor label inventory")
    if scene_names is not None and (
        type(scene_names) is not dict or
        any(type(k) is not str or type(v) is not str for k, v in scene_names.items())
    ):
        raise DirectorTimelineError("Invalid scene label inventory")
    try:
        screenplay = Screenplay.model_validate(raw)
    except (ValueError, TypeError):
        raise DirectorTimelineError("Storyboard must pass structural validation") from None
    if len(screenplay.shots) > 12 or screenplay.target_duration_seconds > 90:
        raise DirectorTimelineError("Local director preview limited to 12 shots and 90s")

    actors = actor_names or {}
    scenes = scene_names or {}
    rows: list[dict] = []
    cues: list[dict] = []
    prompts: list[dict] = []
    cursor = 0
    prev = None
    for n, shot in enumerate(screenplay.shots, 1):
        shot_start, shot_end = cursor, cursor + shot.duration_seconds
        scene_label = (
            scenes.get(shot.scene_id, shot.scene_id)
            if shot.scene_id else "未指定场景"
        )
        cast_labels = [actors.get(a, a) for a in shot.character_ids]
        label = f"{n:02d} · {shot.shot_id}"
        rows.append({
            "shot_id": shot.shot_id, "shot_label": label,
            "start_second": shot_start, "end_second": shot_end,
            "duration_seconds": shot.duration_seconds,
            "scene_id": shot.scene_id, "scene_label": scene_label,
            "cast_actor_ids": list(shot.character_ids),
            "cast_label": "、".join(cast_labels) or "无出镜演员",
            "camera": shot.camera,
            "continuity_start": shot.continuity_start,
            "continuity_end": shot.continuity_end,
        })
        if prev is not None:
            boundary = cursor
            if any(
                text.strip().startswith(("请核对", "待填写", "TODO", "TBD"))
                for text in (prev.continuity_end, shot.continuity_start)
            ):
                prompts.append({
                    "kind": "continuity_unfinished",
                    "boundary_second": boundary,
                    "from_shot": prev.shot_id, "to_shot": shot.shot_id,
                    "message": "开镜/收镜连续性仍含草稿占位内容，请人工补全并复查",
                })
            elif not _same_note(prev.continuity_end, shot.continuity_start):
                prompts.append({
                    "kind": "continuity_text_diff",
                    "boundary_second": boundary,
                    "from_shot": prev.shot_id, "to_shot": shot.shot_id,
                    "message": "上一镜收尾与下一镜起始描述文字不同，建议人工核对；并不证明穿帮",
                })
            if prev.scene_id != shot.scene_id:
                prompts.append({
                    "kind": "scene_transition",
                    "boundary_second": boundary,
                    "from_shot": prev.shot_id, "to_shot": shot.shot_id,
                    "message": "场景 ID 变化：可能是正常切场，请核对叙事连贯性",
                })
            if set(prev.character_ids) != set(shot.character_ids):
                prompts.append({
                    "kind": "cast_transition",
                    "boundary_second": boundary,
                    "from_shot": prev.shot_id, "to_shot": shot.shot_id,
                    "message": "出镜演员集合变化：可能是正常切镜，请核对人物出入场",
                })

        n_cues = len(shot.dialogue)
        if n_cues > shot.duration_seconds and shot.dialogue and shot.dialogue[0].start_second is None:
            prompts.append({
                "kind": "untimed_cue_overflow",
                "boundary_second": shot_start,
                "from_shot": shot.shot_id, "to_shot": shot.shot_id,
                "message": "未定时对白条数超过镜头整数秒数，自动均分将产生零长度时槽",
            })
        offset = 0
        for j, line in enumerate(shot.dialogue):
            approved = line.start_second is not None
            if approved:
                rel_start, rel_end = line.start_second, line.end_second
            else:
                length = shot.duration_seconds // n_cues + (
                    1 if j < shot.duration_seconds % n_cues else 0
                )
                rel_start, rel_end = offset, offset + length
                offset += length
            cues.append({
                "shot_id": shot.shot_id, "shot_label": label,
                "cue_number": j + 1,
                "speaker_actor_id": line.speaker_actor_id,
                "speaker_label": actors.get(line.speaker_actor_id, line.speaker_actor_id),
                "start_second": shot_start + rel_start,
                "end_second": shot_start + rel_end,
                "text": line.text,
                "timing_source": "导演明确填写" if approved else "离线技术均分（未经导演批准）",
            })
        cursor = shot_end
        prev = shot
    if cursor != screenplay.target_duration_seconds:
        raise DirectorTimelineError("Timeline length mismatch")
    return {
        "kind": "local_director_timeline",
        "duration_seconds": cursor,
        "shot_count": len(rows),
        "shots": rows,
        "dialogue_cues": cues,
        "review_prompts": prompts,
        "review_prompt_count": len(prompts),
        "paid_api_calls": 0,
        "read_only": True,
        "approval_granted": False,
        "publish_approved": False,
        "human_continuity_review_required": True,
    }
