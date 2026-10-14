# PR-07b1｜本机离线审片工作台（不是线上发布系统）

## 目标与使用方式

现在已有经人工剧本/角色审核的 Episode → 离线 H.264/AAC/mov_text MP4 渲染、逐镜内容缓存与真实 FFmpeg 完整技术 QA。本 PR 使这些既有产物能通过本机 Streamlit 前端**生成、复核、播放和查看镜头清单**，不再只能查 GitHub Actions Artifact 或 Python 文件路径。

在项目根目录安装 `pip install -e '.[frontend,render,test]'`，保证系统 `ffmpeg` / `ffprobe` 在 PATH，并让 API、Streamlit 读取**同一**本地数据库：

```bash
export DRAMA_FACTORY_DATA_DIR=./data
export DRAMA_OFFLINE_RENDER_ROOT=./artifacts/offline-reviews
uvicorn drama_factory.api:app --host 127.0.0.1 --port 8000
# 在另一个终端（同一机器、相同环境变量）：
streamlit run frontend/app.py --server.address 127.0.0.1
```

选择栏目 → **本机审片** → 选择剧集/Production。当状态是 `ready_for_video_generation` 或 `offline_preview_finished` 时，可点「生成 / 更新已审核的离线 MP4」；渲染只调用本地 `render_approved_preview`，不连接 Gemini 等模型，错误不会显示原始剧本文本。完成后刷新或选「复核本机已完成的样片」，可看竖屏 MP4 和镜头列表。

## 真正的安全边界

- `load_local_offline_review(db, production_id, root, series_id=...)` 仅通过本地 SQLite 查询 **已完成的** Production，且必须属于选中的 Series；仅可打开工作目录下**固定路径** `<root>/<series_id>/<production_id>/preview.mp4`。路径绝不取自任意上传参数。
- DB `result_json` 与同工作目录中的 `manifest.json` 必须一致，episode/series/production、`status`、原始 MP4 路径、零付费标志都要正确；拒绝链接文件/目录、错误根路径、篡改记录、无签收或损坏的视频。
- 播放之前**每次重新**调用已有 `inspect_offline_delivery`，检查整段 FFmpeg 解码、原 MP4 哈希、逐镜缓存哈希、字幕侧文件与 MP4 内嵌字幕，以及既有技术内容说明。
- UI 显示可用镜头数量、时长、占位与本地片段数、缓存重用状态；不把小说、声音、剧本文字、外部 Interaction ID、音频二进制或费用凭证展示在审片报告。
- 没有新增公网 API、生产视频 Worker、持久化发布审批状态、私有对象分享、Google 网络或计费功能。播放文件仅供**本地可信操作员**。**Streamlit/API 均无鉴权，必须绑定 127.0.0.1，不得公网开放。**

## 验收

新增测试直接生成有人工审核记录的原创合成离线 MP4，经本机完整 QA 后再从独立审核读取器打开。覆盖审核未完成、跨剧集、路径切换、DB/旁车 manifest 篡改、MP4 哈希变化、符号链接，验证只读工作台不变更任何生产状态。Python 3.11、3.13、本地 native libSQL 与 offline-video FFmpeg 四项 CI 必须全绿。

> 这是 PR-07b 的**本机审片子阶段**，不是 PR-07b 完整的私有媒体上传、资产编辑和身份权限功能；这些仍未实现。离线技术 QA PASS ≠ 画面已经由 AI 生成 ≠ 商用版权/声音已审核 ≠ 允许发布。
