# PR-31b2i — 多表任务/预算/审计原子性验收合同（离线基线）

## 真实来源与验收边界

本阶段的参考不是抽象 Counter，而是仓库中现有的业务函数：

- `jobs/shots.py` 的 `claim_next_job`、`record_submission_intent`、`record_submission`。
- `jobs/budgets.py` 的 `reserve_job_budget`、`record_operator_verified_charge`。
- `shot_jobs`、`shot_job_events`、`job_budget_reservations`、`budget_reservation_events` 四张已有生产业务表。

实际 TxLab v2 只读诊断 [#38383515455](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38383515455) 报告 `v2=3`（此前已提交的两次串行增量 + 另外一次并发成功），另一并发线程在 `worker_read / busy` 失败。这次读回**不证明整个远端多表事务合同**，也不说明有已提交的值被覆盖。此后的实验均须保留失败时的**不确定账单、不可自动再次付费**原则。

## 当前业务真实事务边界

| 边界 | 成功时需持久化的一组状态 | 失败时必须保持的旧状态 |
| --- | --- | --- |
| 领取 Worker 镜头 | `shot_jobs.status=leased`、尝试次数/租约、`shot_job_events.claimed` | `pending`、旧尝试次数、无 claimed 事件 |
| 三级预算预留 | 同一笔 `job_budget_reservations.held`、三层政策的一致限额判断、`budget_reservation_events.held` | 无半笔预算预留、无对应 audit，原租约保持 |
| 记账“可能已计费” | `shot_jobs.status=submission_intent`、`generation_intent_recorded=1`、`shot_job_events.generation_intent_recorded` | `leased` 和 `generation_intent_recorded=0`，已有 `held` 预算仍然占用；不会伪造已提交供应商请求 |
| 保存已返回的供应商 Task ID | `shot_jobs.status=submitted`、`provider_task_id`、`shot_job_events.provider_task_recorded` | 原 `submission_intent`、任务 ID 为空但**仍需人工对账**，不允许重复付费提交 |
| 人工核销供应商费用 | `job_budget_reservations.status=reconciled`、`actual_usd`、凭据及审核员；`shot_jobs.actual_vendor_charge_usd`；`budget_reservation_events.operator_entered_vendor_charge` | 预算仍为 `held`，费用与凭据未记录，任务仍为 `submission_intent` / `submitted`，不丢审计 |

`reserve_job_budget` 与 `record_submission_intent` **在现有系统中本来就是两个独立事务**：必须先提交预算持有，才能持久化外部供应商生成意图，然后才能发出可能计费的请求。不要为了“少几个 SQL 往返”擅自把这些外部阶段塞进一个持有远程写锁的长期事务里。

## 本 PR 的离线实测合同

新增 `tests/test_remote_ledger_atomicity_baseline.py`，实际通过 `OfflineSqliteLedger` 调用已有业务函数，绝不替换主生产适配器。

1. 在 `record_submission_intent` **状态写入后**注入 audit 失败：状态/意图/事件必须同时回滚，已有预算 `held` 不得被释放；去掉故障后只能成功产生一个对应事件。
2. 在 `record_submission` **任务 ID 写入后**注入 audit 失败：已持久化的 `generation_intent_recorded=1` 不能消失，不自动产生第二个付费请求；之后只允许记录一个正确返回的 Task ID。
3. 在 `record_operator_verified_charge` 的两个状态更新完成后注入 audit 失败：预算行、任务行和事件必须一起回滚，不能出现「预算 reconciled、任务未记费用」。
4. 在临时 SQLite 测试库里加入专用故障触发器，拒绝**第二张表**（`shot_jobs.actual_vendor_charge_usd`）更新：第一张表已执行的预算核销也必须回滚；移除故障后重验合法核销。
5. 两个线程同时为同一条已持有预算的任务做不同金额的人工核销：只能一次成功、另一次拒绝，最终两张表金额一致，财务审计只能追加**一条** `operator_entered_vendor_charge`。
6. 没有 `generation_intent_recorded=1` 时，不能因为已有预算就伪造真实供应商发起与人工费用核销。

所有测试数据均为 CI 新建的原创虚构项目与临时 SQLite，零 Turso、Drive、付费模型 SDK 调用；不打印任何真实资料。

## 远端 libSQL 的真实待验收问题

**尚未实现真正 libSQL 后端，不声明远端兼容：**

- `BEGIN IMMEDIATE` 后的多表写入与审计需要在同一个**服务器可证实**的事务里提交或回滚，不允许客户端每条 SQL 单独 autocommit。
- 原生产 Schema 的外键、部分唯一索引、append-only 触发器、租约/费用不可变条件必须独立核实，不能用一个计数器的成功替代。
- `worker_read / busy` 不是明确拒绝 BEGIN；不能使用之前仅对前置写锁拒绝开放的一次安全重试规则。所有结果不明的 `commit`、超时/网络中断都必须进入核查，而非自动提交供应商第二次请求。
- 真正分布式持久停写、跨 Runner/跨地区一致性、供应商已计费但回执丢失、完整媒体回执恢复，需要单独的隔离云端实测和逐次授权。
- 不开启 `live_cutover_permitted`，不将生产 SQLite 数据迁往 Turso，不能触碰原有 `drama_drive_receipts_v1`。

下一阶段再考虑：针对已有四张业务表及其实际 Schema，设计**纯离线、可注入的远程连接语义候选**，但仍必须在隔离真实 Turso 通过多表测试后才能部署。
