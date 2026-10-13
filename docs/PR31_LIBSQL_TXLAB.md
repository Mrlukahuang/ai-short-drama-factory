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

## PR-31b2d：单写锁争抢的离线安全重试边界

新增纯离线 `storage/txlab_retry_policy.py` 与测试 fixture：两个 sqlite3 连接，**不等待写锁**，一个 `BEGIN IMMEDIATE` 先占有写锁，第二个 `BEGIN IMMEDIATE` 当场得到 `SQLITE_BUSY`。第一连接随后成功提交，记录计数自然为 1；这不是数据库丢失已提交的更新，而是**第二次写入压根未取得事务写锁**。只有人工确认第一次事务已经结束并新建连接后，第二次技术性写入才能单独执行，计数变 2。**这是本地复现的机制，并不是对之前云端失败异常的事后实锤。**

测试明确以下重试判定：仅当已证实数据库明确以 `SQLITE_BUSY` 拒绝 **`BEGIN` 本身**、从未执行写 SQL，且此前重试为 0 次，才可以考虑**一次有界的前置锁竞争重试**；否则必须交给人工或专门的可恢复事务协议检查。特别是 `worker_update`、`worker_commit`、超时、网络断线和未知事务结果，即使标记为 busy，也一律**不能自动重发**。该模块仅返回推荐决策数据，**不包含自动重试代码，不与真 TxLab/Production Worker 连接**。原真实写入 Workflow 仍锁止，没有任何新云测试授权。

正式使用前还需要新隔离库的实测确认：服务器异常码确认为锁竞争、提交结果的查询/幂等办法、退避次数、终止条件及计费副作用，不能将这套本地实验直接视为已经验证 Turso SDK 的重试安全。

## PR-31b2e：准备第二版隔离远程测试（2026-10-13，**仅离线代码完成后待新授权**）

此前真实实验 [Actions #38342320367](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38342320367) 失败、两次只读 [#38358995649](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38358995649) / [#38362170364](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38362170364) 确认唯一探针计数为 1。还不清楚真实错误究竟为锁冲突还是其他因素，不允许解释为已验证远程双 Worker 原子性。

新的独立候选 `storage/txlab_v2.py` 避免强求两个同时争抢的 Writer 都必须成功：

- 在**新的** `pr31_txlab_v2_probe_v1` 表插入一条随机技术记录（不读取、覆盖或删除旧 v1 测试行），验证显式 `BEGIN IMMEDIATE` 和 `ROLLBACK`。
- 先让两条独立连接**串行**各提交一次，把已确认的计数校验为 2，建立无写锁冲突的基本事务基准。
- 再让两条独立连接同时尝试 `BEGIN IMMEDIATE`；逐次区分 **committed** 和服务器已明确返回的 **SQLITE_BUSY at BEGIN**。如果存在正常锁冲突，不把拒绝的请求误当成一个已经成功提交的事务；若获得锁的连接成功提交，最终 counter 应等于已确认总提交数。
- 遇到 `UPDATE`、`COMMIT` 超时或未知错误**立即失败且不自动重试**；只输出固定脱敏 `stage/category`，不能把模糊提交看作“没有写入”。
- 额外验证主键重复被拒绝、只输出测试总数和布尔报告，不输出行 ID、marker、URL、Token、SQL SDK 异常详情。

**本实现并不证明远端已经成功**：以上均先用新临时 SQLite Fake/真实本地并发测试，`remote_distributed_concurrency_certified=false` 永远关闭。原短剧生产数据库、正式 Worker、审批和费用预算完全不参与。

新工作流 `.github/workflows/manual-isolated-libsql-txlab-v2.yml` **最初使用 `if: false` 锁止**。旧的 `RUN_ISOLATED_LIBSQL_TRANSACTION_CANARY` 授权已经用完。随后用户于 **2026-10-13 明确授权一次 TxLab v2 真实写入验收**；PR-31b2f 在单独经过 CI 的修改中将本次 v2 工作流解锁，增加 `github.run_attempt == 1` 以及 GitHub Actions API 对该工作流历史 `workflow_dispatch` 次数/本次 run ID 的检查：**仅第一次手动运行满足门禁，重跑或新发起第二次均拒绝写入**。GitHub API 不可用或不一致时也拒绝写入；不能靠这项机制证明远程事务安全。原来两项 TxLab 专用 Secrets 继续使用，无需更换，不注入原短剧主库 Secrets。成功也只说明这一次 SDK/数据库测试场景，不构成真实生产切换、跨 Runner 并发、断线重试安全的最终证明。

## PR-31b2f：一次性真实 v2 验收授权的操作说明

**操作者已授权单次真实 TxLab v2 事务测试，但尚需 GitHub Actions 手动触发；PR 合并与常规 CI 全绿不等于已经执行真实写入。**

- 手动入口：[Manual isolated TxLab v2 one-time transaction verification](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/workflows/manual-isolated-libsql-txlab-v2.yml)，分支必须为 `main`。
- 确认词仅为 `RUN_ISOLATED_TXLAB_V2_ONE_TIME`。这是**新** v2 工作流，不是旧的 `manual-isolated-libsql-txlab.yml`，也不是仅 SELECT 的诊断工作流。
- 预检先查询该工作流的 GitHub 历史记录，确认这是首次手动调度，且 `run_attempt=1`，才会把新 TxLab 凭据注入真实试验步骤。初次执行完**不要点击 Re-run jobs 或重新 Run workflow**；如出现红灯须先查已有 v2 记录，不能盲目第二次写入。
- 本次授权仅限旧用户独立 TxLab 的新 `pr31_txlab_v2_probe_v1` 表、单条技术记录、有限次回滚/串行和竞争更新/主键检验；**不读取或修改原短剧库、旧 v1 测试表或生产账本，不调用任何付费 AI**。
- 真实运行日志只会输出已验证提交次数、明确被拒绝的 `BEGIN` 次数和脱敏的失败阶段/类别。远程跨 Runner、真实计费供应商幂等、网络故障/回滚均继续标为未验收。
- 工作流只读权限为仓库内容和 Actions 运行历史；不会使用写 GitHub Issue/PR/Secret 权限。

## 结果边界

如果这一次实验全绿，仅能证明**指定 libSQL Python SDK、两个独立连接在这个事务序列中**符合需求；仍不代表跨 GitHub Runner/跨地区分布式原子性、任意网络中断、完整 Schema/触发器兼容、真实预算/审批账本迁移或生产切换已经通过。

离线测试还包括“主库 URL 强制拒绝、缺少独立授权不可连接、重复主键拒绝、事务回滚、故障没有自动重试、日志错误脱敏、工作流只有 main/人工触发且不注入旧凭据”。真正大规模并发、断线恢复、Worker 故障/付费幂等仍在 PR-31b2b、PR-31d 之后单独设计。
