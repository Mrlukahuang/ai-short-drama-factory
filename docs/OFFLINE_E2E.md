# PR-11：离线真实 MP4 端到端生产冒烟测试

**目的：先验证完整数据流，不购买更多图片、视频或 TTS 服务。**

## 实际工作流

`Column → Series → Story Bible → 演员/场景资产 → Screenplay JSON → 无副作用 /validate → 人工明确 /commit → Episode → Production → 批准剧本 → 批准角色 → 每镜头缓存素材 → FFmpeg 合成 → 字幕轨 → ffprobe 验收 → MP4 + manifest`

用 `python -m drama_factory.pipeline.offline_demo --out artifacts/offline-demo` 启动独立离线演示；所有剧情、角色与数据都是测试用虚构数据。Demo 创建临时 SQLite 记录，通过真实 FastAPI 内部 TestClient 发起审核和分集 API 请求（不需要外网），而非跳过校验直接输出电影文件。

- 视频：逐镜头使用 Pillow 生成静态技术预览卡片，FFmpeg 编码 H.264/yuv420p、360×640、15fps。
- 音频：FFmpeg 生成非常小声的人工合成提示音，AAC/48kHz；**不是 AI 配音，也不是中文对白**。
- 字幕：按已批准 Episode 的 `ShotDraft.dialogue` 生成 SRT，并封装为 MP4 `mov_text` 可开关软字幕。它是文字，不是口型。
- 后期：每镜头先规范化单独视频片段，再用 FFmpeg concat 合并，统一一条视频、一条音频、一条字幕轨。
- 验收：ffprobe 逐镜检查 H.264/AAC、分辨率、时长；成片检查字幕轨，并只在真实文件检查成功后保存 manifest 和状态。
- 恢复：镜头缓存名含 `series_id`、`episode_id`、镜头全部输入及编码参数的 SHA256；再运行可复用正确镜头，损坏某一镜头只重建该镜头。
- 门禁：必须存在 Production，且原有审批状态已经到 `ready_for_video_generation`。输出 `offline_preview_finished`，**不冒充真实 AI 视频已成功**。
- 资源限制：离线样片最多 12 镜头、90 秒；当前单机 FFmpeg，不是多 Worker 并发队列。
- 发布：GitHub CI 增加 `offline-video` job，自动产生一个 6 秒样片并上传 `offline-end-to-end-mp4` Artifact；**CI 不读取任何 GEMINI_API_KEY 或其他付费模型密钥**。

## 本地复现

```bash
sudo apt-get install -y ffmpeg  # macOS: brew install ffmpeg
python -m pip install -e '.[test,render]'
python -m drama_factory.pipeline.offline_demo --out artifacts/offline-demo
ffprobe -hide_banner artifacts/offline-demo/demo.mp4
```

在 GitHub Actions 的 Python CI 运行页下载 `offline-end-to-end-mp4`，包含 `demo.mp4` 和 `manifest.json`。输出文件可能因 FFmpeg 版本有细微字节差异；校验依靠格式、音视频与字幕流、目标时长和 SHA256，而不是跨机器比较字节。

## 本阶段刻意没有完成

- 没有 AI 人物镜头、真实 Google Omni 视频、中文 TTS、口型、背景音乐或正式剪辑。
- 没有向公网提供未认证的转码 API，也没有在 Git 仓库永久保存任何输出媒体。
- 离线预览卡片只是验证工厂总线可产出合法可播放 MP4 的技术夹具，不应称为正式短剧。
- AI VideoProvider、镜头级持久化付费任务/外部 task_id、预算和并发仍按原计划逐步开发。
