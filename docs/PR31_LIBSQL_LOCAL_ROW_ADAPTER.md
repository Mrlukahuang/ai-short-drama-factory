# PR-31b2o0 — libSQL SDK 本地 Row / Cursor / Transaction 适配器合同

> **仅一次性本地 CI 测试用的实验接口**。不包含 Turso URL、Token、云端连接、生产 Worker 替换、远程费用、实际照片/视频。已通过的独立 v3 一次写入授权仍然用尽。

## 发现的真实差异

在 [PR31_REAL_LEDGER_LIBSQL_SDK_CONTRACT](PR31_REAL_LEDGER_LIBSQL_SDK_CONTRACT.md) 中，`libsql==0.1.11` SDK 的 `fetchone()` 直接返回 tuple；但 [shot jobs](../src/drama_factory/jobs/shots.py)、[budget policies](../src/drama_factory/jobs/budgets.py) 及现有 `LedgerBackend` 依赖 `row["status"]`、`row[0]`、`dict(row)` 等混合语义。

**不能直接将 SDK 的 native Cursor/Connection 代入现有业务模块**，否则在生产数据更新前的读查询即可能失败，或未来在多表 JOIN 的同名列上拿错数值。

## 本轮实现

新增 `src/drama_factory/storage/libsql_sdk_local_ledger.py`：

- `NamedSdkRow(Mapping)`：按 SDK Cursor 的 `description` 映射查询值，支持列名、整数序号、`dict(row)`；**列名有重复或行宽不一致立即拒绝**，不通过覆盖前一列制造静默账目错误。
- `NamedSdkCursor`：`fetchone/fetchall` 都返回统一的行表示；`rowcount/lastrowid` 明确转发而不是靠动态属性猜测。
- `LocalNativeLibsqlLedger`：`connection/one/many/exec` 兼容已有 `LedgerBackend`；每条独立连接都设置并验证 `PRAGMA foreign_keys=ON`；连接上下文正常提交，异常回滚，始终 close。没有修改原 `db.Database` 的业务实现。
- 构造时**同时要求** `offline_test_only=True`、已存在的无 symlink 本地 SQLite 文件，以及单独的 `pr31_native_libsql_local_test_marker`，否则拒绝。库中**不提供“给任意已有数据库打上标记”的公开函数**，避免误对生产文件启用实验适配器。打标操作仅存在于 pytest 原创临时文件 fixture。
- SDK 在 `connection()` 内按需 import；正常生产流水线不安装 SDK 也可以继续使用原 SQLite。
- 公开的安全状态始终 `remote_sql_semantics_verified=false`、`remote_concurrency_verified=false`、`production_backend_switched=false`、`live_cutover_permitted=false`、`paid_provider_calls=0`。

## Native SDK 必须实际通过的业务测试

新的 `tests/test_libsql_sdk_local_ledger_adapter.py` 已加入 GitHub Actions **强制真实 SDK 本地 CI**，不用 FakeProvider 或 Turso：

1. 现有普通 SQLite 项目文件因缺少专用标记而被拒绝，不对它写入测试 marker。
2. 行转换支持 `row["status"]`、`row[0]`、`dict(row)`，重复同名列必须拒绝，不允许 silent overwrite。
3. 实际业务函数 `prepare_shot_jobs`、`claim_next_job`、`configure_policy`、`reserve_job_budget`、`record_submission_intent`、`record_operator_verified_charge` 对原有九表/生产业务数据合同工作。
4. 在费用核销审计失败时，预算预留、镜头已记费用、事件写入应全部回滚。
5. 在镜头领取后的审计失败时，领取状态/attempts/lease owner 应恢复为 pending/0/NULL，不能留下半笔镜头尝试或未来重复计费机会。
6. 所有测试数据均在 CI 新建本地 SQLite，使用真实 libsql 扩展但**没有 SDK 远端 URI/Secrets**，禁止并发实测误称远端 Worker 通过。

**对未来的限制**：此适配器没有处理远端连接池、真实异常类别分级、COMMIT 回执丢失时的只读对账、跨 Runner 租约 fencing 和实际生产多 Worker 争抢。这些在真正 libSQL 远端部署前都需要新的隔离验收。即使本阶段全部 CI 通过，也不能启用云端生产 Worker。

## 下一步

- PR-31b2o1（先离线）：真实业务函数在 native SDK 上的并发 Worker/Budget 锁竞争与错误分类预检，不能未经确认就在失败时自动重试。
- 如未来需用独立 TxLab 做**新的多表真实业务 Schema 测试**，必须先取得新的单次写入授权；旧 v1/v2/v3 的一次性工作流继续锁止。
- PR-31d 的正式 SQLite 迁移、生产停写/恢复窗口仍未获授权或验证。
