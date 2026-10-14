# PR-31b2o3 — Native libSQL 本地真实镜头事务与 epoch fencing 实验

**性质：仅本地隔离测试，不是远端 TxLab/跨 Runner 验收，也不接入现有生产 Worker。**

在 PR-31b2o2 的纯 claim 判定合同之后，本轮把持久 writer gate 与真实 `shot_jobs`、`shot_job_events` 放到**同一个由真实 `libsql==0.1.11` SDK 打开的临时 SQLite 文件事务**中。仅允许现有 `LocalNativeLibsqlLedger`（创建时通过独立测试 marker 校验）和再次在事务中校验 marker；没有任何 libsql:// 连接或真实账户写入。禁止使用 native SDK `executescript()` 批量 DDL；建表、不可变审计触发器全部逐条 `execute()`。

## 已实现的候选原子合同

`init_local_native_fence_lab(..., isolated_test_only=True)` 为**已标记的临时本地数据库**新增独立的 `pr31_native_job_fence_gate`（单例 running/paused + 单调 epoch）及只增不改的 `pr31_native_job_fence_events`。这些对象**绝不进入生产 Schema**，不变更 `src/drama_factory/db.py` 或云端 Schema。

`fenced_claim_local_job(...)`：一次 `BEGIN IMMEDIATE` 完成 gate running 校验、原始 `shot_jobs` 的 pending→leased+attempts 递增、`shot_job_events` 的 claimed 事件、独立 gate 审计。领取令牌含 job、owner、attempt、epoch 和租约过期时间，只用于本地测试，不对外发放。

`fenced_fail_unsubmitted_local_job(...)`：只允许**未有任何付费意图**的 leased 镜头转入 failed。一次事务校验 durable epoch、gate 状态、owner、attempt、过期时间、原始领取期限、状态和零付费意图，条件 UPDATE 必须恰好更新一条，后随真实镜头审计和 gate 审计。任何条件失败或审计写入异常整个事务回滚；旧 attempt 即使 Worker 名称相同也无法更新；过期 token 禁止写回。

`set_local_writer_gate(...)`：模拟暂停/恢复须同事务更新 epoch 并追加审计，resume 需要明确本地 operator_reviewed。暂停后、以及重新恢复后，旧 token 都失效。此实现**只控制这些新增的离线实验函数**，不会拦截正式 `claim_next_job` 或其他现有 Worker 写入。

## 实际离线测试

- 六线程并发领取两个真正 `shot_jobs`，不可重复 job；每次成功都有同一事务中的 shot 和 gate 审计。
- 人工恢复后同名 Worker 第 2 次领取，旧 attempt 在原子 CAS 处拒绝。
- Epoch 暂停/恢复使先前 Worker 的旧 token 永远失效，过期租约拒绝。
- 存在已持久化付费提交意图时，不允许“安全失败”通路做擅自恢复。
- 第二项 gate 审计写入失败时，前面的镜头状态和审计一起回滚。
- **真实 SDK COMMIT 先落磁盘，再模拟 ACK 丢失**，原任务和双审计各保持一次，调用端收到异常且不自动重复写入。
- 写入与 pause 并发，执行顺序由本地同一数据库事务决定；暂停提交后无合法旧 token 可以再成功写回。

四项免费 CI（Python 3.11/3.13、FFmpeg、固定版本真实 native SDK 本地合同）通过才合并。已在 CI 的固定 SDK 测试清单中显式加入本测试文件。

## 明确未验证、后续必须单次授权

这**不是**多台 GitHub Runner 的共同持久锁，不验证 Turso 远端事务一致性、数据库端时钟、供应商外部计费、任一真正故障恢复入口，也不能据此批准 SQLite→Turso 迁移。真实跨 Runner `gate/epoch`、租约生效与 Provider side effect 必须在用户重新授予新一次 TxLab 远端写入权限后单独审核。当前：

- `remote_multiworker_concurrency_verified=false`
- `durable_fleet_writer_gate_verified=false`
- `network_commit_recovery_verified=false`
- `production_backend_switched=false`
- `live_cutover_permitted=false`
- 本轮远端数据库读写、Drive 访问、收费模型调用 = **0**。
