# PR-31 并发原生 SDK 锁竞争回归稳定性修复（纯本地）

2026-10-14 的合并后主分支 [Actions #38538227606](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38538227606) 四个 Job 中，3/4 成功；`Real libSQL Python SDK — local-only contract` 的 `test_six_concurrent_native_claims_cannot_share_a_job_or_epoch` 曾在六个 Python 线程同时执行 `BEGIN IMMEDIATE` 时暴露真实 native SDK `ValueError: database is locked`，没有发生任何供应商 API 调用或远端 Turso 写入。

本修复严格在 `fenced_claim_local_job()` 的**第一条 BEGIN IMMEDIATE** 处捕获 native SDK 完全匹配的 `ValueError('database is locked')`，返回统一脱敏 `NativeFenceLabDenied('Offline pretransaction write lock unavailable')`，并**没有在函数内部自动重试**。其他 SQL/审计/COMMIT 阶段的错误仍原样抛出，尤其绝不将网络 ACK/未知 COMMIT 当作安全重试；仅限已经标记为 disposable fixture 的本地 native SDK 实验环境，不改变正式 Worker 或付费权限。

回归测试额外注入一次 BEGIN 之前的真实形状锁拒绝，要求零镜头领用、零 gate 审计、零自动重试，且两个原始 pending 任务完整保留。六线程极限竞争允许部分线程在 BEGIN 前被无害拒绝；**待该轮所有竞争线程结束后**，测试以新的 Worker 名称对**明确未提交且未付费**的本地 pending 任务执行独立安全领用，最终要求两条任务恰好各被领取一次、attempt=1、epoch=1、审计各 2 条。已有 paid-intent 和 COMMIT 回执丢失实验仍单独 fail closed。

此修改只修正本地 SDK 测试中对写锁竞争的分类，不是跨 Runner/Turso 真并发验收、不是无条件重试授权、不是生产部署。
