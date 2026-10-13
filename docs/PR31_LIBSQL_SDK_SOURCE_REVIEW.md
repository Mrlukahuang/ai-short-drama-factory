# PR-31b2l0 — 真实 libSQL Python SDK 的本地兼容性研究与验证

**状态：SDK 本地测试；不接入 Turso Cloud、不上传/写任何真实数据、不使用 GitHub Secrets。** 单次 TxLab v3 远端真实写入仍需要**全新明确授权**，本 PR 不增加写入 Workflow 或 SDK 远端连接代码。

## 一、证据来源（请区分源码分析与实测）

1. 我们当前包配置：[pyproject.toml](../pyproject.toml) 中 `turso-libsql = ["libsql>=0.1.11,<0.2"]`；前一次真实 TxLab v2 的 GitHub Actions [#38380555425](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38380555425) 使用 `libsql 0.1.11`。本次 CI 为可复现性**精确安装 `libsql==0.1.11`**，但只打开全新的本地 sqlite 文件。
2. 官方 Python [Quickstart](https://github.com/tursodatabase/turso-docs/blob/main/sdk/python/quickstart.mdx) 与 [Reference](https://github.com/tursodatabase/turso-docs/blob/main/sdk/python/reference.mdx)：`libsql` 用于原 libSQL 引擎（SQLite fork）、**不支持 MVCC 并发写入**；`turso_serverless` 是新版 Turso Database 的不同 SDK。不能混用引擎能力或把旧 libSQL 的 `SQLITE_BUSY` 当作实现 bug。
3. 实际 Rust Python 绑定 [libsql-python/src/lib.rs @ 4fee9cbd](https://github.com/tursodatabase/libsql-python/blob/4fee9cbd49db1a3a61dd1d3501fd681cbf9b1009/src/lib.rs)；截至审阅，其 `Connection.commit()` / `rollback()` **发送明确的 `COMMIT` / `ROLLBACK`**；`Connection.__exit__` 并不等于 `close`。`execute()` 对 DML 有隐式 BEGIN 行为，因此必须避免无意把建表/批量账单置于多个无法证明一致性的单独事务。
4. 特别注意该源码的 `Connection.executescript()` 路径：内部使用 `let _ = ...execute_batch(...).map_err(...)` 后返回 `Ok(())`，可能丢失原始批量执行错误。**不要使用 `executescript()` 作为安全 Schema 导入器，必须逐条 `execute()` 并在每一步校验错误，最后复查索引/触发器**。这是源码风险发现，而不是声称所有远端版本必现；未来若 SDK 升级必须重新对照源码/实测。
5. SQLite 和 Turso 的 `foreign_keys` 是**按连接启用的 PRAGMA**，不同 DB 连接不能继承。PR-31b2i 的全部外键/审计/费用语义只有在远端强制校验 `PRAGMA foreign_keys=ON`（且实际能生效）并测试失败回滚后才能视为成立。

## 二、加入一个第四项真实 SDK 的零云 CI

新增 [tests/test_libsql_sdk_local_only.py](../tests/test_libsql_sdk_local_only.py)，以及原 [ci.yml](../.github/workflows/ci.yml) 中 `libsql-sdk-local`：

- 在 GitHub 无 Secret 的环境安装准确版本 `libsql==0.1.11`，显式设置 `DRAMA_FACTORY_OFFLINE=1` 且 TxLab URL/Token 为空；**没有远端数据库连接、后台监控任务或手动 `workflow_dispatch`**。
- 用实际 Rust 编译的 `libsql` Python 扩展打开 `pytest.tmp_path` 下的**本地**数据库，以 v3 定义的 `pr31_v3_*` 五表、部分唯一索引、四个 append-only 触发器作为测试 DDL；逐条 `execute`，不调用 `executescript`。
- 验证 `PRAGMA foreign_keys=ON` 可回读为 1，外键破坏会报错；同 Provider 的重复非空 Task ID 拒绝；事件表 UPDATE/DELETE 被触发器拒绝。
- 对预算 → 任务费用 → 不可变财务事件跨表操作，在三处依次注入模拟失败，确认 `rollback()` 后**另一个 SDK 连接**看不到半笔账。
- 验证 `commit()` 后由独立新连接读回完整账单，另模拟**提交确认丢失**的调用方异常，禁止再进行第二次已计费操作。

此项是比 sqlite3 Fake 更接近线上 SDK 的**本地二进制运行证据**；但数据库文件不是远端 Turso Server，不代表 GitHub 云 Runner 横向并发、网络超时、跨表远端 COMMIT ACK、真实权限/Schema 均已验收。

**主线门禁**：Python 3.11、Python 3.13、FFmpeg 仍必须绿；增加第四个 `libsql-sdk-local` 任务，也必须真实绿，绝不能以 `skipped` 冒充 SDK 通过。

## 三、未来真实 TxLab v3 提前确认的失败条件

- 未独立授权：**不允许**用任何当前 Secrets 做远端 CREATE、INSERT、UPDATE、DDL 或新的测试 Workflow。
- 不能只看到 `executescript()` 正常返回就声称结构完整；所有 Schema DDL 应逐条执行、复查，并使用固定命名 `pr31_v3_*` 避免已有 v1/v2 结果。
- 每个连接、每个事务在写前必须明确 FK 设置及确认；反向失败测试（故意孤儿 FK、非法重复 Task ID、审计 UPDATE/DELETE）要证明远端确实拒绝。
- 先单连接远端多表原子性与回滚；跨 Runner 并发是**另外**一个验收任务，不要重演 v2 的不确定写锁竞争而把单次授权用完。
- 故障阶段和日志必须脱敏且**不自动重试**。如果 COMMIT 不确定，必须先只读核查，不可继续提交第二笔付费请求。
- 所有真实测试阶段都不修改主数据库 `ai-short-drama-factory`、原 v1/v2 探针或已成功的 `drama_drive_receipts_v1`。

## 四、当前结论

`libsql==0.1.11` 的**本地 SDK 合同通过**只能说明绑定与局部 SQLite 引擎行为符合可执行预期；无法推断远端 Server/协议完全兼容。未来真正切换主生产数据库，仍要经过现有 [业务原子性基线](PR31_LEDGER_MULTITABLE_CONTRACT.md)、[Schema 门禁](PR31_CRITICAL_SCHEMA_GUARD.md)、独立真实云端的多表/并发/断线验收以及明确生产迁移和回滚授权。
