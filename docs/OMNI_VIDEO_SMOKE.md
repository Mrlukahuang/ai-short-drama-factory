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


## PR-14：首次视频试片失败与下载恢复机制

2026-10-12 [GitHub Actions #38229227030](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38229227030) 在提交 Omni 视频生成请求之后收到 `output_video.uri`，但旧版本将 URI 最后一段按纯 ID 检查，未能接受 Google 的 `:download?alt=media` 后缀，故失败为 `InvalidVideoResponse: Invalid Google video file URI`。**密钥检查成功，SDK 安装成功，但视频未下载、未完成合成；Google 侧可能已计费，需看账号账单。**

按照 [Google 官方 Omni URI 视频交付文档](https://ai.google.dev/gemini-api/docs/omni) 修正 URI 解析：支持 `https://generativelanguage.googleapis.com/v1beta/files/文件ID:download?alt=media`，严格限制 Google 官方域名与文件路径，并将不含密钥、原始 URL 或提示词的文件 ID 写入仅仓库私有的 `omni-video-recovery-receipt` Artifact（保留 3 天）。FFmpeg 或文件下载失败时，该凭据仍尽可能上传。

### 免费恢复已有结果（不提交新的视频生成）

当先前的运行已经生成 `omni-video-recovery-receipt`，但因为视频下载、后期或验收失败而未完成成片：

1. 打开那次运行，下载 `omni-video-recovery-receipt` 并读取其 `file_id`（只用于私有仓库）。
2. 从本仓库 **最新 main** 的 Actions → `Google Omni one-video to episode (manual, may incur cost)` 新开工作流。
3. `confirmation` 输入 **`RECOVER_EXISTING_VIDEO`**，`recovery_file_id` 填写上一步的 ID。
4. 系统仅用 `client.files.get` / `client.files.download` 查询及获取以前的已生成文件，再交给现有 FFmpeg 合成管线；**绝不调用 `interactions.create`**，不再次提交视频生成请求。
5. 这不保证 Google 文件永久保留或能被所有账号访问；若文件失效会失败，但不会自动再付费生成。保存的文件 ID 不应公开发布。

本次 #38229227030 使用旧代码，**没有保存恢复 Artifact，不能凭现有日志取得文件 ID**；因此本次无法直接使用免费恢复功能。

### 新的真实试片

只有在用户检查了先前 Google 账单并认可再次收费测试后，才可以从最新 main 的手动 Workflow 输入 `GENERATE_ONE_PAID_VIDEO` 启动新的**单次**视频生成请求。失败后优先检查新创建的恢复 Artifact，不要直接点击 Re-run jobs。
