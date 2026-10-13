# PR-31b2l1 — 真实 TxLab v3 多表实验候选（**默认禁用**）

**本 PR 只有代码和本地 Fake 合同测试；没有新的 v3 写入授权，没有实际远程 SQL，也不会改变生产流程。**

新增 `src/drama_factory/storage/txlab_multitable_v3_live.py`，将已经离线通过的 [v3 五表/外键/索引/触发器](PR31_TXLAB_V3_MULTITABLE_PLAN.md) 变为一个**限一次、无自动重试**的实验流程。新建 `.github/workflows/manual-isolated-libsql-txlab-v3.yml`，但运行 Job 有**永久锁止的 `if: false`**。只有用户给出**新的明确单次真实 TxLab v3 写入授权**，再经一个独立小 PR 解除锁止、复核四项 CI，才能人工执行**一次**。旧 v1/v2 写入授权和确认词绝不复用。

## 将来真正运行时严格顺序

1. 验证地址仅允许现有隔离 TxLab 主机 `ai-short-drama-factory-txlab-<org>[.<region>].turso.io`，禁止 `ai-short-drama-factory` 主库、其他 Turso 库及嵌入账号密码/路径的 URL。只使用 `DRAMA_TXLAB_DATABASE_URL` / `DRAMA_TXLAB_AUTH_TOKEN`，不注入原业务四个 Secrets。
2. 对目标连接执行并读回 `PRAGMA foreign_keys=ON`。这是**实验要求**，不是已声称远端通过。
3. 在执行**任何 DDL/DML 之前**用只读 `sqlite_master` 检查 `pr31_v3_*` 对象数必须为 **0**；上次半途失败留下任何 v3 表/索引/触发器都拒绝重复启动。若无法完成检查同样拒绝。
4. 逐条 `execute` 新表、部分唯一索引、四个审计不可修改触发器的 SQL；绝不 `executescript()`；完成后必须回读**恰好十个**预期对象，没有遗漏或同名替代。这些表全部是虚构的 `pr31_v3_*`，不复制真实业务数据。
5. 一次事务 INSERT 虚构任务、持有 40 分的预算、生成意图和初始审计。另一个事务故意写过预算、费用和临时审计后 `ROLLBACK`，校验回到 `held`、费用 NULL、事件数 1。
6. 在**没有并发 Worker**的情况下执行一次核销：预算→任务费用→追加审计→单次 COMMIT。使用**第二条独立连接**检查预算 45 分、任务 45 分和财务审计事件数 2。
7. 故意在事务内执行孤儿外键写入、重复非空供应商 Task ID、审计 UPDATE 和 DELETE，每次**只有预期的约束错误才算通过**；网络超时或锁竞争不算约束生效。全部测试性失败事务显式回滚，不再额外 COMMIT。
8. 最终仅输出固定布尔/计数和脱敏阶段类别，不输出 Token、URL、用户 ID、视频脚本或第三方 SDK 原始错误。**无 DROP/DELETE 清理、无第二次写入重试**；如果 CREATE/COMMIT 阶段失败，之前已提交的对象/记录可能存在，必须另行只读对账。

## 逐级验收，不越级宣布成功

- 本 PR 用 `sqlite3` 新建临时数据库进行合同注入测试（包括旧 v3 schema 预检拒绝、DDL 中途失败只留一张表而拒绝重试、COMMIT 已落库却丢回执、外键测试遇到网络错误不能误判通过、独立连接读回）。
- PR-31b2l0 的第四项固定 `libsql==0.1.11` SDK CI 继续运行**仅本地文件**。新候选的本地 Fake 通过与真实 SDK 本地测试通过，均**不是远程证明**。
- 即使未来独立 TxLab v3 真实通过，也只证明**此单次测试的五张虚构表/一个串行多表事务**。仍需完整生产 Schema、真实多级预算和 lease/fencing、跨 Runner 并发、断线恢复及正式迁移/回滚批准。工作流不会在本 PR 自动执行。

## 操作保护

- 新 Workflow 的 `if: false` 在 GitHub Actions 的 Job 开始之前阻断全部步骤。未来获授权的启用 PR 还必须保留 `main`、`run_attempt == 1`、完全一致的确认词，并用 GitHub Actions 只读 API 验证当前是该 v3 Workflow **第一次 `workflow_dispatch`**；任何重复调度、API 不可用或非当前 run ID 都拒绝写入。
- 新代码的 `run_live_v3()` 只有在 `operator_approved=True`、独立确认词和写入开关全部同时提供时才允许打开连接。当前 PR、普通 CI 和对外业务 API 都不提供这些条件。
- 绝不复用 v1/v2 已被消耗的授权，绝不触碰主库 `drama_drive_receipts_v1`、Drive 资产或付费模型。


## PR-31b2l2：提前准备的 v3 只读事故对账

原已验收的 [Manual isolated TxLab SELECT-only postfailure diagnostics](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/workflows/manual-txlab-readonly-diagnostics.yml) 增加 v3 **只读**汇总，不改变手动工作流、确认词或 v1/v2 结果：

- 用固定 `SELECT name FROM sqlite_master WHERE name LIKE 'pr31_v3_%'` 统计 v3 Schema 对象数，只有**恰好 10 个期望对象名称**才报告 `v3_schema_names_complete=true`。如果建表/触发器中途失败、只有部分对象，则报告数量和 `false`，**不能尝试自动补建或清理**。
- 只有对应表存在时，才读 `pr31_v3_reservation` 的 `held/reconciled` 与 NULL/45 分费用**总数**、`pr31_v3_job` 的意图/费用**总数**，以及 `pr31_v3_budget_event` 的 `held/reconciled` 事件**总数**。即使只有一个表存在，也不会 `SELECT` 不存在的其他表。
- 没有 `INSERT/UPDATE/CREATE/DROP/DELETE`，没有读取任何镜头、项目、Task ID、审计记录 ID、用户素材路径、Token 或整行 JSON。所有连接仍仅可使用现有独立 TxLab URL 和两项 TxLab 专用 Secrets。
- 某个只读阶段失败，只报告固定标签 `select_v3_schema` / `select_v3_reservation` / `select_v3_job` / `select_v3_budget_event`，**不会原样输出**可能包含密钥的 SDK 错误。
- 即使报告 v3 结构齐全、费用行和审计计数一致，也仅是**事后的状态观察**，不能证明网络异常的精确时间线或远程隔离、并发提交已通过。始终 `v3_remote_transaction_semantics_verified=false`。

这项工具提前完成，避免重演 v1/v2 写入后才临时补对账脚本的被动处理。本 PR 没有执行任何远端 v3 写入，也不需要重新配置 Secrets 或手动触发只读工作流。新 v3 写入仍需后续独立明确授权。
