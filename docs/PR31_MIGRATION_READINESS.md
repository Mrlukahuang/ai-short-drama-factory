# PR-31a — SQLite → Turso 生产账本迁移的只读体检与安全设计

> **当前状态：仅离线体检，不迁移、不连接 Turso。** PR-30c 已在专用 Turso 成功镜像一条 Drive 元数据回执 [Actions #38279948391](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38279948391)，但**生产任务/审批/预算并未迁移**。PR-30c 一次性写入授权已用完。

## 不能直接把连接字符串换成 Turso

对当前代码 `src/drama_factory/db.py`、`jobs/shots.py`、`jobs/budgets.py`、`jobs/google_recovery.py` 逐项核对后，确认这些关键安全语义：

| 本地既有机制 | 目前实际依赖 | 远端迁移前必须证明 |
|---|---|---|
| `Database.connection()` | `sqlite3.connect(timeout=15)`，`PRAGMA foreign_keys=ON`，自动 commit/rollback；初始化会 `executescript(SCHEMA)` 并追加旧库迁移、回填 | 远端连接、事务、外键、初始化和旧版本迁移的行为不能直接套用；初始化器不得在只读核查时执行 |
| 镜头领取 `claim_next_job` | `BEGIN IMMEDIATE`，筛选 pending 后更新状态与尝试次数、增加审计事件 | 两个不同 Runner 同时领取必须最多成功一次，租约时间、尝试次数和审计与状态一致 |
| 付费生成意图 | `leased → submission_intent → submitted`，状态变化与日志在同一事务，提交意图发生在真正付费请求之前 | 提交意图成功但供应商回应丢失时不能自动二次付费；`provider_task_id` 唯一约束、幂等键和恢复流程必须保留 |
| 预算 `reserve_job_budget` | `BEGIN IMMEDIATE` 下同时读取栏目/剧集/Provider 的版本化额度、同日已花/预留/并发计数，再插入 held 回执 | 跨 Runner 并发预留不能双花；美元用 decimal 字符串而不是 float；策略快照、唯一键、事件需原子写入 |
| 旧失败与回收 | `held` 预算预留、`leased` 超时 Worker、`submission_intent` 不确定请求、`google_existing_files.recovery_active` 锁 | 切换期间必须停写、盘点、人工核对未结算状态；不应自动清除或当作安全重试 |
| 资产账本 | `stored_artifacts`、`drive_artifacts`、`drive_artifact_events` 与本地不可变存储目录互相引用 | 迁移 SQL 行**不等于**已经迁移 MP4 文件；需单独核实 Drive 文件、哈希、授权及恢复路径 |
| SQLite 强约束 | `CHECK`、外键、部分唯一索引、追加式 `BEFORE UPDATE/DELETE` 触发器、`PRAGMA journal_mode=WAL` | 在真实目标 Turso/libSQL 版本逐项独立核实 SQL DDL/事务语义；不假设 WAL PRAGMA 或触发器行为等同 |

## 本 PR 新增的只读体检器

`src/drama_factory/storage/migration_readiness.py` 只接受操作者指定的**已存在的本地 SQLite 文件**。不构造 `Database()`，避免它的 `CREATE TABLE`/`ALTER TABLE`/`UPDATE` 自动迁移副作用；而是使用 SQLite URI `mode=ro`、`PRAGMA query_only=ON`、一致的只读 `BEGIN` 快照和 `rollback` 结束快照。

执行示例（不会尝试远端连接；不要针对未授权的共享或线上数据库运行）：

```bash
python -m drama_factory.storage.migration_readiness \
  --source /path/to/your-existing-local.sqlite3 \
  --confirmation INSPECT_LOCAL_SQLITE_READ_ONLY
```

输出脱敏 JSON，只包含：本地数据库结构 SHA256 指纹、表数量、必需表/列缺失情况、`PRAGMA quick_check`、`PRAGMA foreign_key_check` 计数，以及以下**汇总计数**：

- `leased_jobs`：当前尚被 Worker 领取的任务。
- `uncertain_submission_jobs`：`submission_intent` 或 `submitted` 状态，不能不核实供应商就重新调度。
- `unreconciled_vendor_intents`：已记录生成意图但未有核实供应商结算金额，即使标记失败也要人工核实。
- `held_budget_reservations`：仍占用额度的预留。
- `active_google_recoveries`：尚持有 Google 文件恢复锁的任务。

**不会**输出剧本、小说内容、项目名称、路径、资产 ID、Drive ID、供应商 Task ID、金额明细、Token 或原始数据库错误堆栈。所有检查只读、不修复坏外键、不创建缺失表、不向 Turso 传输用户行数据。不存在的路径直接拒绝且不会创建新 SQLite 数据库。

`offline_snapshot_checks_passed=true` **仅表示这次离线结构/完整性/未结状态检查通过**。即使显示为 `true`，报告中的 `live_migration_authorized=false`、`live_cutover_permitted=false` 永远保持关闭，直到后续专门 PR、远端事务/并发验证、恢复方案、授权全部完成。真实源库的同时写入还需额外一致性冻结流程；此体检器不执行锁库或快照导出。

## 后续 PR-31 拆分建议

1. **PR-31a（本次）**：只读风险体检器、离线测试和风险/流程文档。**不触碰现有云端数据**。
2. **PR-31b**：纯离线 FakeRemote/SQLite 演练远端事务抽象，明确支持 `BEGIN`/commit/rollback、唯一约束、审计事件原子性；压测双 Worker 抢单和三层预算竞争。严禁在模型调用路径自动切换后端。
3. **PR-31c**：导出/导入的可核验快照契约（表顺序、外键检查、逐表计数、哈希摘要、敏感列保护）；离线恢复和回滚演练；保留只读报告、暂停写入与反向切回步骤，不覆盖专用 `drama_drive_receipts_v1`。
4. **PR-31d 之后**：经过另行人工批准、专用隔离环境备份后才测试真实 libSQL 的事务、触发器、索引和并发，最终才讨论 Worker 切换、数据恢复和正式生产迁移。每一步需要可验证的实际 GitHub Actions 结果；未经授权**不迁移或删除任何真实库中的表**。

## PR-31b0：源 SQLite 真实多线程原子性基线

除了原有依次执行的预算/租约测试，增设四项**共享同一个临时 SQLite 文件、使用不同独立连接的真实线程竞争**：

- 8 个并行 Worker 同时争抢 2 个待处理镜头：必须恰好 2 个不同镜头被领取一次，`attempts=1` 且各自仅产生一条 `claimed` 事件；无多余的供应商 Task ID。
- 两个已领取的镜头同时申请各 0.40 美元、额度只有 0.60 美元：必须一人持有、一人被拒绝，持有总额仍为 0.40，预算事件仅一条，实际付费意图为零。
- 在镜头领取事务的事件入库故意抛异常：领取状态、尝试次数和审计一并回滚。
- 在预算预留事务的事件入库故意抛异常：预算预留/事件一并回滚，已有租约仍有效。

这些是**本地 SQLite 的已实现语义基线**，不是 Turso、libSQL 或跨 Runner 的远端并发证明。将来所有候选远端实现需在相同合同下独立跑出证据；只有真正的 Turso 事务/并发验收通过才可考虑迁移 Worker。

## PR-31b1：隔离的后端接口合同（离线）

`storage/ledger_backend_contract.py` 明确了现有 `jobs/shots.py`、`jobs/budgets.py` 实际使用的 `LedgerBackend` 结构接口：`connection()`、`one()`、`many()`、`exec()`，每次事务有显式 `BEGIN IMMEDIATE`、支持 rollback、外键、按字段读取。新增的 `OfflineSqliteLedger` **仅能打开已存在的本地 SQLite 文件**、必须手动传入 `offline_test_only=True`，拒绝 `libsql://` URL，并且**不调用初始化/迁移器**。

测试直接以这个候选对象（而非生产 `Database` 实例）调用现有真实镜头领取和三级预算函数，重演两个并发竞争、审核异常时事务回滚，证明业务代码可以使用隔离的交易接口。此结果**不是 Turso 实现**；该候选是第二套 sqlite3 连接器，目的仅为锁定可注入接口的依赖范围和原有不可变语义。既不替换 FastAPI/Worker 当前默认数据库，也不在运行时加载 Turso SDK。

合同 JSON `export_offline_contract_metadata()` 将 `remote_sql_transaction_verified`、`remote_concurrency_verified`、`production_backend_switched`、`live_migration_authorized` 保持 false。真正远端适配器需要另建、新授权、跨 Runner 压测及失败恢复；不能由此获得任何生产开关。

## 安全测试

`pytest -q tests/test_migration_readiness.py` 覆盖不存在文件拒绝且不创建目录、只读扫描前后字节一致、异步/不确定计费与预留锁阻断、外键损坏不修复、旧版缺表/缺列拒绝、异常输出脱敏，以及不导入 Turso/Drive/图像 SDK。常规 Python 3.11/3.13 CI 自动运行，默认无云凭据、无需 FFmpeg 或网络。

重要：**这不是 PR-31 完成，也不提供生产迁移开关。** 从临时 Runner SQLite 迁到持久云端仍是独立工程。
