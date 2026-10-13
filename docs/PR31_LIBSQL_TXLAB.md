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

## 首次真实运行失败与安全诊断（2026-10-13）

用户授权并**仅执行一次**原手动工作流：[Actions #38342320367](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38342320367)，`main` commit `ff19daad419b94b57ac8b0c69309003ab7f826fe`，结果 `failure`。Python 3.11 和 `libsql 0.1.11` SDK 安装成功，两项 TxLab Secrets 存在并被 GitHub 遮盖，唯一失败步骤为 `Run exactly one isolated libSQL transaction canary`。步骤运行约 20 秒，CLI 的 SDK 异常被脱敏，**未能得知失败发生于连接、DDL、INSERT、BEGIN IMMEDIATE、并发或唯一约束**。尤其**不能把 failure 当作没有真实写入**；此测试可能已经创建表或提交测试行。

**重要：本次一次性远程写入授权已经使用，不得点击 Re-run jobs 或再次触发原事务工作流。**

### 新增仅 SELECT 的诊断入口

`.github/workflows/manual-txlab-readonly-diagnostics.yml`，名称 `Manual isolated TxLab SELECT-only postfailure diagnostics`。

- `workflow_dispatch` + `main` branch + 精确确认词 `CHECK_ISOLATED_TXLAB_READ_ONLY`；使用仅有的两项独立 TxLab Secrets，**不会**注入或使用原数据库/Drive 凭据。
- 入口代码 `src/drama_factory/storage/txlab_readonly_diagnostics.py` 严格验证 `ai-short-drama-factory-txlab` 主机名，仅做三条预定义 SELECT：`SELECT 1`、`sqlite_master` 指定测试表是否存在、若存在则用 `COUNT`/`SUM` 按 `counter=0/1/2/other` 统计测试记录。**零 DDL/DML，不调用原事务 Canary，不自动重试，不打印任何随机 Probe ID、行标记、Secret、URL 或原始 SDK 错误**。
- 如果 SELECT 失败，CLI 只记录已固定的脱敏阶段：`target_validation`、`connect`、`select_ping`、`select_schema`、`select_counter_summary`。即使成功，也只知道当前表和汇总行状态，无法完全重建之前每一个事务是否提交。
- 正式诊断结果出来后才选下一步；若是 SDK/事务行为问题，先离线修好再决定是否需要**新的**真实写入授权。不得删除现有表或擅自清理测试行。

## 首次只读检查的实测结果与后续保护（2026-10-13）

下面是两次实际 GitHub Actions 只读运行的**观测记录**，不是推测：

- [Actions #38358995649](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38358995649)，`completed/success`。
- [Actions #38362170364](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38362170364)，`completed/success`。
- 两次都在隔离 TxLab 库完成 `SELECT 1`，`test_table_exists=true`；`total_probe_rows=1`，其中 `counter_one_rows=1`、`counter_zero_rows=0`、`counter_two_rows=0`、`counter_other_rows=0`；`database_modified_by_this_check=false`。
- 由此证实先前失败的写入 Canary **确实留下一条实验记录，计数为 1**。不过聚合查询无法确定事务失败的精确 SQL 阶段；不能把“计数为 1”直接解释为已证实的 lost update。
- Turso/libSQL `BEGIN IMMEDIATE` 采用写锁竞争，第二个并行写事务可能收到 `SQLITE_BUSY`。这与观测一致，但是**待验证假说**，并非第一次 Run 的 SDK 实际错误码。参阅 [Turso 事务手册](https://github.com/tursodatabase/turso/blob/main/docs/manual.md) 和 [Turso 关于交互式事务锁竞争的说明](https://turso.tech/blog/batches-in-sqlite-838e0961)。

### PR-31b2c：避免模糊错误与误触发二次写入

- 原工作流 `.github/workflows/manual-isolated-libsql-txlab.yml` **永久安全锁止为 `if: false`**，即使用户再次输入旧确认词，也不会执行真实 SQL 写入。未来新的真实运行必须另开独立 PR、更新工作流及确认新授权。
- 事务测试代码的阶段在代码内限定为固定枚举，归类仅为 `busy` / `timeout` / `connection` / `constraint` / `unknown`；在下一次**获得全新授权**的隔离测试发生失败时，只打印脱敏 `stage` 和 `category`。SDK 异常原文、SQL 用户输入、测试行 ID、Token、库 URL 一律不输出。
- 离线回归用 Fake SQLite 注入 `SQLITE_BUSY`，验证只留下已提交的部分测试行、不悄悄重试、不将锁错误误判为事务原子性成功；原既有案例继续在 Python 3.11/3.13 CI 运行。
- **不在本 PR 执行任何新的真实 TxLab DDL/DML**，也不申请清理上一次留下的实验行。原短剧主库 `ai-short-drama-factory` 的元数据、Secrets 和任何数据均不受影响。
- 仍需后续另外设计可证实的锁竞争与重试策略：必须区别“未开始事务前安全重试”和“提交可能成功但回执丢失时不安全重试”，并在新的独立实例环境验收；不能把自动无限重试塞入付费 Worker。

## 结果边界

如果这一次实验全绿，仅能证明**指定 libSQL Python SDK、两个独立连接在这个事务序列中**符合需求；仍不代表跨 GitHub Runner/跨地区分布式原子性、任意网络中断、完整 Schema/触发器兼容、真实预算/审批账本迁移或生产切换已经通过。

离线测试还包括“主库 URL 强制拒绝、缺少独立授权不可连接、重复主键拒绝、事务回滚、故障没有自动重试、日志错误脱敏、工作流只有 main/人工触发且不注入旧凭据”。真正大规模并发、断线恢复、Worker 故障/付费幂等仍在 PR-31b2b、PR-31d 之后单独设计。
