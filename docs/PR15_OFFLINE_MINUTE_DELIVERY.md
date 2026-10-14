# PR-15a｜一分钟 9:16 离线真实 MP4 技术样片

此阶段的目标是先把一分钟成片的**技术链路**彻底跑通，而不是假装已经生成真人/AI 画面。脚本创建三段各 20 秒的虚构镜头，其中一个镜头来自本地 FFmpeg 合成的移动测试图案，其余使用明确标注 OFFLINE PREVIEW 的图卡；音频为合成音调或本地静音，没有真人配音、口型或真实 AI 视频。

## 自动化执行与验收

默认 `python -m drama_factory.pipeline.offline_demo --out artifacts/offline-demo` 仍产生原始 6 秒免费烟雾测试。新参数 `--seconds 60 --out artifacts/offline-demo-60` 使用**相同** FastAPI 原创短剧、Story Bible、演员/场景资产、审片批准流程、三镜头任务和逐镜 SHA256 缓存，输出可播放 60 秒纵向 MP4 和 manifest；只接受 6 或 60 秒，拒绝其他时长。

每次 main / PR 的 offline-video Job 在原有 6 秒烟雾测试之外**真实执行 60 秒编码**，以 ffprobe 和 manifest 验收时长（59.4–60.6 秒）、360×640、H264、AAC、mov_text 软字幕、三段总长 60 秒、PR-14b/c 完整解码和字幕/缓存哈希质检，运行全部无需 API Key。CI 将完整技术演示 MP4 和 manifest 上传为 7 天 GitHub Actions Artifact `offline-one-minute-technical-mp4`。

## 不得误称为完整影视成片

这不是演员连续真人短剧。manifest 中必须 `spoken_dialogue_generated=false`、`paid_api_calls=0`、`genuine_ai_video_verified=false`、`publish_approved=false`、`production_ready=false`、`operator_review_required=true`。实际模型生成、固定角色身份、中文配音/口型、音画真实一致性、版权审核、正式发布仍在后续 M2/M3/M4/M5 里程碑，需要独立真实验收。本 PR 没有云端写入或付费 Provider 调用。
