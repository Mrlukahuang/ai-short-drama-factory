# PR-31b2o2 — 离线恢复对账与跨 Runner fencing 预检查（未上线）

本 PR 只增加 **被 native-SDK 适配器批准的临时标记 SQLite 测试库**的只读检查器，以及 **纯函数** claim fencing 判定合同。不会接入生产 Worker、不会变更数据库 Schema / Actions / Secrets / Drive、不会初始化生产数据库或访问 Turso，也不会调用付费 Provider。真实远端 TxLab v3 单次写入授权已消耗，v1/v2/v3 写入不可重跑。

## 恢复检查器

`inspect_offline_job_recovery(backend, job_id, now=...)` 的入口必须是精确类型 `LocalNativeLibsqlLedger`（该类型只能由标记的隔离测试文件构造）。检查器再次在 **SQLite mode=ro + PRAGMA query_only=ON + BEGIN** 的一致读快照内验 marker，以固定 SQL 检查：

- 镜头状态、generation intent、非空 Provider Task ID、attempt/租约
- 预算预留 `held / released / reconciled`、实际费用与任务实际费用是否一致
- 必需的 `generation_intent_recorded` 和 `operator_entered_vendor_charge` 事件次数
- 过期租约、缺失任务、状态或审计自相矛盾

返回**仅枚举或布尔**：`safe_to_inspect_only`、`needs_operator_review`、`held_budget`、`intent_uncertain`、`existing_provider_task`、`charge_reconciled`、`lease_expired`、`inconsistent_ledger`、`missing_job`、`failed_job`。不输出 Job ID、Provider Task ID、Worker、预算金额、用户名、凭据、剧本、文件路径、错误信息或审计明文。

`charge_reconciled` **只代表离线数据库内部的字段+单条审计相互一致**，**不是**供应商已实际出账的独立证明；COMMIT ACK 丢失后依旧要求人工核对。任何返回都恒定 `may_resubmit_paid_provider=false`、`may_release_held_budget=false` 和 `needs_operator_review=true`。对账报告永不能单独启动收费或迁移。

## 已有 Worker 的重要缺口

当前 `claim_next_job` 会在事务中增加 `attempts` 并登记 `lease_owner`、`lease_expires_at`。但某些现有写回函数（例如 `record_submission`、`record_failure`、`complete_fake_clip_job`）只核对 Worker 名称与状态，**并未在每个写回处核对 attempts、租约是否过期及全局 writer epoch**。本 PR 不静默改变它们、不能把本地锁当成跨 Runner 的正确性证明。现有 `offline_fencing.py` / PR-31c2 已提供独立的本地 epoch 持久化模拟，不在此重复造一个生产 gate。

`assess_claim_fence(...)` 是纯函数：要求同一 Worker **加上**相同领取 attempt、同一全局 writer epoch、gate 为 running、租约未过期、且任务仍为 leased / 尚未记录付费意图。不满足时只返回脱敏拒绝原因；满足时只返回 `candidate_requires_atomic_cas`，**不是放行**。

未来若要正式跨 Runner 启用，必须先单独审查并实现这些原子协议：

1. 每次写账本时在**共享持久的交易事务**中核验 `gate_state=running AND global_epoch=acquired_epoch`；迁移暂停/恢复必须递增 epoch，原 Worker 令牌不可复用。
2. 对单镜头写回要求 `job_id + lease_owner + attempts + lease_expires_at > database_now + expected_status` 的条件更新，更新数必须精确为 1；审计写入与状态在同一交易里提交，失败都回滚。不能用本地 runner 时钟替代跨机器的数据库时钟。
3. 新领取必须产生更高的单调代数；**即使 Worker 名称复用**，旧 attempt 也绝不能写回。
4. Provider 请求尤其危险：不能仅靠先前读取结果或 `CAS` 保证外部幂等。持久化 Intent 提交成功后再发外部请求；若请求/网络回执/COMMIT 不明，只读查供应商 Task ID 和账单，人工解除隔离，不自动重发。
5. 依次验收真实生产子集 Schema 的隔离 TxLab DDL/跨表、跨 Runner contention、网络 ACK loss、恢复/回滚，**每一轮真实远端写入需重新单次明确授权**；生产切换仍禁止。

## 离线验收和证据限制

- `tests/test_pr31_offline_recovery_native_sdk.py`：真实 `libsql==0.1.11` 本地 SDK 创建的原业务账本、held 预留、可能已计费但缺 Task ID、实际 COMMIT 后模拟 ACK 丢失、失败审计回滚、过期租约、敏感字段不在回执、无写入。
- `tests/test_pr31_claim_fencing_contract.py`：相同 Worker 名旧 attempt、不同 Worker、过期租约、旧 epoch、暂停 gate、无时区或无效 token 一律拒绝；合法形态也不授权写入或付费。
- 四项既有 CI 必须全部绿：3.11、3.13、FFmpeg、native SDK 本地。没有远程/生产测试；保留 `cross_runner_fencing_verified=false`、`remote_network_recovery_verified=false`、`live_cutover_permitted=false`。

**无 Schema 修改；无数据迁移；无远端费用；无 Secret 读取或更新；不触发任何手动 Workflow。**
