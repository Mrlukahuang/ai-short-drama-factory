# PR-10k｜已确认的 TTS Interaction 只读恢复原 WAV（严格离线 Fake）

## 为什么要做

PR-10i 已串联审核、预算 held、持久不可重发的 paid intent、唯一 Interaction 回执和 WAV 双重校验；PR-10j 明确指出 `acknowledged` 任务已经具有供应商 ID，网络或 Worker 崩溃后**只能恢复原请求**，不能生成同一句新语音。本 PR 将这个状态的恢复行动独立实现并以 Fake 验证。

## 安全合同

`recover_offline_existing_tts_wav(db,task_id,reader)` 只接受确切类型的 `OfflineFakeExistingAudioReader`，**没有 Google SDK import、network client 或新的 interactions.create 请求**。首先 SELECT 已持久化 `tts_tasks`：仅当 `status=acknowledged`、Provider Interaction ID 存在且与 Fake 仅读回源完全匹配、原三级预算为 `held` 或仅人工凭证 `reconciled` 时，才允许 Fake 模拟已有资源读回。无 ID、`prepared`、`submission_intent`、`quarantined`、`verified` 均不能调用 Fake 读取。

恢复后必须重新核实返回 Interaction ID 与此前持久 ID 相同；24kHz 单声道 16-bit PCM WAV 原始字节经 PR-10e 独立解码、时长约束和 PR-10h 最终持久化边界**再次验收**，才会更新为 `verified`。绝不登记新的供应商任务 ID，也不释放未核实预算。错误 Provider ID、网络超时、错 WAV 全部固定脱敏错误；原 `acknowledged` 和 held 状态保留，仍不能补提交新的 paid 请求。

结果只返回已有记录的 SHA256、验证标志和无付费计数；无小说、台词、演员、请求正文、Interaction ID、账单凭证或原 WAV 内容。输出恒有 `new_tts_generation_attempts=0`、`actual_paid_provider_calls=0`、`automated_retry_allowed=false`、`publish_approved=false`。

本地 CI 使用完全 Fake 的预存 provider response，在合法恢复、损坏 WAV/模拟超时/错 ID、未知 ACK 任务、未提交任务、已验任务及任意 SDK/子类客户端注入场景断言不产生付费调用或多余状态变化。

## 下一阶段

此模块不是 Google 历史查询 Adapter，仍无法真实获取已存在 Interaction 的 result/audio；后续需要只读官方 Interactions GET 的 SDK/API 文档核验、凭据最小权限及原始 ID/账户归属比对，并针对真正网络超时不自动重试。只有在所有生产级账本、费用与声音授权门禁真实通过后，才考虑给 Worker 受限启用。已消耗的真实 TTS 和历史 TxLab Workflows 不得重跑。
