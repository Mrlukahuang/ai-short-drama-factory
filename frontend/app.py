"""Local multi-column Streamlit console; no authentication, DO NOT expose publicly."""
import json
import os
import requests
import streamlit as st

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

column_tab, original_tab, novel_tab, project_tab, model_tab = st.tabs(
    ["栏目管理", "原创短剧", "小说导入（独立端口）", "资产与生产任务", "模型注册表"])

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

with model_tab:
    model_config = json_request("GET", "/api/v1/models")
    if model_config:
        st.json(model_config)