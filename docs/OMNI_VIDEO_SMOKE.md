# PR-13a：Google Gemini Omni 视频单镜头 → 完整短剧生产线

## 目标

验证下一条真正收费的生产链：`Google Omni Interactions API → 真实生成视频 → Google Files URI/内联下载 → FFprobe 来源审查 → 第 2 镜头导入 → FFmpeg 格式统一 → 配字幕 → 合成 6 秒 MP4 → 供人工下载审看`。

*官方来源*：[Gemini Omni 视频生成文档](https://ai.google.dev/gemini-api/docs/omni)，2026-10-12 核对。
模型 ID `gemini-omni-1.1-flash`；`response_format={"type":"video","aspect_ratio":"9:16","resolution":"360p","delivery":"uri"}`。若 URI 文件处于 PROCESSING 状态，SDK 只轮询同一个文件最多 60 次（5 秒间隔），绝不重复发送模型生成请求；若服务返回内联 Base64 视频则也支持解析。

## 手动运行（会产生真实模型费用）

1. 已配置的 GitHub 私有 `GEMINI_API_KEY` 可继续使用，**不要把密钥发送到聊天、Issue 或 PR**。
2. 打开本仓库 [Actions](https://github.com/Mrlukahuang/ai-short-drama-factory/actions)，找到 `Google Omni one-video to episode (manual, may incur cost)`。
3. 点击 Run workflow，必须选择最新的 `main`，输入 **`GENERATE_ONE_PAID_VIDEO`**，确认真实费用后点击运行。
4. 成功后在 run 的 Artifacts 下载 `omni-real-clip-and-composed-episode`，得到一个真实 Gemini 视频 `omni_raw.mp4`、一个将其嵌入第 2 镜头的 `demo.mp4`，以及 `manifest.json`。

视频内容仅为虚构小红球滚过木桌的 3 秒左右测试镜头，不追求人脸一致性，不含未经授权人物或小说。

## 安全边界

- 只有人工 workflow_dispatch + 准确确认词 + `GEMINI_API_KEY` + `DRAMA_ENABLE_PAID_GENERATION=YES` + 脚本中单次批准全满足，才会调用 Google。
- 普通 CI、PR 和 README 更新 **不会执行付费生成**。本 PR 不实际执行模型请求。
- `maximum_acknowledged_spend_usd="2.00"` 是开发人员的确认记录，不是 Google 服务器强制账单封顶；实际费用取决于供应商输出时长、计费、账户设置。
- **单次 Actions 运行只提交一条视频生成请求，没有生成请求重试。** 即使下载或后期失败，该模型请求也可能已计费，所以失败后应检查日志再决定是否重跑。
- 视频来源必须通过本机媒体验证与长度检查，才允许交给 FFmpeg。暂不对公众提供视频 URL 接口或任意上传入口。
- 云端真实任务管理、账单硬预算、演员多参考、用户身份鉴别、机密文本输入、连续视频场景质量均还未完成。
- GitHub Artifact 3 天后过期，成功的测试素材请自行保存。

## 离线回归

```bash
python -m pip install -e '.[test,google-video]'
pytest -q tests/test_google_omni_video.py
python -m drama_factory.providers.omni_video_smoke --out artifacts/offline-demo
```

离线 CI 通过 Fake Provider / 注入 SDK stub 测试，确保 provider gate、URI 轮询/下载、内联 Base64、媒体校验、后期衔接不依赖 Google API。
