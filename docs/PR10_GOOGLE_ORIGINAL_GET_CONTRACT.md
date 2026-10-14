# PR-10n｜原始 Gemini Interaction ID 的 GET 只读恢复合同（离线）

## 已核对的官方能力（2026-10-14）

* Google Python SDK 的公开 `client.interactions.get(id=..., include_input=False, stream=False)` 按**已有** Interaction ID 查询已有记录：<https://googleapis.github.io/python-genai/genai.html>。
* Google Interactions 文档确认存储对象可供 `interactions.get` 恢复；默认 `store=true`，也允许 `store=false`。官方目前写明付费层保留 55 天、免费层保留 1 天，账户另可设较短保留期：<https://ai.google.dev/gemini-api/docs/interactions-overview>。
* 这**不保证**旧 TTS 的音频 Base64 一定保留，或保留期间始终可 GET。404、权限失败、超时、`store=false`、音频字段不存在都必须 fail closed。绝不可调用 `interactions.create` 当作恢复。

## 本 PR 真正实现了什么

新增 `src/drama_factory/jobs/tts_google_readback_contract.py` 与隔离测试。仅接受 **exact type** `OfflineFakeGoogleInteractionsGetter`，明确没有导入 SDK、没有网络客户端、没有凭证/生产开关。它模拟 SDK 的 GET 参数，但**绝无**真实 Google GET 与付费请求。

`inspect_offline_original_google_tts_get(db, task_id, getter)`：

1. 首先在 SQLite 单次只读事务里审核旧 TTS 任务的状态、逐条不可变事件链、Provider=google、原 Interaction ID 及原 held/reconciled 预算，严格只接收 `acknowledged`。绝不读取私人剧本正文。
2. 确认 Fake GET 的预绑定原始 ID 与持久 ID 完全一致，仅进行一次 `get(id=original_id, include_input=False, stream=False)`。不允许任意 SDK/鸭子类型或 Fake 子类注入。
3. 对返回的 Interaction ID 与 WAV MIME/Base64、24kHz 单声道 16-bit PCM、大小/时长独立审核；若同一 Google Provider 下已有其他分镜的已验证 SHA256 相同，则安全拒绝。GET 前后再次交叉检查本地审计/状态。
4. 成功也**只返回脱敏检查收据**，不会把 `acknowledged` 更改为 `verified`，不会持久化音频、修改预算、释放预留、验证真实账单或批准发行。

回归场景包括正常 Fake GET、相异原 ID、未知 ACK、未提交与已验证状态、丢失审计、GET 403/404/超时、错 ID、缺失音频、格式坏/错 MIME、重复 WAV、已用 Getter 与 SDK 伪装注入。每种场景都不生成新请求或重试。

## 尚未验收 / 下一步

当前 `tts_tasks` 持久账本**不具备来源 Google project/account/auth scope 的可靠绑定**。因此真实读取 Adapter 仍关闭，返回字段 `origin_google_project_and_permissions_verified=false`。原始 TTS 测试的实际 Interaction ID 是否存储、是否可读回音频、是否仍在保留期及 Google 供应商真实账单均未验证。

后续要先新增生产身份来源不可变绑定、只读凭证/权限审计、原始互动 ID 的人工授权 GET 试验（禁止新建）、供应商原回执真实性与音频语义/声音授权人工审查；只有经过独立审查，才可将 GET 的真实下载结果接入 PR-10k 已有的双重 WAV 校验和持久化边界。PR-10m 的整集观测仍为只读，不承担自动恢复/付费控制。

**绝不**重启已消耗的 TTS canary 或 TxLab workflow、不触碰真实 Turso、不中断任何持久 held、不允许因 404/ACK 不明重新生成语音。官方 get 存在 ≠ 已验证真实 Google 回读，离线 CI 通过 ≠ 生产级可恢复。
