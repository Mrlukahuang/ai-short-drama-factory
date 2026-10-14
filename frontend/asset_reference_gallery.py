"""Streamlit-only, trusted-local-machine image reference panel."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import streamlit as st

from drama_factory.db import Database
from drama_factory.pipeline.local_asset_references import (
    LocalReferenceError, MAX_SOURCE_BYTES,
    list_local_asset_references, stage_local_asset_reference,
)


def show_local_asset_reference_gallery(series_id: str, assets: list[dict]) -> None:
    """No remote API or model calls; never grants any production approval."""
    st.markdown("#### 本机人物 / 场景 / 道具参考图")
    st.caption(
        "仅在同一台本机使用，图像会缩放并重编码为不带原始 EXIF/GPS 元数据的 PNG。"
        "参考图绑定到已登记的具体资产版本，但不是独立授权证明、"
        "AI 角色一致性认证或可直接提交给模型的参考帧。"
    )
    choices = {
        a["id"]: a for a in assets
        if a["kind"] in ("actor", "scene", "prop")
    }
    if not choices:
        st.info("请先在上方登记人物、场景或道具资产版本。")
        return
    local_db_file = (
        Path(os.getenv("DRAMA_FACTORY_DATA_DIR", "./data")).expanduser().resolve()
        / "factory.sqlite3"
    )
    if not local_db_file.is_file():
        st.info("当前没有本地 factory.sqlite3；仅同机 API 数据库支持本地参考图。")
        return
    ref_root = (
        Path(os.getenv("DRAMA_FACTORY_DATA_DIR", "./data")).expanduser().resolve()
        / "local-asset-references"
    )
    asset_id = st.selectbox(
        "选择本剧资产的特定版本",
        list(choices),
        format_func=lambda aid: (
            f'{choices[aid]["kind"]} / {choices[aid]["asset_key"]} '
            f'v{choices[aid]["version"]} · {aid[-6:]}'
        ), key=f"local_ref_asset_{series_id}",
    )
    local_db = Database(local_db_file)
    upload = st.file_uploader(
        "选择本机原创或已取得使用权的参考图（JPG/PNG/WEBP，≤8 MiB）",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"local_ref_upload_{series_id}_{asset_id}",
    )
    if upload is not None:
        if upload.size > MAX_SOURCE_BYTES:
            st.error("本机参考图超过 8 MiB 上限。")
        else:
            digest = hashlib.sha256(upload.getvalue()).hexdigest()[:16]
            rights = st.checkbox(
                "我确认拥有此图的原创/使用权，且仅在本机用于当前资产版本的人工参考。",
                key=f"local_ref_rights_{series_id}_{asset_id}_{digest}",
            )
            if st.button(
                "登记参考图到此版本（不审批、不发送给模型）",
                disabled=not rights,
                key=f"local_ref_save_{series_id}_{asset_id}_{digest}",
            ):
                try:
                    receipt = stage_local_asset_reference(
                        local_db, series_id, asset_id, ref_root,
                        filename=upload.name, content=upload.getvalue(),
                        operator_attests_rights=rights,
                    )
                except (LocalReferenceError, OSError):
                    st.error("本地图片入库失败：格式、体积、版本、权限声明或图片完整性不符合要求。")
                else:
                    st.success(
                        f'已登记到 {receipt["kind"]} v{receipt["version"]}，'
                        f'原始内容哈希 {receipt["source_sha256"][:14]}…。'
                    )
    try:
        gallery = list_local_asset_references(
            local_db, series_id, asset_id, ref_root,
        )
    except (LocalReferenceError, OSError):
        st.error("本机参考图或版本收据完整性异常，禁止预览。")
        return
    if gallery:
        st.caption(f"此资产版本已登记 {len(gallery)} 张本机参考图；图片会在展示前重新进行 SHA256 验证。")
        for offset in range(0, len(gallery), 3):
            cells = st.columns(3)
            for cell, entry in zip(cells, gallery[offset:offset + 3]):
                with cell:
                    st.image(entry["png_bytes"], use_container_width=True)
                    st.caption(
                        f'{entry["width"]}×{entry["height"]} · '
                        f'v{entry["version"]} · '
                        f'{entry["png_sha256"][:12]}…'
                    )
    else:
        st.caption("此资产版本暂无本地参考图。")
    st.warning(
        "上传者的版权自述≠已核验肖像权/商业授权。当前没有账号鉴权、"
        "上传反病毒沙盒或私密媒体权限隔离，严禁公网开放。"
    )
