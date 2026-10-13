# PR-31b2a：专用隔离 libSQL 事务实验库（**仅准备工作流，尚未真实运行**）

## 为什么需要另一份 Turso 库

已有短剧专用 Turso `ai-short-drama-factory` 已通过 PR-30b 只读连接和 PR-30c 单条 `drama_drive_receipts_v1` 元数据写入。上一次 PR-30c 的**一次性写入授权已用完**，不能拿它继续试验新表、事务、并发冲突或故障恢复。**禁止在那份库上运行 PR-31b2a。**

本 PR 为今后的**单次手动**新实验增加代码和 Workflow。实验必须使用另外创建的独立、可丢弃数据库：

- 新建的 Turso DB **名称**：`ai-short-drama-factory-txlab`（与既有 `ai-short-drama-factory` 不同）。
- 引擎仍选择 **libSQL / SQLite**，尽量选与原库相同的 Sydney 地区，以便测试同种引擎/区域；不改变原有数据库引擎。
- 在 Turso 后台新生成**仅绑定 txlab 实验库的 Token**，不要使用原短剧库的 `DRAMA_TURSO_AUTH_TOKEN`。
- GitHub Repo Actions Secrets 必须新建 **`DRAMA_TXLAB_DATABASE_URL` 和 `DRAMA_TXLAB_AUTH_TOKEN`**；不修改/复用原有四个 Drive/Turso Secrets，更不能把 Token 发送到聊天、截图或 Issue。
- SDK 使用 `libsql`；CLI 对 URL 的主机名做严格校验，**仅允许** `libsql://ai-short-drama-factory-txlab-<org>[.<region>].turso.io`，明确拒绝原库、`nz-social-trend-radar`、账号密码嵌在 URL 和自定义查询字符串。

**尚未请求或使用用户的这次真实新写入授权**。在用户明确创建新的实验库并允许一次远程事务写入后，再手动使用下方 Workflow。普通 Python/FFmpeg CI 使用内存/临时 sqlite3 文件，不能运行真正的远程写入。

## 手动 Workflow（只对已审查的 main）

`.github/workflows/manual-isolated-libsql-txlab.yml`

工作流只可手动 `workflow_dispatch` 运行，Branch 必须是 `main`，确认词为：

```text
RUN_ISOLATED_LIBSQL_TRANSACTION_CANARY
```

它只读取两项新的 TxLab Secrets，绝不注入原短剧生产库的 URL/Token，也不读取 Drive、Google 视频或其他 Provider 凭据。专用 Runner 上安装 `turso-libsql` 依赖，不启动视频 Worker，也不调用付费模型。

**本次实验会修改新建的 txlab 实验库**，受限操作如下：

1. `CREATE TABLE IF NOT EXISTS pr31_txlab_transaction_probe_v1`，只包含技术模拟主键、计数器和唯一标记。
2. `INSERT` 一条带随机技术标记的新测试行并提交。
3. `BEGIN IMMEDIATE` 内修改本行计数器 `+5`，`ROLLBACK`，检查改动没有持久化。
4. 开两条独立 libSQL 连接，同时争抢同一行；每条显式 `BEGIN IMMEDIATE`、读取当前值、`UPDATE` 加一、提交；最终必须是 **2**，不能丢失任何一次更新。
5. 故意尝试重复主键的 `INSERT`，要求数据库拒绝并在 `ROLLBACK` 后保留原来计数值。
6. 只向 Job 日志输出脱敏 JSON 布尔结果；不能输出测试行 ID、Token、数据库 URL、真实用户 ID 或 SDK 原始异常堆栈。

**失败请勿盲目重跑**：DDL/INSERT 可能已经在远程提交，测试失败并不代表库未修改。应先读取脱敏 Actions Job Logs 和数据库状态，决定是否需要重新授权。实验**不执行 DROP/DELETE、库迁移、正式 Worker 切换、部署或任何真实供应商调用**。历史测试行会留在专用 txlab 库中，后续人工清理需要另外的审查与授权。

## 结果边界

如果这一次实验全绿，仅能证明**指定 libSQL Python SDK、两个独立连接在这个事务序列中**符合需求；仍不代表跨 GitHub Runner/跨地区分布式原子性、任意网络中断、完整 Schema/触发器兼容、真实预算/审批账本迁移或生产切换已经通过。

离线测试还包括“主库 URL 强制拒绝、缺少独立授权不可连接、重复主键拒绝、事务回滚、故障没有自动重试、日志错误脱敏、工作流只有 main/人工触发且不注入旧凭据”。真正大规模并发、断线恢复、Worker 故障/付费幂等仍在 PR-31b2b、PR-31d 之后单独设计。
