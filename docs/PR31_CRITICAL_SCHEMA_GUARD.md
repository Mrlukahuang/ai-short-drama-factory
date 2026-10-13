# PR-31b2j：镜头/费用账本关键 Schema 保护检查（**仅本地只读**）

## 为什么检查这些结构

PR-31b2i 已将真实镜头任务与预算/审计原子性作为**本地 SQLite** 的回归基线，但同样的 Python SQL 连接抽象和成功 `SELECT 1` 不等于**远端 Turso 数据库导入了同样的约束**。例如：如果迁移了任务与账单行，却遗漏 `UNIQUE(provider,provider_task_id)` 的非空部分唯一索引，重复供应商 Task ID 可能不再被数据库阻断；遗漏审计表的 UPDATE/DELETE 触发器会破坏历史不可改证据。

新增 `storage/critical_ledger_schema.py`，只读扫描**现有本地 SQLite 文件**，必须显式 `offline_review_only=True`，只通过 SQLite URI `mode=ro` + `PRAGMA query_only=ON` + `BEGIN` 一次一致性读取。仅查询 `sqlite_master`、固定 `PRAGMA index_list/index_info/foreign_key_list` 和 `quick_check/foreign_key_check`，不调用自动建表/迁移器，不读取任何业务行的文本、身份或金额明细，不创建副本，也不连接云端。

## 必须完整保留的结构

| 保护点 | 具体校验 |
| --- | --- |
| 五张核心业务表 | `shot_jobs`、`shot_job_events`、`budget_policies`、`job_budget_reservations`、`budget_reservation_events` |
| 五个显式索引 | `idx_shot_jobs_provider_task`、`idx_shot_jobs_series_status`、`idx_shot_events_job`、`idx_budget_policies_scope`、`idx_job_budget_daily` |
| 关键唯一约束 | 镜头 `idempotency_key` 唯一、同一镜头至多一笔预算预留，以及 **`provider+provider_task_id` 唯一且仅针对非空 Task ID 的部分索引** |
| 四个不可修改审计触发器 | `shot_job_events` 与 `budget_reservation_events` 的 `BEFORE UPDATE` 和 `BEFORE DELETE`，名称正确还不够，必须能找到 `RAISE(ABORT)` 的阻断逻辑 |
| 五条关键外键 | 任务事件→镜头、预算预留→镜头/栏目/剧集、预算事件→预留 |
| 数据完整性 | `PRAGMA quick_check(10)` 与 `PRAGMA foreign_key_check` |

CI 使用真实 `Database` 生成全新临时 schema，再故意删去部分唯一索引、把同名不可改审计触发器替换为无效 `SELECT 1`、建缺失外键/唯一约束的破损测试库、以及插入孤立外键。这些都必须被报告为 blocker；报告只输出约束类别、固定错误代码、结构 SHA-256 与计数，不包含原始 SQL、行 ID、剧本文本、DB 路径或任何 Secret。

## 边界与后续工作

此报告中的 `local_schema_safety_checks_passed=true` **仅证明当前本地样本具有这些结构**，不代表所有旧版 SQLite 结构细节已验证，更不代表真正远端 Turso 同一 Schema 通过。尤其并未验证完整触发器 SQL 与 Turso SDK、远程 `BEGIN IMMEDIATE`/交互式事务、租约/预算竞争、提交回执丢失及跨 Runner 持久停写。即使全部通过，输出中的 `real_remote_schema_import_verified=false`、`remote_transaction_atomicity_verified=false`、`production_backend_switched=false`、`live_cutover_permitted=false` 永远不开放。

真正的远端阶段必须另外创建隔离验证脚本与新授权，在**仅有独立 TxLab**的前提下验证同等 DDL、部分唯一索引、外键、不可改触发器和真实多表事务；原业务 Turso 的 `drama_drive_receipts_v1` 不能被触碰，原 SQLite 不被迁移或自动冻结，不能自动付费重试。
