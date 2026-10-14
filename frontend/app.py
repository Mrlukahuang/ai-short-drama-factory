"""Local multi-column Streamlit console; no authentication, DO NOT expose publicly."""
import json
import os
import requests
import streamlit as st
from pathlib import Path

from drama_factory.db import Database
from drama_factory.pipeline.offline_render import PreviewError, render_approved_preview
from drama_factory.pipeline.offline_review import LocalReviewDenied, load_local_offline_review

API = os.getenv("DRAMA_FACTORY_API", "http://127.0.0.1:8000")
st.set_page_config(page_title="AI 短剧工厂", layout="wide")
st.title("🎬 AI 短剧工厂 · 栏目 / 剧集管理")
st.caption("离线原型：人物与场景已按剧集隔离；尚未调用付费模型或生成可播放视频。")


def json_request(method, url, **kwargs):
    try:
        response = requests.request(method, API + url, timeout=120, **kwargs)
        if not response.ok:
            st.error(f"API {response.status_code}: {response.text[:800]}")
            return None
        return response.json()
    except requests.RequestException as exc:
        st.error(f"API 不可用：{exc}")
        return None


columns = json_request("GET", "/api/v1/columns") or []
column_names = {c["id"]: f'{c["name"]} · {c["slug"]}' for c in columns}
selected_column = st.sidebar.selectbox(
    "当前栏目", list(column_names), format_func=lambda cid: column_names[cid],
    key="selected_column") if columns else None
st.sidebar.caption("每个栏目拥有独立剧集；人物、场景和声线默认不能跨剧引用。")

column_tab, original_tab, novel_tab, project_tab, review_tab, model_tab = st.tabs(
    ["栏目管理", "原创短剧", "小说导入（独立端口）", "资产与生产任务", "本机审片", "模型注册表"])

with column_tab:
    st.subheader("栏目总览")
    if columns:
        st.dataframe(columns, use_container_width=True)
    with st.form("create_column", clear_on_submit=True):
        st.markdown("#### 创建栏目")
        slug = st.text_input("栏目标识（英文、小写，不可重复）", placeholder="romance")
        name = st.text_input("栏目名称", placeholder="都市情感")
        description = st.text_area("栏目定位 / 默认创作规则")
        style = st.selectbox("栏目默认风格", ["live_action", "anime_2d", "animation_3d"])
        if st.form_submit_button("新建栏目"):
            result = json_request("POST", "/api/v1/columns", json={
                "slug": slug, "name": name, "description": description,
                "default_visual_style": style})
            if result:
                st.success(f"栏目 {name} 已创建")
                st.rerun()

with original_tab:
    st.subheader("创建原创剧集")
    if selected_column:
        st.caption(f"归属栏目：{column_names[selected_column]}。每部剧集有独立人物和场景资产。")
        title = st.text_input("剧集名称", "都市情感短剧试验")
        premise = st.text_area("故事梗概", "男女主因一场误会重逢。")
        selected_style = next(c["default_visual_style"] for c in columns if c["id"] == selected_column)
        style = st.selectbox("视觉风格", ["live_action", "anime_2d", "animation_3d"],
                             index=["live_action", "anime_2d", "animation_3d"].index(selected_style))
        if st.button("在当前栏目创建剧集"):
            result = json_request("POST", f"/api/v1/columns/{selected_column}/series",
                                  json={"title": title, "premise": premise, "visual_style": style})
            if result:
                st.success("剧集已创建")
                st.json(result)
    else:
        st.info("请先创建一个栏目。")

with novel_tab:
    st.subheader("上传小说 / 版权改编素材")
    st.info("独立小说入口，目前只在本地解析和索引。取得影视改编权之前不启动改编任务、不发送给模型。")
    st.caption("后续会加入：选定目标栏目及剧集 → 事件图 → 分集规划 → 剧本审核。")
    book = st.file_uploader("TXT / MD / EPUB / DOCX / PDF（限 20 MiB）", type=["txt","md","epub","docx","pdf"])
    book_title = st.text_input("作品名称")
    rights = st.selectbox("版权状态", ["pending","owned","licensed"],
        format_func=lambda v: {"pending":"待确认","owned":"本人原创并持有改编权","licensed":"已取得改编授权"}[v])
    rights_ref = st.text_input("授权凭据 / 合同编号（购买版权时填写）")
    adaptation_grant = st.checkbox("我确认拥有或已获授予影视改编权（screen_adaptation）")
    if st.button("上传并读取章节", disabled=book is None or not book_title.strip()):
        uploaded = json_request("POST", "/api/v1/novels/upload",
            data={"title":book_title,"rights_status":rights,"rights_reference":rights_ref,
                  "rights_scope":"screen_adaptation" if adaptation_grant else ""},
            files={"file": (book.name, book.getvalue())})
        if uploaded:
            st.success(f"已建立作品记录，识别 {uploaded['chapter_count']} 个章节")
            st.session_state['source_id'] = uploaded['source_id']
            st.json(uploaded)
    source_id = st.text_input("已有作品 Source ID", value=st.session_state.get('source_id', ''))
    if source_id and st.button("查看章节索引"):
        chapters = json_request("GET", f"/api/v1/novels/{source_id}/chapters")
        if chapters is not None:
            st.dataframe(chapters, use_container_width=True)
    st.markdown("#### 后续改编任务端口（当前只登记，不自动拆集）")
    episodes = st.number_input("希望拆分的集数", 1, 300, 20)
    seconds = st.number_input("每集目标秒数", 30, 1800, 90)
    if source_id and st.button("登记改编任务"):
        result = json_request("POST", f"/api/v1/novels/{source_id}/adaptation-jobs",
            json={"desired_episodes":episodes,"target_seconds_per_episode":seconds,
                  "visual_style":"live_action"})
        if result:
            st.json(result)

with project_tab:
    st.subheader("当前栏目剧集、角色与场景")
    if selected_column:
        series = json_request("GET", f"/api/v1/columns/{selected_column}/series") or []
        if series:
            st.dataframe(series, use_container_width=True)
            series_names = {s["id"]: s["title"] for s in series}
            series_id = st.selectbox("选中剧集", list(series_names), format_func=lambda sid: series_names[sid])
            assets = json_request("GET", f"/api/v1/series/{series_id}/assets")
            if assets is not None:
                st.markdown("#### 已登记资产版本")
                st.dataframe(assets, use_container_width=True)
            with st.form("create_asset", clear_on_submit=True):
                st.markdown("#### 追加演员 / 场景版本")
                kind = st.selectbox("资产类型", ["actor", "scene", "voice", "prop"])
                asset_key = st.text_input("资产标识", placeholder="female_lead")
                example = '{"name":"女主","appearance":"黑长发","identity_anchors":["左眉痣"]}'
                specification = st.text_area("设定 JSON", value=example,
                    help="actor: name/appearance/identity_anchors; scene: name/location/layout; voice: name/voice_description")
                if st.form_submit_button("保存新版本"):
                    try:
                        data = json.loads(specification)
                    except json.JSONDecodeError as exc:
                        st.error(f"JSON 无法解析：{exc}")
                    else:
                        created = json_request("POST", f"/api/v1/series/{series_id}/assets",
                            json={"kind":kind, "key":asset_key, "specification":data})
                        if created:
                            st.success(f"已保存 {kind} v{created['version']}")
                            st.json(created)
            productions = json_request("GET", "/api/v1/productions", params={"series_id":series_id})
            if productions is not None:
                st.markdown("#### 当前剧集生产任务")
                st.dataframe(productions, use_container_width=True)
        else:
            st.info("当前栏目暂无剧集，可在『原创短剧』创建。")
    st.caption("真实并发调度、预算控制和跨剧共享授权将在后续 PR 实现；当前不执行视频模型。")

with review_tab:
    st.subheader("🎞️ 本机离线审片工作台")
    st.warning("仅在本机使用：不包含用户认证、网络文件分发或发行审批。预览为占位画面和本地合成测试音，不是真实 AI 短剧。")
    st.caption("仅接收当前栏目下已登记的剧集/Production；播放前会重新核验 MP4 SHA256、所有镜头缓存、字幕轨、完整音视频解码。零付费模型请求。")
    local_data = Path(os.getenv("DRAMA_FACTORY_DATA_DIR", "./data")).expanduser().resolve()
    review_root = Path(os.getenv(
        "DRAMA_OFFLINE_RENDER_ROOT", "./artifacts/offline-reviews",
    )).expanduser().resolve()
    local_db_file = local_data / "factory.sqlite3"
    if not selected_column:
        st.info("请先选中栏目。")
    elif not local_db_file.is_file():
        st.info("未找到本机 factory.sqlite3。请确保 Streamlit 与 API 使用相同的 DRAMA_FACTORY_DATA_DIR。")
    else:
        review_series = json_request("GET", f"/api/v1/columns/{selected_column}/series") or []
        if not review_series:
            st.info("当前栏目还没有剧集。")
        else:
            review_names = {s["id"]: s["title"] for s in review_series}
            review_series_id = st.selectbox(
                "选中待审剧集", list(review_names),
                format_func=lambda sid: review_names[sid], key="offline_review_series",
            )
            review_runs = json_request(
                "GET", "/api/v1/productions", params={"series_id": review_series_id},
            ) or []
            if not review_runs:
                st.info("还没有 Production。请先提交剧本并完成剧本、人物审核。")
            else:
                runs = {p["id"]: p for p in review_runs}
                run_id = st.selectbox(
                    "选择 Production", list(runs),
                    format_func=lambda rid: f'{rid} · {runs[rid]["status"]}',
                    key="offline_review_run",
                )
                status = runs[run_id]["status"]
                st.caption(f"当前状态：{status}。只有完成审核的 Production 才可渲染；预览不会批准发行。")
                local_db = Database(local_db_file)
                if st.button(
                    "生成 / 更新已审核的离线 MP4",
                    disabled=status not in ("ready_for_video_generation", "offline_preview_finished"),
                ):
                    try:
                        scoped = local_db.one(
                            """SELECT e.project_id FROM productions p
                               JOIN episodes e ON p.episode_id=e.id WHERE p.id=?""",
                            (run_id,),
                        )
                        if scoped is None or scoped["project_id"] != review_series_id:
                            raise LocalReviewDenied("当前 Production 不属于所选剧集")
                        render_approved_preview(local_db, run_id, review_root)
                        st.success("离线 MP4 渲染及独立技术 QA 已通过。可以复核并播放。")
                    except (PreviewError, LocalReviewDenied, OSError, ValueError):
                        st.error("预览渲染失败或审核条件不满足；没有启用付费生成。")
                # Never trust a DB manifest filename as a path for Streamlit:
                # playback is opened only by the local read-only verifier.
                if status == "offline_preview_finished" or st.button("复核本机已完成的样片"):
                    try:
                        report = load_local_offline_review(
                            local_db, run_id, review_root, series_id=review_series_id,
                        )
                    except LocalReviewDenied:
                        st.info("尚无可播放、可校验的本机样片。渲染后刷新页面，或检查本机路径。")
                    else:
                        st.video(report["preview_path"])
                        st.caption(
                            f'已验证时长 {report["duration_seconds"]:.1f}s · '
                            f'镜头 {len(report["shots"])} · '
                            f'本地素材镜头 {report["actual_local_media_clips"]}'
                        )
                        if report["placeholder_visuals"]:
                            st.warning("含占位镜头；不可当作真实影视画面发布。")
                        st.dataframe(report["shots"], use_container_width=True)
                        st.caption("技术 QA 合格 ≠ 内容、版权、声音或发布审核合格。")
    st.caption("生产部署前必须先完善身份认证、角色权限和私有媒体访问控制。本界面禁止公网暴露。")

with model_tab:
    model_config = json_request("GET", "/api/v1/models")
    if model_config:
        st.json(model_config)