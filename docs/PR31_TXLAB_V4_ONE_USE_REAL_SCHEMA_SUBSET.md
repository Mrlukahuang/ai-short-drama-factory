# TxLab v4 — 单次真实隔离 Schema 子集兼容性与 fenced 事务验收

## 真实远端一次性验收结果（2026-10-14）

**已实际执行，且授权已消耗，禁止再次派发。** 证据：[GitHub Actions #38505044059](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38505044059)：

- 工作流 `manual-isolated-libsql-txlab-v4.yml`，事件 `workflow_dispatch`、首次 `run_attempt=1`，完成状态 `completed/success`；Job `isolated-v4-one-use` 成功，远端执行的报告确实打印在该 Job 日志，而不仅是离线 CI。
- 原始远端脱敏 JSON 回执：`mode=isolated_live`，`isolated_v4_lab_verified=true`，`schema_objects_verified=22`，`exact_core_business_table_columns_rehearsed=true`，`synthetic_claim_intent_task_atomic=true`，`synthetic_three_scope_budget_held=true`，`rollback_and_independent_readback_verified=true`，`local_or_serial_epoch_pause_verified=true`，`no_automatic_retry=true`。
- 原始回执同时明确：`remote_multiworker_concurrency_verified=false`、`server_clock_lease_verified=false`、`network_commit_ack_loss_verified=false`、`full_production_schema_verified=false`、`vendor_billing_verified=false`、`production_database_touched=false`、`production_backend_switched=false`、`live_cutover_permitted=false`、`paid_provider_calls=0`。
- 防重入结论：**授权已使用**，安全收尾 PR 将手动 Job `if: ${{ false && ... }}` 永久锁止。历史脚本/文档中的运行步骤只留作追溯，绝不能再次操作或绕过。

## 授权与范围

用户于 2026-10-14 授权 **TxLab v4 单次真实隔离测试**。这只是独立、可丢弃实验库中的一次新 `pr31_v4_*` DDL/DML 演练。沿用此前已经配置的专用 `DRAMA_TXLAB_DATABASE_URL` / `DRAMA_TXLAB_AUTH_TOKEN` GitHub Secrets，并通过 `validate_lab_url` 严格限制主机名必须为 `ai-short-drama-factory-txlab-*.*.turso.io`（或等价该 validator 接受的隔离名），禁止生产库、原数据、Google Drive、外部付费模型。

这是**真实业务关键五表的字段/约束子集验证**，不是完整生产数据库的复制，也不是跨 Runner 并发。11 张新表（包括 4 张只含 synthetic ID 的 parent FK stub、writer gate 和事件表）、5 个新索引、6 个 append-only 触发器；一共 22 个全部以 `pr31_v4_` 开头的新对象。五张核心表 `shot_jobs`、`shot_job_events`、`budget_policies`、`job_budget_reservations`、`budget_reservation_events` 复制 `db.SCHEMA` 的真实字段与约束，仅将表名/FK 目标替换为新的 `pr31_v4_*`；所有父表都是虚构引用锚点，不含生产业务数据。绝不 `DROP`、`ALTER`、`CREATE IF NOT EXISTS`、旧表更新或自动清理。没有完整真实生产 Schema 已通过的声明。

## 一次事务演练（无供应商费用）

1. 使用唯一 v4 前缀目录预检查目标 `sqlite_master`：只要已有任何 v4 对象，直接失败，不覆盖、修复或自动重试。
2. 逐条执行 DDL（避免旧 SDK `executescript` 风险）；读回对象名称精确集合再提交。任何 DDL 失败，先前对象可能已提交，必须停下单独只读诊断。
3. 插入虚构的父实体、两个租约预置时间、三条 `0.60` 美元测试预算政策、一个 pending 镜头和 epoch=1/running writer gate。这里的金额只是 synthetic 整数/文字，不代表真实供应商 charge。
4. 在 **同一次 BEGIN IMMEDIATE** 模拟 `pending → leased → submission_intent → submitted`、一次 `0.40` 预算 held、一个 `SYNTHETIC_V4_TASK_001` 模拟 Task ID 以及镜头/预算/epoch 审计。先整笔 ROLLBACK 并核验所有表无变化，再执行唯一一次同样事务 COMMIT。
5. 新独立连接回读镜头和 hold，另一次事务把 writer gate 暂停/epoch=2 并追加事件，检测旧 epoch 条件更新 0 行。此**仅**验证同一 remote server 上的串行同库合同，不是跨 GitHub Runner 的抢写或数据库端时钟验收。
6. 原子事务之外，用预期 constraint rejection 验证非空 Provider Task ID 唯一、append-only 审计与 FK，全部回滚；再使用第三次连接读取最终状态和完整性。无任何外部 Provider 调用。

成功报告只含安全布尔标记与 Schema 对象数量，不含库 URL、Token、Job ID、资产、SQL 原文、私有业务信息或金额。失败只打印固定 stage/category；因为远端 COMMIT/DDL 可能已经持久化，任何失败都不得重新运行，必须另外只读诊断。

## GitHub Actions 原单次运行门禁（现已消耗并锁止）

新 `.github/workflows/manual-isolated-libsql-txlab-v4.yml` 只能通过 **main 分支的手动 workflow_dispatch** 启动，确认字符串精确为 `RUN_ISOLATED_TXLAB_V4_ONCE`。预防二次写入：

- YAML Job 层要求 `github.run_attempt == 1`、main 分支和确认字符串匹配。
- 在加载数据库 Secrets 及任何 SQL 前，用 GitHub API 读取该 workflow 既有 **所有**手动派发次数，必须 `total_count == 1` 且首条运行 ID 等于本次。第二次 workflow_dispatch、Re-run job、误操作都不能重走远端实验。
- 沿用与 v1/v2/v3 相同的 TxLab concurrency group，避免多个独立实验 Workflow 并行争抢同一目标。
- 确认后仍只运行受 `DRAMA_TXLAB_V4_CONFIRM` 和 `DRAMA_ENABLE_TXLAB_V4_WRITE` 双环境门禁、单独验证隔离域的 Python v4 入口。
- v1/v2/v3 以及本轮已使用的 v4 Workflow 均保持 `if: false` 永久硬锁；不得复用历史授权进行新写入。

历史执行说明：GitHub 连接器不支持创建新的 `workflow_dispatch`，2026-10-14 用户已从 GitHub 网页完成首次且唯一的 v4 手动测试。**禁止再次点击或重新运行**。

## 不覆盖的生产门槛

`remote_multiworker_concurrency_verified=false`、`full_production_schema_verified=false`、`server_clock_lease_verified=false`、`network_commit_ack_loss_verified=false`、`vendor_billing_verified=false`、`production_backend_switched=false`、`live_cutover_permitted=false`。真正跨 Runner 远端门禁、权限、外部计费、迁移/回滚仍按 PR-31c3/31d 分开申请授权。
