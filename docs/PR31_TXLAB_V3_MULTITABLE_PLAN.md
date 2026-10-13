# PR-31b2k — libSQL 多表兼容性学习与隔离 v3 验收设计

> 状态：**仅离线 SQLite 测试包**；未创建新的真实 Turso 表、未使用 Secrets、未获得新的 TxLab 写入授权。无远端 v3 工作流/CLI，CI 不会与 Turso 连接。原业务 SQLite、Google Drive 和付费视频流水线均不改变。

## 一、已经读过的项目来源与事实

- [README](../README.md)、[AGENTS](../AGENTS.md)、[ADR](DECISIONS.md)、[ROADMAP](ROADMAP.md)：Python 是付费与审核的最终裁决方，不能跳过预算、版权和供应商重复计费保护。
- [PR31_LEDGER_MULTITABLE_CONTRACT](PR31_LEDGER_MULTITABLE_CONTRACT.md)：真正的事务边界是“任务状态 + 审计”“预算持有 + 审计”及“人工核销时预算行 + 镜头费用行 + 不可变事件”，**不是**一个计数器。
- [PR31_CRITICAL_SCHEMA_GUARD](PR31_CRITICAL_SCHEMA_GUARD.md)：迁移不能丢失 Task ID 非空部分唯一索引、预算/事件外键、不可 UPDATE/DELETE 审计触发器。
- 已真实运行 [TxLab v2 #38380555425](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38380555425)：`worker_read / busy`；后续只读 [#38383515455](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38383515455) 证实 v2 一条 counter=3，并非零提交，不能盲目重跑。
- 两份 2026-10-13 跨聊天交接是**历史快照/架构建议**，其中 PR #30 以前“尚未真实连接 Turso”的陈述不适用于当前 PR #53 之后的状态；以本仓库最新 CI 和真实 Actions 为准。架构建议只用于补接口，不让 ArtCraft/Godot/OpenMontage 取代生产调度。

## 二、外部源码与官方说明：仅作候选，不伪称已验证

参考：
- [Turso 官方 Python Quickstart](https://github.com/tursodatabase/turso-docs/blob/main/sdk/python/quickstart.mdx)：连接**远端 libSQL** 使用 `libsql`；新版 Turso Database 是另一引擎、适配器不能混用。
- [libsql-python 源仓库](https://github.com/tursodatabase/libsql-python) 的 `pyproject.toml` 和示例：本仓库使用 `libsql>=0.1.11,<0.2`，与之前真实 Actions 安装的 `libsql 0.1.11` 对应。
- [Turso/libSQL 引擎区别](https://github.com/tursodatabase/libsql) 与 [事务手册](https://github.com/tursodatabase/turso/blob/main/docs/manual.md)：旧 libSQL 仍可能受单写者锁影响；新版引擎的 MVCC/BEGIN CONCURRENT 特性**不能**直接套用于现有 TxLab libSQL。
- [Turso 关于批量与交互式事务的说明](https://turso.tech/blog/batches-in-sqlite-838e0961)：跨多个网络往返持有写事务可能增加 `SQLITE_BUSY`，考虑缩短事务窗口，但**不得**通过移除原子提交和审计约束来规避冲突。

本次没有远端访问，因此仍**未知**：该 TxLab 实例对全部 CHECK/FK/部分 UNIQUE/触发器 DDL 的真实支持，Python `libsql` 连接上的 `PRAGMA foreign_keys`/事务隔离行为、故障时 COMMIT 回执语义、不同 GitHub Runner 的竞争语义。须用实际隔离库在另外一次**新授权**下证明，不能靠本地相似 SQL 推断。

## 三、本轮新增的、不可操作真实业务数据库的 v3 包

`src/drama_factory/storage/txlab_multitable_v3.py` 定义一组**独立前缀** `pr31_v3_*` 的模拟表、唯一索引、外键及审计触发器，当前运行入口只能新建 **O_EXCL、0600、未存在的本地 SQLite 文件**，拒绝远端 URL、旧文件、symlink 或没提供 `isolated_test_only=True`。

涉及五张纯虚构表（非生产 schema）：`pr31_v3_policy`、`pr31_v3_job`、`pr31_v3_job_event`、`pr31_v3_reservation`、`pr31_v3_budget_event`。仅使用虚构 `synthetic_*` 标记、40/45/60 分的固定测试金额；不复制业务 row ID、剧本文本、Drive ID、实际账单、供应商 Task ID、用户资源或 Secrets。

独立 `BEGIN IMMEDIATE` 事务以**先改预算预留 → 再改任务实际费用 → 再追加财务事件 → 单次 COMMIT** 的顺序验证三个原子写入。故障注入发生在第一表后、第二表后、审计写入后，各场景均须全部回滚；两名审核员并发只能产生一次核销。**COMMIT 已成功但回执丢失**时应保留已提交记录、抛出不确定结果并**拒绝再次核销/重发**。

另外实际测试：
- 已存在本地文件/假冒生产 SQLite/symlink/远端 URL 拒绝；
- `provider_task_id IS NOT NULL` 条件唯一索引，同一 Provider 重复非空 Task ID 拒绝，NULL 可并存；
- 外键与 CHECK 拒绝孤儿记录、假造未发生的生成意图；
- 四个 append-only 触发器分别拒绝事件 UPDATE/DELETE；
- 报告不暴露具体 row ID、路径和模拟凭据；输出 `remote_schema_verified=false`、`remote_multitable_transaction_verified=false`、`production_backend_switched=false` 等明确边界。

它不替代真实 `shot_jobs` / `job_budget_reservations`，更不认为已完成 Turso 的生产 Schema 迁移；PR #52/#53 继续作为实际业务和结构的基线。

## 四、将来真正 TxLab v3 单次测试的明确入口条件（**本 PR 不执行**）

**必须先满足：**

1. 用户对**一次新 TxLab 多表真实写入**明确授权；旧 v1/v2 授权已用尽，旧真实写入工作流不能重跑。
2. 另一个小 PR 增加新的 `manual-isolated-libsql-txlab-v3.yml` 工作流和远端桥接实现，默认锁止；单独审查后才允许第一次手动调度。继续只注入 `DRAMA_TXLAB_DATABASE_URL` / `DRAMA_TXLAB_AUTH_TOKEN`，严禁主库的四项原有 Secrets。
3. 新工作流在任何 DDL/DML 之前严格校验 URL 只能命中 `ai-short-drama-factory-txlab-<org>...`；检查 v3 目标对象**不存在**（禁止在已有 v3 半成品上静默重跑）；限定一次运行、绑定本次 run ID，失败不得自动重试。
4. 用明确阶段输出安全枚举，核实远端 FK/部分唯一索引、append-only 触发器、回滚、跨表 COMMIT；**避免 v2 那种不确定并发**——先做单连接的多表事务语义验收，第二轮再独立安排真实并发和断线故障。
5. 操作中途失败不执行 DROP/DELETE，不把 SDK 异常或 Token 打印到 Actions；应先另起**只读** v3 状态核查，才能决定后续修复和新授权。

**不能通过简单“本地成功”就给远端开生产开关**：跨 Runner 序列化、付费供应商请求前持久化意图、多租约/版本 fencing、恢复快照和完整 Schema 的兼容性仍是不同的验收任务。旧 v1/v2 结果保留不清理，原短剧 `drama_drive_receipts_v1` 不动。

## 五、后续推荐顺序

`PR-31b2k` 离线 CI 全绿 → 将这个 v3 包作为明确的**实验规范** → 若用户希望尽快推进真实远端，另询一次性 v3 写入许可 → 先远端功能/原子性再跨 Runner/故障恢复 → 再考虑全生产快照/回滚。任何一步未验证都不跳过，不能推迟制作 UI/QA 的独立规划，但不在同一个 PR 混改。
