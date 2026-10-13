# PR-31b2m — 生产账本与已通过 TxLab v3 的差距门禁

## 真实证据与不应扩大的结论

真实单次独立 TxLab v3 [Actions #38417337745](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38417337745) **已成功**：`schema_object_count=10`（五张虚构表、一张唯一索引、四个触发器）、`rollback_multitable_verified=true`、`committed_multitable_readback_verified=true`、`foreign_key_constraints_verified=true`、`partial_unique_provider_task_verified=true`、`append_only_triggers_verified=true`。

这说明**那一次实验、那些虚构表、串行多表事务**的实际远端 libSQL 行为符合测试预期。它不是完整生产 Schema 的迁移结果：实验程序输出仍明确 `remote_multiworker_concurrency_verified=false`、`full_production_schema_verified=false`、`live_cutover_permitted=false`。PR #59 已把唯一真实 v3 写入 Workflow 重新硬锁止。

本阶段不再用一个玩具计数器代表生产能力。来源是仓库自身当前 `db.py` Schema、`jobs/shots.py` 和 `jobs/budgets.py` 的真实业务函数，以及既有 [PR-31a 迁移源库只读体检](PR31_MIGRATION_READINESS.md)、[PR-31b2i 多表原子性业务合同](PR31_LEDGER_MULTITABLE_CONTRACT.md)、[PR-31b2j 关键账本约束](PR31_CRITICAL_SCHEMA_GUARD.md)。

## 对照矩阵

| 必备生产能力 | TxLab v3 真实已经验证 | 与现行生产的差距和下一个关口 |
| --- | --- | --- |
| 串行多表提交、回滚 | **已验证**，但仅虚构 `pr31_v3_*` 五表 | 现有 `shot_jobs`、`job_budget_reservations`、财务/任务事件仍未部署或以完整 DDL 在 Turso 验证 |
| 外键、部分唯一 Task ID 索引 | **已验证**，只针对虚构任务 | 生产栏目→剧集→分集→镜头任务、预算保留、Provider Task ID 的完整实际外键和唯一约束、CHECK、租约字段仍未远程复现 |
| append-only 审计事件 | **已验证**，但仅 v3 两张事件表 | 生产镜头/预算事件以及 cloud/Drive 复制凭据的 UPDATE/DELETE 阻断必须全部保留 |
| 三级预算上限 | **未验证** | 同时覆盖栏目、剧集、Provider 费额/并发数量、政策版本、已持有及已核实金额，多个 Worker 争抢不得超支 |
| 镜头 Worker 租约和幂等 | **未验证** | 同镜头仅一 Worker 领取，生成意图入库在付费请求之前；未知供应商回执不能清除该保护以便重复付费 |
| Google Drive / S3/R2 视频回执 | **未验证** | 资产哈希/大小、已验收存储副本、append-only 云资产/Drive 事件、断线恢复和原始文件归属 |
| 网络断线/COMMIT ACK 丢失 | **未验证** | 不得假设错误意味着未提交；必须有只读对账、不会自动重发的幂等和人工恢复 |
| 跨 Runner/生产迁移回滚 | **未验证** | 完整一致性快照、源库停写、验证新库并决定原库回退窗口、灰度与费用保护 |

**特别注意**：本地预算预留与提交付费意图是现有两个分离的事务；不能为了缩短远程锁时间，把外部付费模型请求放在持有写锁的事务里。此原则见 [PR-31b2i](PR31_LEDGER_MULTITABLE_CONTRACT.md)。

## PR 本身实现了什么

新增 `src/drama_factory/storage/pr31_remote_gap_assessment.py`，调用此前两个本地**只读**检查器，再对 `db.py` 中额外的素材/镜头保护做第三次本地 Schema 元数据核查：

- 六张额外表：`stored_artifacts`、`cloud_artifacts`、`cloud_artifact_events`、`drive_artifacts`、`drive_artifact_events`、`google_existing_files`。
- 三个媒体/存储索引：`idx_stored_artifacts_production`、`idx_cloud_artifacts_local`、`idx_drive_artifacts_source`。
- 四个不可变媒体审计触发器：cloud/Drive 事件各自的 UPDATE/DELETE；同名无效触发器不得蒙混过关。
- 九条关键额外外键，及六条唯一性语义（包括预算策略修订、独立云资产、Drive 同目录副本、Google 文件 ID）。
- 七组真实生产业务必需字段，包括 Worker 租约、生成意图、预算政策版本与 snapshot、财务核销证据、资产 SHA256/大小和云对象键。
- 同时保留既有迁移体检的未结租约、未确认供应商计费、预算 hold 与 Drive 恢复锁等运行时风险。**结构看上去完整也不等于可停写迁移**。

读端依然只使用**已有本地文件**的 `file:?mode=ro`、`PRAGMA query_only=ON`、`BEGIN` 一致性元数据快照，不执行 `Database()`、Schema 初始化、真实内容读取、云端连接、拷贝、付费请求或 DDL/DML。三个只读扫描彼此不是同一个跨进程全局快照，因此明确返回 `source_global_cross_scan_snapshot_verified=false`；未来真正迁移前**必须另外停写和取得可靠的快照/增量尾点**。

报告只输出当前本地结构的数量、脱敏问题代码、业务风险**汇总计数**、Schema 哈希及固定的远程未验收项；不会输出剧本、项目/镜头 ID、文件路径、SDK 报错或 Token。

## 如何在有明确本地操作需要时运行

仅提供**可选的本地 CLI**（本轮 GitHub CI 不读取你的实际数据库）：

```bash
python -m drama_factory.storage.pr31_remote_gap_assessment \
  --source /path/to/existing/local.sqlite3 \
  --confirmation PR31_LOCAL_GAP_REVIEW_ONLY
```

它拒绝 `libsql://`、不存在的源文件、`:memory:`、符号链接和没有明确只读确认词的调用。输出中的 `local_schema_safety_checks_passed=true` 和 `local_quiescence_checks_passed=true` **仅代表相应本地观测**，`full_production_schema_import_verified`、`remote_multiworker_concurrency_verified`、`remote_network_commit_recovery_verified`、`production_backend_switched`、`live_cutover_permitted` 仍永远为 `false`。

## 后续分阶段验收，不一次性大规模真实迁移

1. **PR-31b2n（下一小步，先离线）**：将真实业务表的 Schema/索引/触发器组成受控、可对账、可失败停机的**隔离测试子集**；优先涵盖 `shot_jobs`、预算政策/预留与两类事件表。只用虚构数据，先在真实 libSQL SDK 本地 CI 完整验证，再另请新的**单次 TxLab 写入授权**。
2. **PR-31b2o（需独立批准）**：跨 Runner 的同一镜头 lease 与预算抢占测试；必须有明确锁失败分类、上界及不重复提交付费意图，不能盲重试不可确认的 COMMIT。
3. **PR-31b2p（需独立批准）**：模拟 COMMIT 回执丢失、供应商生成状态不确定及断线重连**只读对账**；生产 Worker 仍禁止自动付费重试。
4. **PR-31d（更后面，需要另外的生产授权）**：真实源库停写/一致性备份、分段迁移、数据 SHA/计数对账、灰度与原库回退；未验收之前不能开放 `live_cutover_permitted`。

本轮 PR 不创建任何真实云端手动写入工作流，也不复用已用尽的 v1/v2/v3 授权。
