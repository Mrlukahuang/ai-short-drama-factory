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

## 本 PR 的验证范围

`pytest -q tests/test_turso_preflight.py` 在 Fake DBAPI SQLite 模拟器上测试必须人工确认、没有 Token 的拒绝、只执行 SELECT、引擎校验、是否存在专用表、静态审计 GitHub Workflow 必须是手动触发且不包含 Drive/Gemini 凭证。

**不代表真实 Turso 已经连接。** 真实连通性需要用户创建专用库、私下配置 Secret、明确手动执行后才会确认。后续需要重新设计 Turso 作为所有 Worker/预算事务的权威数据库；这不是本 PR。
