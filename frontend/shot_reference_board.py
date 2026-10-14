"""Streamlit local draft shot reference picker with side-by-side comparison.

No cloud media, model upload, production approval or AI quality assertion.
"""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from drama_factory.db import Database
from drama_factory.pipeline.local_asset_references import (
    LocalReferenceError, list_local_asset_references,
)
from drama_factory.pipeline.shot_reference_board import (
    LocalShotReferenceError, build_shot_reference_board,
    save_shot_reference_selection,
)
from drama_factory.pipeline.screenplay import Screenplay


def show_shot_reference_board(raw_draft: dict, series_id: str,
                              all_assets: list[dict]) -> None:
    with st.expander("逐镜参考图选择 · 相邻镜头对照（本机）", expanded=False):
        st.caption(
            "这里只管理已应用草稿的人工参考选择，不会更改剧本、批准角色或发送图片给任何 AI。"
            "剧本哪怕只修改一句对白，旧选择也不会自动沿用。"
        )
        root = Path(os.getenv("DRAMA_FACTORY_DATA_DIR", "./data")).expanduser().resolve()
        db_file = root / "factory.sqlite3"
        if not db_file.is_file():
            st.info("当前没有本机 factory.sqlite3，请使用与本机 API 相同的数据目录。")
            return
        try:
            draft = Screenplay.model_validate(raw_draft).model_dump(mode="json")
            if draft["series_id"] != series_id:
                raise LocalShotReferenceError("Selected draft series differs")
            db = Database(db_file)
            board = build_shot_reference_board(
                db, draft, root / "local-asset-references",
                root / "local-shot-references",
            )
        except (ValueError, LocalShotReferenceError, OSError):
            st.error("当前草稿或参考图绑定状态不完整，无法安全加载导演参考板。")
            return
        shots = board["shots"]
        asset_map = {a["id"]: a for a in all_assets}
        shot_keys = [s["shot_id"] for s in shots]
        chosen = st.selectbox(
            "当前镜头", shot_keys,
            key=f'shotref_shot_{board["screenplay_fingerprint"]}',
        )
        pos = shot_keys.index(chosen)
        shot = shots[pos]
        target_ids = list(shot["actor_ids"])
        if shot["scene_id"]:
            target_ids.append(shot["scene_id"])
        props = {
            aid: a for aid, a in asset_map.items()
            if a["kind"] == "prop"
        }
        # Only fetch locally verified images. An invalid image must not be
        # offered as a choice or shown as a supposedly verified reference.
        gallery = {}
        try:
            for aid in target_ids + list(props):
                if aid not in asset_map:
                    raise LocalShotReferenceError("Unknown selected asset")
                gallery[aid] = list_local_asset_references(
                    db, series_id, aid, root / "local-asset-references",
                )
        except (LocalReferenceError, LocalShotReferenceError, OSError):
            st.error("某资产参考图完整性核验失败，请先在资产图库修复。")
            return
        st.caption("无参考图的资产仍可参与剧本，但本次视觉对照将显示缺失。")
        if not any(gallery.values()):
            st.info("当前镜头及道具尚无本机参考图。请先到「资产与生产任务」登记。")
            return
        chosen_props = st.multiselect(
            "当前镜头额外出现的道具（仅导演注释，不进入已审批 Screenplay）",
            list(props),
            default=[aid for aid in shot["reference_selection"] if aid in props],
            format_func=lambda aid: f'{props[aid]["asset_key"]} v{props[aid]["version"]}',
            max_selections=4,
            key=f'shotref_props_{board["screenplay_fingerprint"]}_{chosen}',
        )
        selected = {}
        for aid in target_ids + list(chosen_props):
            asset = asset_map[aid]
            choices = gallery[aid]
            old = shot["reference_selection"].get(aid)
            hashes = [None, *[item["source_sha256"] for item in choices]]
            default_idx = hashes.index(old) if old in hashes else 0
            pick = st.selectbox(
                f'{asset["kind"]}: {asset["asset_key"]} v{asset["version"]}',
                hashes, index=default_idx,
                format_func=lambda value: (
                    "未指定" if value is None else
                    f'图片 {value[:12]}…'
                ),
                key=f'shotref_pick_{board["screenplay_fingerprint"]}_{chosen}_{aid}',
            )
            if pick is not None:
                selected[aid] = pick
                image = next(x for x in choices if x["source_sha256"] == pick)
                st.image(image["png_bytes"], width=175)
        confirm = st.checkbox(
            "我已亲自核对这一个镜头的参考选择；此操作不等于版权、角色或商业发布审批。",
            key=f'shotref_confirm_{board["screenplay_fingerprint"]}_{chosen}',
        )
        if st.button(
            "保存这个镜头的参考选择（含清空）", disabled=not confirm,
            key=f'shotref_save_{board["screenplay_fingerprint"]}_{chosen}',
        ):
            try:
                saved = save_shot_reference_selection(
                    db, draft, chosen, selected,
                    root / "local-asset-references",
                    root / "local-shot-references",
                    operator_confirmed=confirm,
                )
                st.success(
                    f'已为 {saved["shot_id"]} 记录 '
                    f'{saved["selection_count"]} 个本机人工参考选择。'
                )
                st.rerun()
            except (LocalShotReferenceError, OSError):
                st.error("参考选择保存失败：资产/剧本指纹/图像完整性不满足要求。")

        st.markdown("#### 相邻镜头参考对照（只读）")
        left_idx = max(0, pos - 1)
        right_idx = min(len(shots) - 1, pos + 1)
        indices = [left_idx, pos] if pos > 0 else [pos, right_idx]
        columns = st.columns(2)
        for col, idx in zip(columns, indices):
            entry = shots[idx]
            with col:
                st.markdown(f'**镜头 {entry["shot_id"]}**')
                if entry["reference_images"]:
                    for ref in entry["reference_images"]:
                        a = asset_map.get(ref["asset_id"])
                        label = (
                            f'{a["kind"]}: {a["asset_key"]} v{a["version"]}'
                            if a else f'资产 {ref["asset_id"][-6:]}'
                        )
                        st.caption(label + f' · {ref["source_sha256"][:10]}…')
                        st.image(ref["png_bytes"], use_container_width=True)
                else:
                    st.caption("尚无明确保存的参考图片")
        if board["review_prompts"]:
            st.warning(
                f'有 {len(board["review_prompts"])} 处相邻镜头参考选择不同或缺失，'
                "需要导演人工检查；换装/切场可能完全正常。"
            )
            st.dataframe([
                {
                    "前镜": q["from_shot"], "后镜": q["to_shot"],
                    "资产": (asset_map[q["asset_id"]]["asset_key"]
                           if q["asset_id"] in asset_map else q["asset_id"][-6:]),
                    "提示": q["message"],
                }
                for q in board["review_prompts"]
            ], use_container_width=True, hide_index=True)
        else:
            st.caption("没有发现参考选择差异，但不代表服装/脸型/道具连续性已审核。")
        st.warning(
            "仅本机操作员自行登记的图像，绝不代表人物肖像、版权或模型使用权已独立核验；"
            "没有用户鉴权和媒体隔离，严禁公网部署。"
        )
