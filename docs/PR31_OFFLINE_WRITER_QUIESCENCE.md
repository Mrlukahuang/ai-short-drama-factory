# PR-31c3b — 本地暂停/恢复前的**纯只读** Quiescence 安全体检

PR-31c3a 在不同 Python OS 进程验证了本地 `epoch`、租约和日志在强制崩溃下的基本安全性。但在真实切换中，**pause 成功不等于可以恢复/切换**：旧任务可能依旧持有 lease，已经提交付费意图却尚未确认 Task ID/账单，或者预算仍被冻结；仅靠一个 epoch 值就打开 Writer 会产生新请求和双重计费风险。

本轮新增 `inspect_offline_writer_quiescence`，**只读预检，不执行 resume、更不授予 resume 权限**。仅接受 `LocalNativeLibsqlLedger` 已标记过的临时 SQLite 本地实验文件，使用一个独立 SQLite `mode=ro`、`PRAGMA query_only=ON`、`BEGIN` 快照，进入快照后再次确认 marker。不存在连接远端 Turso、读取任何云端账户 Secrets、写入库、修改门禁、释放预算、调用供应商的路径。输出只有预定义标志，不能含 Job/Worker/Task ID、金额、文件路径和底层错误。

阻断条件包括：

- Writer gate **没有 paused**，或者 durable epoch 和 append-only pause/resume 审计序列不一致。
- `leased`、`submission_intent`、`submitted` 的未结镜头/未结束 lease。
- 任一镜头曾记录生成意图（含即使人工录入核销金额但没有外部供应商幂等证据）、存在 Provider Task ID 需要独立复核。
- 任意 held 预算预留未核对或关键镜头/预算状态不一致。

只有以上危险因素全部不存在且 gate 为 paused，`offline_quiescence_candidate_for_review=true` 才成立。这**仍然不是恢复许可**：`safe_to_authorize_resume=false`、`may_resume_remote_writers=false`、`may_resume_production_writers=false`、`may_retry_paid_provider=false`、`may_release_held_budget=false`、`live_cutover_permitted=false` 永久返回 false。本实验不替代真正生产权限审核、备份一致性审查或 Vendor 账单校对。

测试使用真实 `libsql==0.1.11` 本地标记实验账本构造任务和成本状态，然后检查纯只读结果、状态和磁盘字节未变化、异常和篡改拒绝。不覆盖真正的远端 pause/resume；TxLab v1/v2/v3/v4 已消耗授权继续硬锁止，下一次跨 Runner 的远端写入和生产切换仍须另行明确批准。
