# PR-31b2o4 — 本地 native SDK 三级预算 + 意图原子 fencing 实验

**范围：仅 CI 隔离、带 marker 的临时 SQLite 测试账本。** 真实 `libsql==0.1.11` 本地 SDK，不是 Turso 云端事务；不改变生产 Worker、生产 Schema、手动 TxLab workflow、Secrets、Drive 或付费 Provider。

## 与 PR-31b2o3 的差别

o3 已经在真实镜头 `shot_jobs` 上建立本地 writer gate / epoch + attempt CAS，测试未提交意图的失败写回。本轮延伸到**付费请求之前**的两个原子动作：三级预算预留与 `generation_intent_recorded` 持久化。业务源表沿用现有 `budget_policies`、`job_budget_reservations`、`budget_reservation_events`、`shot_jobs` 与 `shot_job_events`，不另造业务账本。

`fenced_hold_and_record_intent_local(...)` 使用一次 `BEGIN IMMEDIATE`：

1. 验证已有本地 marker、全局 gate 正在运行且当前 epoch 等于领取令牌。
2. 以 `job_id + lease_owner + attempts + lease_expires_at` 校验未过期的 leased 镜头；`generation_intent_recorded=0`，没有 Provider Task ID；同镜头不能有既有预算预留。
3. 检查预算提议额不超过已批准镜头上限，且栏目/剧集/Provider 三项有效策略都满足当日余额与活跃预留上限。原始持久预算策略/预留同表，使用现有 `budgets._amount/_latest/_event` 进行金额、有效策略与事件语义复用。
4. 原子插入 held 预留及不可修改的预算事件，条件 CAS 更新镜头为 submission_intent，设置 `generation_intent_recorded=1`，同时追加真实镜头事件和本地 gate 审计；任何审计失败立即整事务回滚。
5. SDK COMMIT 后仅返回**没有 ID、金额、任务或身份资料的离线检验标记**。无论结果是否成功，始终 `authorizes_paid_provider_call=false`、`may_automatically_retry=false`。

## 故障注入验收

- 两 Worker 的不同真实镜头同时占用同一个 0.60 美元 Provider 日限额，每个希望预留 0.40 美元；只允许一笔原子 held+intent+三项审计提交。
- Worker 名称、领取 attempt、epoch、租约过期或 deadline 不匹配时拒绝写入；pause/resume 后旧 token 不能复用。
- 未配置三级预算、金额不合法时拒绝并保持原数据库状态。
- 预算事件失败或末尾 gate 审计失败：所有插入/任务状态/预算/审计一起回滚。
- 真正 native libSQL 本地 COMMIT 持久后人工模拟 ACK 丢失：独立读回仍为且仅为一套 held+intent+审计；同样的调用 **禁止自动重复**，报告保留 `intent_uncertain`，不释放预算，绝不能因此再次请求付费模型。
- 新测试明确加入第四项专用 native SDK CI 测试清单，确保不是被 pytest skip 掩盖。

## 需要单独新授权的事项

**本 PR 不包含真正的供应商付费请求或跨 Runner/远程数据库验证。** 本地原子性不代表云端 `BEGIN IMMEDIATE`、远端数据库时钟、网络 COMMIT 模糊恢复、供应商 API 幂等或多 Runner 同一持久 gate 已通过。所有生产/远端能力门禁保持关闭：

`remote_multiworker_concurrency_verified=false`、
`network_commit_recovery_verified=false`、
`production_backend_switched=false`、
`live_cutover_permitted=false`。

需要真实 TxLab 下一次 DDL/DML、运行跨 Runner 测试或任何收费模型前，必须另开审核和征求一次新的明确授权；已消耗的 TxLab v1/v2/v3 单次测试不得复用。
