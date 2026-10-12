# PR-30 — 一次性 Turso 专用数据库只读连通性验收

本功能**不会创建/修改任何 Turso 表**，也不访问 Google Drive。为了保护已经用于其他产品的 Turso 数据库，只接受主机名 `ai-short-drama-factory-<org>.turso.io` 或 Turso 控制台返回的区域化主机名 `ai-short-drama-factory-<org>.<region>.turso.io` 的专用数据库。

## 为什么需要新建独立数据库

你的其他项目已经使用 Turso，但短剧工厂的审核、预算、镜头与资产结构独立，而且本仓库的自动化还未配置正式身份认证。**不要复用其他项目的 TURSO_DATABASE_URL / Token。** 应在 Turso 控制台新建单独数据库，建议名字 `ai-short-drama-factory`，并生成只给此库的令牌。

Turso Python 远程连接有两种引擎，GitHub 手动工作流需要选择实际类型：

- **libSQL**（旧 Turso Cloud）：`libsql://ai-short-drama-factory-<org>.turso.io` 或区域化 URL `libsql://ai-short-drama-factory-<org>.<region>.turso.io`，Python SDK `libsql`，工作流 Engine 选择 `libsql`。保留控制台显示的完整区域域名，不可自行去掉 `<region>`。
- **Turso Database**（新引擎）：`https://ai-short-drama-factory-<org>.turso.io`（若控制台返回带区域段的主机名，也必须保留），Python SDK `turso_serverless`，工作流 Engine 选择 `turso`。

官方 Python quickstart: https://github.com/tursodatabase/turso-docs/blob/main/sdk/python/quickstart.mdx

如果控制台实际的 URL、引擎或 hostname 不符合这一格式，先停下让开发者核实，不要为了通过验收修改成其他项目 URL 或关闭安全校验。

## 单次只读检查的两个 GitHub Secrets

在本私有仓库 GitHub Settings → Secrets and variables → Actions → New repository secret 中**手动**添加：

1. `DRAMA_TURSO_DATABASE_URL`：刚刚创建的**专用短剧库**地址，不能是其他项目的地址。
2. `DRAMA_TURSO_AUTH_TOKEN`：只授权这个数据库的 Turso token，不要给 ChatGPT 发送、截图或提交到代码仓库。

请**不要**把这两个值放进同一个仓库其他项目现有 Secret 名称里覆盖。前面 Google Drive 的两个 Secrets 可以原封不动保留。

## 真实只读验收

仓库 Actions → **Manual Turso read-only database check (no writes)** → Run workflow，分支选 `main`，Engine 选实际引擎，再在 Confirmation 输入：

```
CHECK_DEDICATED_DRAMA_DB
```

本工作流通过 `workflow_dispatch` **仅手动触发**；权限 `contents: read`。它会选择该引擎对应 Python SDK，对专用 Turso 数据库执行：

```sql
SELECT 1;
SELECT 1 FROM sqlite_master WHERE type='table' AND name='drama_drive_receipts_v1';
```

返回 `reachable`、`engine`、`metadata_table_exists`、`read_only=true`。不会打印 Token 或 URL、不会向 Turso 创建表、不会修改旧库，也不会上传视频或调用 Gemini。GitHub 的 `short-drama-turso-readonly-verification` 只包含脱敏回执。第三方 Turso SDK 连接失败时，CLI 不打印原始异常或堆栈，以免报错消息意外包含 Secret；工作流仍返回非零退出码并标记失败。需要排错时先核对引擎、专用数据库 URL、Token 作用域及权限，不应临时把 Secret 打印到 Actions 日志。

第一次连接新库时 `metadata_table_exists=false` 是**正确结果**。先确认 SDK、网络、Token 和独立数据库权限，再后续单独授权实际 metadata insert。

## 最小依赖验收（2026-10-13）

首次手动运行 [Actions #38276881688](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38276881688) 安装 libSQL SDK 成功，两个专用 Secrets 也已注入，但 Python 导入 `turso_receipts` 时提前导入了媒体资产验证模块，导致缺少可选 Pillow 包的 `ModuleNotFoundError: No module named 'PIL'`，还未执行任何真实 Turso SQL。修复把媒体校验导入延迟到**已授权单条镜像写入**时，保持只读预检仅需 libSQL SDK 和核心依赖，不扩大线上工作流依赖。新增独立 Python 子进程测试，故意阻止导入 `PIL` 和视频资产模块，仍须通过只读预检。此项属于离线兼容修复，不代表已成功连接 Turso；修复合并后需要再次手动启动真实工作流。

## 本 PR 的验证范围

`pytest -q tests/test_turso_preflight.py` 在 Fake DBAPI SQLite 模拟器上测试必须人工确认、没有 Token 的拒绝、只执行 SELECT、引擎校验、是否存在专用表、静态审计 GitHub Workflow 必须是手动触发且不包含 Drive/Gemini 凭证。

上述 Fake/离线测试本身**不能证明真实 Turso 连接**；真实连接已由下列独立 GitHub Actions 记录证实。后续仍需重新设计 Turso 作为 Worker/预算事务权威数据库；这不属于本阶段。

## PR-30b 真正的 Turso 只读连接验收（2026-10-13）

- **真实运行**：[GitHub Actions #38277564945](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38277564945)，`workflow_dispatch`，`main` commit `8c893ae8efffc43a392b43c8b0583be49d2cc7e0`，`success`。
- **连接目标**：用户刚创建的独立 `ai-short-drama-factory`，Turso Sydney 区域，`libsql` 引擎。专用 URL 通过严格项目名前缀、区域子域验证；两项 Secret 只注入工作流，不打印凭据。
- **实际 Job Logs 脱敏回执**：`{"database_modified": false, "dedicated_name_validated": true, "engine": "libsql", "google_drive_operations": 0, "metadata_table_exists": false, "new_ai_model_generation_calls": 0, "reachable": true, "read_only": true}`。
- **Artifact**：`short-drama-turso-readonly-verification`（仅脱敏结果，GitHub 保留 3 天）。
- **范围**：真正跑通 SDK 网络连接和两条指定 SELECT；新库没有 `drama_drive_receipts_v1` 表符合预期；没有 DDL/DML、没有视频上传或付费 AI 调用。`read_only=true` 描述**本次只读代码路径**，不是数据库级 Token 权限认证。用户选择了只对本短剧库使用的 Full Access Token，因此不要将其误称为只读 Token。
- **尚未证明**：远端 INSERT/DDL、写后查询、SQLite 生产事务迁移、跨 Worker 并发、恢复、数据备份或 PR-30c 的真实 Drive 回执写入。此阶段不得因连接成功而自动启用写入。PR-30c 如需重新上传任何素材、写入真实数据库或调整权限，必须另获用户明确授权。

