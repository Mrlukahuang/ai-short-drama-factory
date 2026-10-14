# PR-10i｜持久 TTS 任务一次执行编排（严格离线 Fake）

## Why

PR-10g/h 已把经过审核的 Actor、Voice 版本、导演台词时槽、三层共享预算、提交意图、provider Interaction ID 唯一绑定和 WAV 接收验证分别落地。但缺少一个能**实测所有环节正确顺序**的编排器；尤其在两个 Worker 同时争同一已审核台词、供应商已经受理却未返回 ACK、或者 WAV 内容损坏时，不能凭代码片段推测不存在二次扣费风险。

## Implemented

`execute_offline_fake_tts_once(db,task_id,spec,control,transport)` **只接受确切类型** `OfflineFakeGeminiTransport`；子类、任意 Google SDK/HTTP Client 或注入回调都会在任何账本变更前被拒绝。此模块没有 Google import、网络请求，也没有调用真实 Gemini TTS 的途径。

1. 重新独立审核剧本、角色、同剧集版本化声音资产、精确 Cue 起止、声音同意声明与请求 SHA256，并比对本地持久 TTS 任务模型/声线/金额配置/已预留预算；不一致无副作用。
2. `commit_tts_submission_intent` 通过本地 SQLite 的 `BEGIN IMMEDIATE` 原子锁，把预留 TTS 状态变成**唯一一次不可逆提交意图**。两个线程即使几乎同时通过只读预检查，第二个也必须在提交意图处失败，不能进入模拟供应商调用。
3. 精确一次 `OfflineFakeGeminiTransport.submit_one`。成功时独立绑定一条 Provider ID，验证合成 Fake 的 24kHz 单声道 PCM WAV，并经 PR-10h 再检将音频 SHA256 和实际长度记录到持久账本，音频字节不进入数据库或事件日志。
4. 回执丢失、非法 ID 或已有其他 Cue 绑定同一供应商 ID 时：本次任务转 `quarantined`，保留 held 预算和审计，**绝不自动重试**。若供应商 ID 已登记但后续 WAV 无效，则保持 `acknowledged`，等待人工恢复既有结果，不能重新发请求。
5. 把可观察结果限定为脱敏计数/哈希及状态。无剧本文字、密钥、声音数据、私人角色 ID 或异常原文，`actual_paid_provider_calls=0`、`publish_approved=false`。

## Tests and remaining work

独立 Fake 测试在普通 Python 3.11/3.13 CI 无凭据运行，覆盖真正两个线程同一数据库争抢、一次成功及全链事件顺序、两种无 ACK 失败、同供应商 ID 重复、真实 24k PCM 造假、声音资产变更/控制项篡改、无预留/任意 Provider 类型注入阻断。原有强制 FFmpeg、真实本地 libSQL SDK 测试继续运行，历史单次真实 TTS 和 TxLab 工作流不重开。

**此项不等于真实供应商提交已经可生产使用**。真实 SDK 不可注入到 Fake 编排器；未来另行设计受控分布式 Runner、正式 Worker 身份/租约/epoch 及跨进程共享数据库、云端提交前事务确认、供应商账单/interaction 恢复以及真实 TTS 的内容审听。没有独立 vendor 硬成本限制证明，也未验证生产部署或 Google 实际账单。
