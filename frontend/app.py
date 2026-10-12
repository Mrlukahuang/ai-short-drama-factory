"""Local Streamlit review console; do NOT publish unprotected to the internet."""
import os
import requests
import streamlit as st

API = os.getenv("DRAMA_FACTORY_API", "http://127.0.0.1:8000")
st.set_page_config(page_title="AI 短剧工厂", layout="wide")
st.title("🎬 AI 短剧工厂 · v0.1")
st.caption("本版只运行状态机与小说解析。不会调用付费 AI，也不会生成可播放视频。")
original_tab, novel_tab, project_tab, model_tab = st.tabs(["原创短剧", "小说导入（独立端口）", "生产任务", "模型注册表"])

def json_request(method, url, **kwargs):
    try:
        r = requests.request(method, API + url, timeout=120, **kwargs)
        if not r.ok:
            st.error(f"API {r.status_code}: {r.text[:800]}")
            return None
        return r.json()
    except requests.RequestException as e:
        st.error(f"API 不可用：{e}")
        return None

with original_tab:
    st.subheader("创建原创短剧项目")
    title = st.text_input("项目名称", "都市情感短剧试验")
    premise = st.text_area("故事梗概", "男女主因一场误会重逢。")
    style = st.selectbox("视觉风格", ["live_action", "anime_2d", "animation_3d"])
    if st.button("创建原创项目"):
        result = json_request("POST", "/api/v1/projects", json={"title":title,"premise":premise,"visual_style":style})
        if result:
            st.success("项目已创建")
            st.json(result)

with novel_tab:
    st.subheader("上传小说 / 版权改编素材")
    st.info("解析保留在本机。取得或确认影视改编权之前，不会启动改编任务或对外发送原文。")
    book = st.file_uploader("TXT / MD / EPUB / DOCX / PDF（限 20 MiB）", type=["txt","md","epub","docx","pdf"])
    book_title = st.text_input("作品名称")
    rights = st.selectbox("版权状态", ["pending","owned","licensed"], format_func=lambda v:{"pending":"待确认","owned":"本人原创并持有改编权","licensed":"已取得改编授权"}[v])
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
    st.markdown("#### 后续改编任务端口（本版只登记任务，不生成剧本）")
    episodes = st.number_input("希望拆分的集数", 1, 300, 20)
    seconds = st.number_input("每集目标秒数", 30, 1800, 90)
    if source_id and st.button("登记改编任务"):
        result = json_request("POST", f"/api/v1/novels/{source_id}/adaptation-jobs",
            json={"desired_episodes":episodes,"target_seconds_per_episode":seconds,"visual_style":"live_action"})
        if result: st.json(result)

with project_tab:
    st.subheader("原创项目与生产记录")
    if st.button("刷新项目"):
        projects = json_request("GET", "/api/v1/projects")
        if projects is not None: st.dataframe(projects, use_container_width=True)
    if st.button("刷新生产任务"):
        productions = json_request("GET", "/api/v1/productions")
        if productions is not None: st.dataframe(productions, use_container_width=True)
    st.caption("剧本、演员批准以及镜头模拟可通过 API 执行；完整审核台将在后续开发。")

with model_tab:
    model_config = json_request("GET", "/api/v1/models")
    if model_config: st.json(model_config)
