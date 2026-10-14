# PR-31b2o5 — 离线模拟供应商 Task ID 的 fenced 回执登记

此 PR 是 PR-31b2o4 的后续 **真实 `libsql==0.1.11` SDK 本地隔离实验**。只允许标记过的临时 SQLite 测试库，不触发真实模型、网络 API 或 Turso，也不改变生产 Worker/Schema/Secrets。

## 目的

现有镜头流程在 `generation_intent_recorded` 提交后，真实供应商可能已经开始计费，但客户端拿不到 Task ID（或数据库 COMMIT 回执丢失）。正确策略不是生成新任务，而是先只读检查原任务及供应商账单、由操作者核实。因此本轮**完全不调用真实供应商**，只用以 `SYNTHETIC_` 开头的固定本地模拟 Task ID，验证回执入账的原子性和失联后的不重放规则。

## 本地合同

`fenced_bind_synthetic_provider_task_local(...)` 只有在同一 `BEGIN IMMEDIATE` 中满足以下前提才允许更新模拟任务状态：

1. 现有隔离 `LocalNativeLibsqlLedger` marker、writer gate 正在运行、epoch 与领取代数仍匹配。
2. 原镜头已处于 `submission_intent` 且 `generation_intent_recorded=1`、Task ID 原为空；Worker 名称、attempt、lease deadline 全部匹配并尚未过期。
3. 同镜头已有一笔 `held` 预算预留，同时已经存在恰好一次 `held` 预算事件和一次 `generation_intent_recorded` 事件。
4. 接受的 ID **只能是** `SYNTHETIC_[A-Za-z0-9_-]{8,80}` 的本地模拟值，不接受真实或任意供应商 Task ID。以 `provider + synthetic_task_id` 预检查已存在的 Task ID，底层现有唯一索引仍是最终保障。
5. 单事务条件 CAS 将镜头从 `submission_intent` 改为 `submitted`、记录模拟 task ID、追加 `provider_task_recorded` 不可修改镜头事件与本地 gate 审计；任何失败一起回滚。

返回的回执不含任何 ID、路径、金额、Token 或剧本。无论返回成功与否，`task_was_generated=false`、`authorizes_paid_provider_call=false`、`may_retry_submission=false`、`paid_provider_calls=0`。

## 免费离线验收

- 只能在有 held 预算和意图事件的镜头登记，不接受空回执或非 SYNTHETIC ID。
- 相同 Provider 下同一个合成 Task ID 不能绑定到两个真实镜头（第二个冲突必须拒绝）。
- 错误的 Worker/attempt/epoch/deadline、租约过期、pause/resume 后的旧 token 都不允许写回。
- 镜头审计或 gate 审计插入失败时，之前的任务更新一同回滚。
- 真正 native SDK 已将 COMMIT 写入磁盘后，模拟客户端丢失 ACK：独立连接读到一套已提交的镜头/Task ID/审计；第二次同请求被拒绝，绝不能误判为“可再次发起付费”。
- 专项 native SDK CI **显式包含**测试文件，不能依赖默认 pytest 选择或 SKIP 绿灯。

## 明确不属于本轮的结果

没有真实供应商任务、账单、资产或 Task ID 网络回查，没有跨 GitHub Runner 的共享事务/时钟/权限验证，不代表可向生产 Turso 导入 Schema 或切换 Writer。真正的远端写入、正式 Worker 接入、Paid Provider、线上切换都需未来用户另外明确授权，当前旧 TxLab v1/v2/v3 的授权已经消耗，所有手动写入工作流继续硬锁止。
