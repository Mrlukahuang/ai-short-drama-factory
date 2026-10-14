"""Local-only visual screenplay form; never executes API requests or approvals.

Run only from localhost Streamlit. The caller owns JSON session persistence.
"""
from __future__ import annotations

import json

import altair as alt
import pandas as pd
import streamlit as st

from drama_factory.pipeline.director_timeline import (
    DirectorTimelineError, director_timeline,
)

from drama_factory.pipeline.local_story_workflow import (
    LocalStoryWizardError, apply_visual_storyboard,
)
from drama_factory.pipeline.screenplay import Screenplay



def show_director_timeline(draft: dict, actors: dict[str, str],
                           scenes: dict[str, str]) -> None:
    """Read-only visualization of the last APPLIED draft, not form edits."""
    with st.expander("导演时间轴 · 镜头/对白/连续性（只读）", expanded=True):
        st.caption("仅显示已应用的草稿。以下只是文本和时间检查提示，不代表导演批准、画面无穿帮或发布许可。")
        try:
            timeline = director_timeline(draft, actor_names=actors, scene_names=scenes)
        except DirectorTimelineError:
            st.info("当前草稿不符合本机时间轴预览限制（最多 12 镜、90 秒）。")
            return
        st.caption(
            f'总时长 {timeline["duration_seconds"]} 秒 · {timeline["shot_count"]} 镜 · '
            f'{len(timeline["dialogue_cues"])} 句对白 · '
            f'{timeline["review_prompt_count"]} 条人工复查线索'
        )
        shots = pd.DataFrame(timeline["shots"])
        labels = [s["shot_label"] for s in timeline["shots"]]
        shot_chart = alt.Chart(shots).mark_bar(size=18).encode(
            x=alt.X("start_second:Q", title="全片时间（秒）",
                    scale=alt.Scale(domain=[0, timeline["duration_seconds"]])),
            x2="end_second:Q",
            y=alt.Y("shot_label:N", sort=labels, title="镜头"),
            color=alt.Color("scene_label:N", title="场景"),
            tooltip=["shot_label:N", "start_second:Q", "end_second:Q",
                     "scene_label:N", "cast_label:N", "camera:N"],
        )
        st.altair_chart(shot_chart, use_container_width=True)
        st.dataframe(
            shots[["shot_label", "start_second", "end_second", "cast_label",
                   "scene_label", "camera", "continuity_start", "continuity_end"]
            ].rename(columns={
                "shot_label": "镜头", "start_second": "开始秒", "end_second": "结束秒",
                "cast_label": "出镜演员", "scene_label": "场景", "camera": "摄影",
                "continuity_start": "开镜状态", "continuity_end": "收镜状态",
            }), use_container_width=True, hide_index=True,
        )
        if timeline["dialogue_cues"]:
            cues = pd.DataFrame(timeline["dialogue_cues"])
            cue_chart = alt.Chart(cues).mark_bar(size=12).encode(
                x=alt.X("start_second:Q", title="全片对白时间（秒）"),
                x2="end_second:Q",
                y=alt.Y("shot_label:N", sort=labels, title="镜头"),
                color=alt.Color("speaker_label:N", title="说话角色"),
                tooltip=["shot_label:N", "speaker_label:N", "text:N",
                         "timing_source:N", "start_second:Q", "end_second:Q"],
            )
            st.altair_chart(cue_chart, use_container_width=True)
            st.dataframe(
                cues[["shot_label", "speaker_label", "text", "start_second",
                      "end_second", "timing_source"]].rename(columns={
                    "shot_label": "镜头", "speaker_label": "说话人", "text": "对白",
                    "start_second": "开始秒", "end_second": "结束秒",
                    "timing_source": "时槽来源",
                }), use_container_width=True, hide_index=True,
            )
            if any(c["timing_source"].startswith("离线")
                   for c in timeline["dialogue_cues"]):
                st.info("未手动指定的对白时间，仅按本机合成规则均分；并非导演批准的配音时槽。")
        if timeline["review_prompts"]:
            st.warning(
                f'{timeline["review_prompt_count"]} 条跨镜连续性或对白时槽提示，请人工核对。'
                "正常切镜也可能触发提示。"
            )
            st.dataframe(
                pd.DataFrame(timeline["review_prompts"])[
                    ["boundary_second", "from_shot", "to_shot", "message"]
                ].rename(columns={
                    "boundary_second": "位置（秒）", "from_shot": "前镜头",
                    "to_shot": "后镜头", "message": "人工复查线索",
                }), hide_index=True, use_container_width=True,
            )
        else:
            st.caption("无规则型提示；这不等于通过人物造型、镜头轴线、版权或发布审查。")


def show_visual_storyboard(raw_json: str, actor_names: dict[str, str],
                           scene_names: dict[str, str], *,
                           form_key: str) -> dict | None:
    """Return edited draft ONLY after Apply. No automatic persistence/review."""
    try:
        draft = Screenplay.model_validate(json.loads(raw_json)).model_dump(mode="json")
    except (ValueError, TypeError):
        st.warning("当前 JSON 未通过结构校验；请在高级编辑器里修复再使用逐镜表单。")
        return None
    show_director_timeline(draft, actor_names, scene_names)
    labels = {aid: f"{name} · {aid[-6:]}" for aid, name in actor_names.items()}
    reverse_labels = {label: aid for aid, label in labels.items()}
    # Streamlit prohibits nested expanders: shot expanders live inside
    # this plain container, not inside another expander.
    with st.container(border=True):
        st.subheader("逐镜头可视化编辑（推荐）")
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
