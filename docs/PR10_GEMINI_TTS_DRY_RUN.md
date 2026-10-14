# PR-10e｜Gemini 3.8 TTS 官方请求格式与 WAV 交付合同（**仅离线，无实际 TTS**）

## 动机

之前 PR-10a–10d 只用原创合成正弦测试音跑通导演审核的多角色、每句时长及音轨/SRT/MP4；而 `GeminiDialogueAudioProvider` 仍被安全锁住。直接启用真实模型将缺少官方接口请求结构、角色声线、输出 RIFF 类型与精确费用/恢复保护之间的安全连接。

依据 **2026-10-14 查阅的 Google 官方文档**：`https://ai.google.dev/gemini-api/docs/speech-generation`，Gemini 3.8 Flash/Flash-Lite TTS 走 Interactions API，单说话人输入 `user_input.content[type=text]` 与 `speech_metadata`，`response_format={type:audio}`，`generation_config.speech_config=[{voice:Kore}]` 等；unary 默认提供 24kHz 单声道 PCM WAV 的 `interaction.output_audio.data`（Base64）。目前仅允许已知文档预设声线 `Kore`/`Puck`、3.8 Flash/Flash-Lite 两个模型。

## 新增安全逻辑

`prepare_gemini_tts_request(db, spec, control)` 仅在剧本/角色双审核、说话人属于当前系列、演员版本化音色资产匹配、存在声音来源同意登记、明确的操作者声音许可确认、**台词逐字核对并具有明确导演审核的起止秒数**后，才在内存中构造 SDK 私有输入。和旧 Fake 入口相比，不能只用 `actor_id: 字符串` 猜测说话人；必须有 `cue_index` + `speaker_actor_id`。公共 `safe_receipt()` 不含剧本文字、角色 ID、Token 或音频内容，只返回模型、SHA256 指纹、声明预算、是否真正提交（永远 false）。实际 SDK kwargs 不进入 repr/日志。计划预算上限必须在 0~2 USD 内，但它仅表示**自我确认**，不是供应商账单的硬性限制。

`inspect_gemini_tts_unary_response(...)` 离线接收一段模拟或以后已有的 Base64 WAV 数据，固定校验单声道、24kHz、16-bit PCM、RIFF、最大 8MiB、实际音频长度不得超过导演批准段落 0.25 秒以上；损坏、空音频、错误采样率或超时长一律拒绝，不泄露原始内容。独立 Fake 音频模拟响应再走真实 FFmpeg 混音与 PR-14/15e 内嵌字幕 QA；证明 **格式互通**，不证明真人发音质量。

## 严格未完成

本 PR **没有 Google SDK 客户端、不会发网络请求、没有收费调用**，也不会更改现有 `GeminiDialogueAudioProvider.synthesize` 的拒绝逻辑。正式提交前仍需持久化 TTS 费用预留、供应商 task/interaction ID 与断线回执恢复、独立声纹/商用许可、真实 API Key/账户和供应商费用验收。必须明确分开 SDK 兼容测试、真实收费测试与上线许可，不能声称现在已经生成真实对白。
