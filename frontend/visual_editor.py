"""Local-only visual screenplay form; never executes API requests or approvals.

Run only from localhost Streamlit. The caller owns JSON session persistence.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from drama_factory.pipeline.local_story_workflow import (
    LocalStoryWizardError, apply_visual_storyboard,
)
from drama_factory.pipeline.screenplay import Screenplay


def show_visual_storyboard(raw_json: str, actor_names: dict[str, str],
                           scene_names: dict[str, str], *,
                           form_key: str) -> dict | None:
    """Return edited draft ONLY after Apply. No automatic persistence/review."""
    try:
        draft = Screenplay.model_validate(json.loads(raw_json)).model_dump(mode="json")
    except (ValueError, TypeError):
        st.warning("当前 JSON 未通过结构校验；请在高级编辑器里修复再使用逐镜表单。")
        return None
    labels = {aid: f"{name} · {aid[-6:]}" for aid, name in actor_names.items()}
    reverse_labels = {label: aid for aid, label in labels.items()}
    with st.expander("逐镜头可视化编辑（推荐）", expanded=True):
        with st.form(form_key):
            episode_number = st.number_input(
                "分集编号", min_value=1, max_value=999,
                value=draft["episode_number"], step=1,
            )
            episode_title = st.text_input(
                "分集标题", value=draft["episode_title"],
            )
            hook = st.text_area("开头钩子", value=draft["hook"], height=72)
            ending = st.text_area(
                "结尾悬念", value=draft["ending_cliffhanger"], height=72,
            )
            edited_shots = []
            for i, shot in enumerate(draft["shots"], start=1):
                with st.expander(
                    f'镜头 {i:02d} · {shot["shot_id"]} · {shot["duration_seconds"]} 秒',
                    expanded=i == 1,
                ):
                    st.caption("镜头 ID 保持不变；所有角色和场景来自当前剧集的已登记版本。")
                    seconds = st.number_input(
                        "镜头时长（秒）", min_value=1, max_value=30,
                        value=shot["duration_seconds"], step=1, key=f"{form_key}_seconds_{i}",
                    )
                    action = st.text_area(
                        "动作／画面", value=shot["action"], height=86,
                        key=f"{form_key}_action_{i}",
                    )
                    camera = st.text_input(
                        "摄影方式", value=shot["camera"], key=f"{form_key}_camera_{i}",
                    )
                    cast = st.multiselect(
                        "出镜演员", list(actor_names),
                        default=[x for x in shot["character_ids"] if x in actor_names],
                        format_func=lambda aid: actor_names[aid],
                        key=f"{form_key}_cast_{i}",
                    )
                    scene_options = [None, *scene_names]
                    scene = st.selectbox(
                        "场景", scene_options,
                        index=scene_options.index(shot["scene_id"])
                        if shot["scene_id"] in scene_options else 0,
                        format_func=lambda sid: scene_names.get(sid, "不指定场景"),
                        key=f"{form_key}_scene_{i}",
                    )
                    start = st.text_input(
                        "开镜连续性", value=shot["continuity_start"],
                        key=f"{form_key}_continuity_start_{i}",
                    )
                    end = st.text_input(
                        "收镜连续性", value=shot["continuity_end"],
                        key=f"{form_key}_continuity_end_{i}",
                    )
                    st.caption(
                        "对白表格可新增/删除行。可留空全部时间实现自动均分，"
                        "或每句同时填写开始和结束整秒；说话角色必须在当前镜头演员中。"
                    )
                    rows = pd.DataFrame([
                        {
                            "说话角色": labels.get(cue["speaker_actor_id"], ""),
                            "对白": cue["text"],
                            "起点秒": cue["start_second"],
                            "终点秒": cue["end_second"],
                        }
                        for cue in shot["dialogue"]
                    ], columns=["说话角色", "对白", "起点秒", "终点秒"])
                    changed = st.data_editor(
                        rows, num_rows="dynamic", hide_index=True,
                        use_container_width=True,
                        column_config={
                            "说话角色": st.column_config.SelectboxColumn(
                                "说话角色", options=list(labels.values()), required=True,
                            ),
                            "对白": st.column_config.TextColumn("对白", required=True),
                            "起点秒": st.column_config.NumberColumn(
                                "起点秒", min_value=0, step=1, format="%d",
                            ),
                            "终点秒": st.column_config.NumberColumn(
                                "终点秒", min_value=1, step=1, format="%d",
                            ),
                        }, key=f"{form_key}_cue_{i}",
                    )
                    cues = []
                    for row in changed.to_dict("records"):
                        begin, finish = row["起点秒"], row["终点秒"]
                        begin = None if pd.isna(begin) else begin
                        finish = None if pd.isna(finish) else finish
                        if isinstance(begin, float) and begin.is_integer():
                            begin = int(begin)
                        if isinstance(finish, float) and finish.is_integer():
                            finish = int(finish)
                        # Preserve each row; invalid speaker/time/text fails
                        # pure Pydantic checks, never silently remove dialogue.
                        cues.append({
                            "speaker_actor_id": reverse_labels.get(row["说话角色"]),
                            "text": row["对白"], "start_second": begin,
                            "end_second": finish,
                        })
                    edited_shots.append({
                        "shot_id": shot["shot_id"], "duration_seconds": seconds,
                        "action": action, "camera": camera,
                        "character_ids": cast, "scene_id": scene,
                        "dialogue": cues, "continuity_start": start,
                        "continuity_end": end,
                    })
            st.caption(
                f"镜头总时长：{sum(s['duration_seconds'] for s in edited_shots)} 秒"
                "（本机技术预览上限 90 秒，保存后仍须服务器校验、人工提交和分级审批）。"
            )
            apply = st.form_submit_button("应用修改到草稿（不提交、不生成）")
        if apply:
            try:
                return apply_visual_storyboard(
                    draft, episode_number=episode_number, episode_title=episode_title,
                    hook=hook, ending_cliffhanger=ending, edited_shots=edited_shots,
                    allowed_actor_ids=list(actor_names),
                    allowed_scene_ids=list(scene_names),
                )
            except LocalStoryWizardError:
                st.error(
                    "镜头、总时长、演员、场景或对白时间不合法；"
                    "原草稿及人工审核结果没有改变。"
                )
    return None
