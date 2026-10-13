# PR-31b2n — 真实生产账本 DDL 的 libSQL SDK 本地兼容验收

> **仅本地模拟**，没有读取任何真实账本、Turso URL/Secrets、Drive、付费 Provider，未修改生产 Worker，也没有新的远端写入授权。

## 相比 TxLab v3 本轮实际增加了什么

真实隔离 TxLab v3 [Actions #38417337745](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38417337745) 确认了五张**虚构** `pr31_v3_*` 表的串行多表原子性，但没有证明现有 `db.py` 的真实业务 DDL 能在 libSQL 上执行。

本轮不复制生产数据，而是在测试中对仓库的**真实 `db.SCHEMA` 字符串**用 SQLite 内存数据库建立仅供读取的 Schema Catalog；只提取固定白名单对象的真实 CREATE SQL，以 `libsql==0.1.11` 的 Python SDK **逐条 execute** 到新建的 `pytest.tmp_path` 本地数据库中。

白名单对象：

- 九张真实结构的业务表：`columns`、`projects`、`episodes`、`productions`、`shot_jobs`、`shot_job_events`、`budget_policies`、`job_budget_reservations`、`budget_reservation_events`。
- 六个显式索引：`idx_columns_slug`、`idx_shot_jobs_series_status`、`idx_shot_jobs_provider_task`、`idx_shot_events_job`、`idx_budget_policies_scope`、`idx_job_budget_daily`；包含现有 Provider Task ID 非空部分唯一索引。
- 四个真实不可修改审计触发器：镜头事件 UPDATE/DELETE、预算事件 UPDATE/DELETE。
- 测试仅写虚构 `test` / `synthetic` / `fake` 记录，不导入线上栏目、业务账单、视频素材或原始小说。

**SDK 使用说明**：用内存 sqlite3 构造受信任源码的 Schema Catalog 并不是使用 libSQL 的危险 `executescript()` 执行目标 DDL。真正被测的 libSQL SDK 每条 DDL 都用 `execute()`，且每个独立连接都设置并读回 `PRAGMA foreign_keys=ON`。这个地方延续 PR-31b2l0 的源码审查要求。

## 真实生产业务字段的离线断言

在上述**真正 Schema 形状**中，测试从虚构栏目→剧集→分集→生产 Run→镜头生成意图→三级预算政策→预算持有→任务/财务审计搭建最小链路，验证：

1. 完整 DDL/结构在本地真实 libSQL SDK 创建并能由独立连接读回，外键健康。
2. 人工预算核销写入预算行、任务行、财务事件三步中**任一失败都完全回滚**；成功一次后两表实际费用一致且只增加一笔审计。
3. 原真实外键拒绝孤儿事件，同镜头两笔预算持有不可重复、同一范围政策修订不可重复、任务及预算事件记录不可 UPDATE/DELETE。
4. **原生 `libsql.Cursor.fetchone()` 返回 Python `tuple`**，而现有 `jobs/shots.py` 和 `jobs/budgets.py` 依赖 `row["status"]` 等按列名取值。SDK 源码明确使用 `PyTuple` 且没有同 `sqlite3.Row` 等价的默认映射；本 PR 用真实 SDK 单独测试证实这种差异，而不是在迁移时才暴露。

本测试证明的是**本地 SDK 对仓库现有结构子集与合约操作的兼容性**，不是整个生产数据复制成功，也不是 libSQL 远端同样成功。实际业务函数仍使用本地 `OfflineSqliteLedger`；这里只是人工构造的业务动作 SQL，**不能宣称已经通过真实 Worker 多线程远端费用/租约竞争合同**。

## 下一步与授权边界

- **PR-31b2o0（先离线）**：增加 SDK tuple→按列名读取的独立适配器（同时处理列名歧义、参数/异常、事务上下文及 close），用**现有真实业务函数**做完整本地 SDK 合同测试；不要直接将原生 SDK 连接丢进生产 Worker。
- **PR-31b2o1（需新授权）**：新隔离 TxLab 中使用真实生产子集完整 DDL 的远端小规模兼容验收。原 v3 实验记录不改、不删除、不重用确认词。
- **后续独立批准**：跨 Runner Worker 租约/三级预算并发竞争、网络 COMMIT 回执丢失、资产 hash 恢复和生产停写/迁移回滚。已有 v3 一次写入许可已耗尽，生产切换仍 **false**。
