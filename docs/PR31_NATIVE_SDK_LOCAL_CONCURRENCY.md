# PR-31b2o1 — 真实 libSQL SDK 本地并发与模糊 COMMIT 回执合同

本轮只在 **CI 临时 SQLite 文件**里运行现有业务函数，通过 `LocalNativeLibsqlLedger` 和真实 `libsql==0.1.11` SDK。数据库文件必须有测试专用 Marker；不接受 `libsql://`、生产 SQLite、Turso Secrets、Drive 资源或任何付费 Provider API。本阶段绝非远端并发验收。

## 可执行验收

- **镜头领取竞争**：8 个真正线程同时争抢 2 个准备好的真实 `shot_jobs`，允许已分类的数据库 busy/业务拒绝，但所有成功领取必须对应唯一 job、一次 attempt 和**同一次事务提交的 claimed 审计**；未知错误直接使 CI 失败。
- **预算竞争**：两个独立 Worker 已各领一个镜头，两线程同时要求预留 0.40 美元，Provider 当日限额为 0.60 美元。只能有至多一笔 held 预留，所有已确认成功的 held 都必须有对应 held 审计，合计不得超过 0.60 美元。busy 不自动重试。
- **COMMIT 回执丢失**：在 `_NativeConnection.commit` 内先调用真实 SDK 提交（实际已落本地磁盘），随后模拟网络回执丢失。业务层必须收到异常、不做第二次提交；独立连接只读回查预算、镜头实际费用和一条审计；再次人工同任务核销被现有业务规则拒绝。
- 全部测试使用真实业务 `prepare_shot_jobs` / `claim_next_job` / `configure_policy` / `reserve_job_budget` / `record_submission_intent` / `record_operator_verified_charge`，未修改这些函数和生产 Worker。

## 证据界限

本地 SDK 测试只能证明本地驱动并发行为与所测业务不变量，**远程不确定结果可能还需要额外的只读对账/持久 fencing**。报告中 `remote_concurrency_verified=false`、`network_commit_recovery_verified=false`、`live_cutover_permitted=false` 持续关闭。真实 TxLab v3 已经一次授权成功，写入工作流已经硬锁止；后续跨 Runner/网络 DDL/DML 需要新的明确授权。

首次本地测试如遇真实 SQLITE_BUSY，应分类记录并拒绝自动重试，不能为了 CI 全绿而隐藏未知异常或强迫失败事务被判作成功。
