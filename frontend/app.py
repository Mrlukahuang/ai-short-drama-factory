"""Local multi-column Streamlit console; no authentication, DO NOT expose publicly."""
import json
import os
import requests
import streamlit as st
from pathlib import Path

from drama_factory.db import Database
from drama_factory.pipeline.offline_render import PreviewError, render_approved_preview
from drama_factory.pipeline.offline_review import LocalReviewDenied, load_local_offline_review
from drama_factory.models import EpisodeDraft
from drama_factory.pipeline.local_shot_media import (
    LocalShotMediaError, stage_local_shot_video, get_staged_shot_clips,
)
from drama_factory.pipeline.local_story_workflow import (
    LocalStoryWizardError, make_storyboard_template,
    canonical_screenplay_digest, validated_draft_still_matches,
)
from visual_editor import show_visual_storyboard
from asset_reference_gallery import show_local_asset_reference_gallery

API = os.getenv("DRAMA_FACTORY_API", "http://127.0.0.1:8000")
st.set_page_config(page_title="AI 短剧工厂", layout="wide")
st.title("🎬 AI 短剧工厂 · 栏目 / 剧集管理")
st.caption("本机开发原型：可生成带测试画面/音效的可播放技术 MP4；没有真实 AI 视频成片，也没有启用付费模型。")


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

column_tab, original_tab, novel_tab, project_tab, script_tab, review_tab, model_tab = st.tabs(
    ["栏目管理", "原创短剧", "小说导入（独立端口）", "资产与生产任务", "分镜与审批", "本机审片", "模型注册表"])

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
            if assets is not None:
                show_local_asset_reference_gallery(series_id, assets)
        else:
            st.info("当前栏目暂无剧集，可在『原创短剧』创建。")
    st.caption("真实并发调度、预算控制和跨剧共享授权将在后续 PR 实现；当前不执行视频模型。")


with script_tab:
    st.subheader("🎬 原创分镜 → 剧本确认 → 制作审批")
    st.info("仅操作本机现有栏目与剧集。先创建 Story Bible、登记本剧角色/场景，再编辑分镜；系统只执行确定性校验。剧本提交、剧本批准、角色批准必须分别人工操作。")
    if not selected_column:
        st.info("请先创建或选择一个栏目。")
    else:
        script_series = json_request(
            "GET", f"/api/v1/columns/{selected_column}/series",
        ) or []
        if not script_series:
            st.info("该栏目尚未有剧集。请先在「原创短剧」页创建。")
        else:
            series_names = {s["id"]: s["title"] for s in script_series}
            chosen_series = st.selectbox(
                "当前原创剧集", list(series_names),
                format_func=lambda sid: series_names[sid], key="wizard_series",
            )
            st.markdown("#### 1 · Story Bible（全剧设定）")
            bibles = json_request(
                "GET", f"/api/v1/series/{chosen_series}/story-bibles",
            ) or []
            with st.expander("新增 Story Bible（版本追加，不覆盖旧设定）"):
                with st.form("wizard_create_bible"):
                    bible_title = st.text_input("设定名称", "第一季人物关系")
                    bible_logline = st.text_area("一句话梗概", "请填写原创故事主线")
                    bible_genre = st.text_input("故事类型", "都市悬疑")
                    if st.form_submit_button("保存 Story Bible 版本"):
                        created = json_request(
                            "POST", f"/api/v1/series/{chosen_series}/story-bibles",
                            json={
                                "title": bible_title, "logline": bible_logline,
                                "genre": bible_genre,
                            },
                        )
                        if created:
                            st.success("Story Bible 已保存。")
                            st.rerun()
            actors_scenes = json_request(
                "GET", f"/api/v1/series/{chosen_series}/assets",
            ) or []
            actors = {
                a["id"]: a["asset_key"] + f' v{a["version"]}'
                for a in actors_scenes if a["kind"] == "actor"
            }
            scenes = {
                a["id"]: a["asset_key"] + f' v{a["version"]}'
                for a in actors_scenes if a["kind"] == "scene"
            }
            if not bibles or not actors:
                st.warning("至少需要一个 Story Bible 和一名本剧演员资产。演员请到「资产与生产任务」页登记。")
            else:
                bible_names = {b["id"]: f'设定 v{b["version"]}' for b in bibles}
                chosen_bible = st.selectbox(
                    "选定 Story Bible", list(bible_names),
                    format_func=lambda bid: bible_names[bid],
                    key="wizard_bible",
                )
                st.markdown("#### 2 · 编写、校验分镜")
                selected_actors = st.multiselect(
                    "镜头中的角色（同剧已登记资产）", list(actors),
                    default=list(actors)[:1], format_func=lambda aid: actors[aid],
                    key=f"wizard_actors_{chosen_series}",
                )
                chosen_scene = st.selectbox(
                    "镜头场景", [None, *scenes],
                    format_func=lambda sid: scenes.get(sid, "不指定场景"),
                    key=f"wizard_scene_{chosen_series}",
                )
                next_episode = st.number_input(
                    "分集编号", 1, 999, 1, 1, key=f"wizard_episode_{chosen_series}",
                )
                num_shots = st.number_input(
                    "初始镜头数", 1, 12, 3, 1, key=f"wizard_shots_{chosen_series}",
                )
                per_shot = st.number_input(
                    "每镜头秒数（可在 JSON 里逐镜修改，总时长最多 90 秒）",
                    1, 30, 20, 1, key=f"wizard_length_{chosen_series}",
                )
                editor_key = f"wizard_json_{chosen_series}_{chosen_bible}"
                if st.button("初始化 / 重置可编辑分镜草稿"):
                    try:
                        template = make_storyboard_template(
                            chosen_series, chosen_bible, selected_actors,
                            chosen_scene, episode_number=int(next_episode),
                            shot_count=int(num_shots), seconds_per_shot=int(per_shot),
                        )
                        st.session_state[editor_key] = json.dumps(
                            template, ensure_ascii=False, indent=2,
                        )
                        st.session_state.pop("wizard_validated", None)
                    except LocalStoryWizardError:
                        st.error("请先选择角色，并确保总长度不超过 90 秒。")
                if editor_key not in st.session_state:
                    st.caption("点「初始化」建立草稿，再编辑动作、对白、镜头连续性和时长。")
                else:
                    st.caption("推荐在逐镜表单编辑。修改只有点击「应用到草稿」才生效；随后必须重新校验并人工确认。")
                    revision_key = f"{editor_key}_visual_revision"
                    applied = show_visual_storyboard(
                        st.session_state[editor_key], actors, scenes,
                        form_key=f"shot_form_{chosen_series}_{chosen_bible}_"
                        f"{st.session_state.get(revision_key, 0)}",
                    )
                    if applied is not None:
                        # Update canonical JSON before instantiating its widget.
                        st.session_state[editor_key] = json.dumps(
                            applied, ensure_ascii=False, indent=2,
                        )
                        st.session_state.pop("wizard_validated", None)
                        st.session_state[revision_key] = (
                            st.session_state.get(revision_key, 0) + 1
                        )
                        st.rerun()
                    with st.expander("高级 JSON 编辑（完整 Screenplay 格式）", expanded=False):
                        raw_script = st.text_area(
                            "Screenplay zh.v1 源 JSON",
                            height=380, key=editor_key,
                        )
                    script_payload = None
                    try:
                        script_payload = json.loads(raw_script)
                        if type(script_payload) is not dict:
                            raise ValueError("not object")
                    except (ValueError, TypeError):
                        st.error("分镜必须是合法的 JSON 对象。")
                    if st.button("① 校验分镜（不会提交或扣费）", disabled=script_payload is None):
                        try:
                            expected = canonical_screenplay_digest(script_payload)
                        except (ValueError, TypeError):
                            st.session_state.pop("wizard_validated", None)
                            st.error("分镜字段/时长/对白不满足本机 Screenplay 契约。")
                        else:
                            result = json_request(
                                "POST", f"/api/v1/series/{chosen_series}/screenplays/validate",
                                json=script_payload,
                            )
                            if result and result.get("valid") is True and result.get("review_required") is True:
                                st.session_state["wizard_validated"] = {
                                    "series_id": chosen_series, "fingerprint": expected,
                                    "valid": True, "review_required": True,
                                    "paid_api_calls": result.get("paid_api_calls"),
                                }
                                st.success(f'服务器校验通过：{result["shot_count"]} 个镜头。需人工确认才可提交。')
                                st.json(result["episode_draft"])
                            else:
                                st.session_state.pop("wizard_validated", None)
                    ready_to_commit = (
                        script_payload is not None
                        and validated_draft_still_matches(
                            script_payload, st.session_state.get("wizard_validated"),
                            chosen_series,
                        )
                    )
                    if script_payload is not None and not ready_to_commit:
                        st.caption("当前编辑内容尚未验证或在验证后已修改。任何改动都需重新校验。")
                    # A reviewed checkbox belongs to one validated exact draft.
                    # Revalidation of edited text MUST produce a fresh checkbox.
                    review_digest = (
                        st.session_state["wizard_validated"]["fingerprint"]
                        if ready_to_commit else "not_validated"
                    )
                    confirmed = st.checkbox(
                        "我已亲自检查此版分镜、对白、角色/场景归属，并确认提交为不可原地覆盖的 Episode。",
                        key=f"wizard_manual_review_{chosen_series}_{chosen_bible}_{review_digest}",
                        disabled=not ready_to_commit,
                    )
                    if st.button(
                        "② 人工确认并提交 Episode", disabled=not ready_to_commit or not confirmed,
                    ):
                        committed = json_request(
                            "POST", f"/api/v1/series/{chosen_series}/screenplays/commit",
                            json={
                                "screenplay": script_payload,
                                "reviewed_by_operator": True,
                            },
                        )
                        if committed:
                            st.session_state.pop("wizard_validated", None)
                            st.success(f'Episode 已创建：{committed["episode_id"]}。')
                            st.rerun()
            st.markdown("#### 3 · 创建 Production 并逐级人工审批")
            episodes = json_request(
                "GET", f"/api/v1/projects/{chosen_series}/episodes",
            ) or []
            if not episodes:
                st.caption("当前剧集还没有已提交的 Episode。完成分镜校验和人工提交后继续。")
            else:
                episode_map = {e["id"]: e for e in episodes}
                chosen_episode = st.selectbox(
                    "待制作分集", list(episode_map),
                    format_func=lambda eid: (
                        f'第 {episode_map[eid]["episode_number"]} 集 · '
                        f'{episode_map[eid]["title"]}'
                    ),
                    key="wizard_chosen_episode",
                )
                approved_episode = json.loads(episode_map[chosen_episode]["body_json"])
                st.dataframe([
                    {
                        "镜头": sh["shot_id"], "秒数": sh["duration_seconds"],
                        "角色数": len(sh["character_ids"]), "已批准对白数": len(sh["dialogue"]),
                    } for sh in approved_episode["shots"]
                ], use_container_width=True)
                all_runs = json_request(
                    "GET", "/api/v1/productions", params={"series_id": chosen_series},
                ) or []
                episode_runs = [r for r in all_runs if r["episode_id"] == chosen_episode]
                if not episode_runs:
                    if st.button("③ 为此分集创建 Production"):
                        created = json_request(
                            "POST", f"/api/v1/episodes/{chosen_episode}/productions",
                        )
                        if created:
                            st.success("Production 已创建，下一步审核剧本。")
                            st.rerun()
                else:
                    run_map = {r["id"]: r for r in episode_runs}
                    chosen_run = st.selectbox(
                        "Production", list(run_map),
                        format_func=lambda rid: f'{rid} · {run_map[rid]["status"]}',
                        key="wizard_chosen_run",
                    )
                    run_status = run_map[chosen_run]["status"]
                    if run_status == "script_review_pending":
                        with st.expander("展开已提交的完整分集剧本（含对白）", expanded=True):
                            st.json(approved_episode)
                        script_checked = st.checkbox(
                            "我已人工复核此 Production 对应的完整剧本、对白与时长。",
                            key=f"wizard_approve_script_{chosen_run}",
                        )
                        if st.button("④ 批准剧本", disabled=not script_checked):
                            result = json_request(
                                "POST", f"/api/v1/productions/{chosen_run}/approve-script",
                            )
                            if result:
                                st.success("剧本已批准。下一阶段：审核人物与场景。")
                                st.rerun()
                    elif run_status == "character_review_pending":
                        used_assets = {
                            a for shot in approved_episode["shots"]
                            for a in [*shot["character_ids"], *([shot["scene_id"]] if shot["scene_id"] else [])]
                        }
                        st.caption("当前分集引用的人物与场景规格（仅本剧登记版本）：")
                        st.json([
                            {
                                "asset_id": a["id"], "kind": a["kind"],
                                "key": a["asset_key"], "version": a["version"],
                                "specification": json.loads(a["specification_json"]),
                            }
                            for a in actors_scenes if a["id"] in used_assets
                        ])
                        cast_checked = st.checkbox(
                            "我已人工核对分集的人物身份、造型版本、场景及授权信息。",
                            key=f"wizard_approve_cast_{chosen_run}",
                        )
                        if st.button("⑤ 批准人物与场景", disabled=not cast_checked):
                            result = json_request(
                                "POST", f"/api/v1/productions/{chosen_run}/approve-characters",
                            )
                            if result:
                                st.success("Production 已通过两级审核。转到「本机审片」生成技术预览。")
                                st.rerun()
                    elif run_status in ("ready_for_video_generation", "offline_preview_finished"):
                        st.success("两级人工审批已完成。请转到「本机审片」页进行免费离线渲染与播放。")
                    else:
                        st.info("该 Production 处于其他状态，无法在此重复审批。")
    st.caption("校验、提交和审批均沿用现有 FastAPI 路由。无自动模型生成、无批量确认或自动发行。")

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
                source_root = local_data / "local-shot-media"
                st.markdown("#### 导入本机原创视频镜头（可选）")
                st.caption(
                    "只允许上传本机 MP4/MOV/WEBM/MKV，单段最多 32 MB。"
                    "不传到任何云端/AI 服务；选择当前 Production 已审核的镜头。"
                    "本地授权声明仅为操作员自述，不代表版权已独立核验。"
                )
                if status in ("ready_for_video_generation", "offline_preview_finished"):
                    episode_row = local_db.one(
                        """SELECT e.project_id, e.body_json FROM productions p
                           JOIN episodes e ON e.id=p.episode_id WHERE p.id=?""",
                        (run_id,),
                    )
                    if episode_row and episode_row["project_id"] == review_series_id:
                        approved_episode = EpisodeDraft.model_validate_json(
                            episode_row["body_json"],
                        )
                        duration_by_shot = {
                            shot.shot_id: shot.duration_seconds
                            for shot in approved_episode.shots
                        }
                        shot_choice = st.selectbox(
                            "选择将被本地视频替换的镜头",
                            list(duration_by_shot),
                            format_func=lambda sid: f"{sid} · {duration_by_shot[sid]} 秒",
                            key=f"local_shot_choice_{run_id}",
                        )
                        video_upload = st.file_uploader(
                            "选择本机视频文件",
                            type=["mp4", "mov", "webm", "mkv"],
                            key=f"local_shot_upload_{run_id}_{shot_choice}",
                        )
                        rights_checked = st.checkbox(
                            "我确认对这段视频拥有原创权利或明确授权，仅将其用于本机技术审片。",
                            key=f"local_shot_rights_{run_id}_{shot_choice}",
                        )
                        if st.button(
                            "登记这段视频到选中镜头（不生成、不发布）",
                            disabled=not rights_checked or video_upload is None,
                        ):
                            try:
                                if video_upload is None or video_upload.size > 32 * 1024 * 1024:
                                    raise LocalShotMediaError("Video size over local limit")
                                receipt = stage_local_shot_video(
                                    local_db, run_id, review_series_id,
                                    source_root, shot_id=shot_choice,
                                    filename=video_upload.name,
                                    content=video_upload.getvalue(),
                                    operator_attests_rights=rights_checked,
                                )
                                st.success(
                                    f'本机视频已登记到 {receipt["shot_id"]}，'
                                    f'SHA256: {receipt["sha256"][:14]}…。'
                                    "这是自述素材，不表示商用权利已独立核验。"
                                )
                            except (LocalShotMediaError, OSError, ValueError):
                                st.error("素材登记失败：视频/时长/格式/镜头归属或权利声明不符合要求。")
                        try:
                            staged = get_staged_shot_clips(
                                local_db, run_id, review_series_id, source_root,
                            )
                        except (LocalShotMediaError, OSError):
                            st.error("已登记素材的完整性检查失败。请修复本机素材后再尝试渲染。")
                            staged = None
                        if staged is not None:
                            st.caption(
                                f"本机有效视频镜头 {len(staged)}/{len(duration_by_shot)}；"
                                "其余仍使用占位卡片，渲染和 QA 会重新读取并校验视频。"
                            )
                            st.dataframe([
                                {"镜头": sid, "时长（秒）": dur,
                                 "本地视频": "已登记" if sid in staged else "未登记／占位"}
                                for sid, dur in duration_by_shot.items()
                            ], hide_index=True, use_container_width=True)
                    else:
                        staged = None
                        st.error("Production 与当前剧集不匹配。")
                else:
                    staged = None
                    st.info("必须先通过剧本及人物审批，才能登记本机视频镜头。")
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
                        if staged is None:
                            raise LocalShotMediaError("Local staged media verification failed")
                        render_approved_preview(
                            local_db, run_id, review_root,
                            source_clips=staged,
                        )
                        st.success("离线 MP4 渲染及独立技术 QA 已通过。可以复核并播放。")
                    except (PreviewError, LocalReviewDenied, LocalShotMediaError, OSError, ValueError):
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