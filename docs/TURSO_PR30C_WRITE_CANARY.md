# PR-30c — 一次性真实 Drive MP4 → 专用 Turso 回执写入验收

> **状态：代码准备/离线 CI；不是实测完成记录。** 只有下述独立手动 GitHub Actions 成功、日志和脱敏 Artifact 经过检查后，才能将 PR-30c 标为真实写入成功。

## 授权与严格边界

2026-10-13 操作者明确授权**一次**私有原创技术 MP4 上传、独立短剧 Turso 库的元数据表创建、**单条** INSERT 和写后 SELECT 校验。本阶段仅是元数据回执镜像验证，不将生产 SQLite 中的预算、审批、租约或镜头任务迁到 Turso，也不触发付费 AI。

专用目标：Turso **libSQL**，数据库 `ai-short-drama-factory`（Sydney）。**禁止复用或写入 `nz-social-trend-radar` 的 Turso 库。** Token 是授予短剧数据库的 Full Access 凭据，当前写入 Workflow 限定了允许执行的应用操作；请勿将 Full Access 称为只读凭据。

需要仓库已有四个 GitHub Actions Secrets，全部只注入手动 Workflow 的单个步骤，绝不在聊天/日志/仓库源码输出凭据：

- `DRAMA_DRIVE_USER_OAUTH_JSON`、`DRAMA_DRIVE_PARENT_FOLDER_ID`（已有并通过 Drive 真机测试）
- `DRAMA_TURSO_DATABASE_URL`、`DRAMA_TURSO_AUTH_TOKEN`（已通过 PR-30b 真机 SELECT-only 检查）

**不需要**新建 Secret，不需要重新做 Google OAuth。若 OAuth External Testing 模式刷新令牌失效，应先独立修复认证，不能暴露 token 到日志。

## 新的手动 Workflow

`.github/workflows/manual-drive-turso-receipt-canary.yml`

1. 仓库 Actions → **Manual one verified Drive MP4 to Turso receipt (PR-30c)** → **Run workflow**。
2. Branch 选已通过全部 CI 的 `main`；确认词精确输入 `UPLOAD_AND_MIRROR_ONE_VERIFIED_MP4`。
3. Workflow 安装固定 SHA256 的 FFmpeg/FFprobe + `[test,drive-storage,turso-libsql]`。内部再次检查四个 Secrets 都已配置、所有 Drive/Turso 双重许可门禁与专用 libSQL URL。
4. **先向 Turso 做 SELECT 1** 验证 URL/Token/网络，再从零生成 2 秒原创技术 MP4（非付费 AI，非真人素材），经本地审核状态机输出独立缓存和 SQLite 账本。
5. 仅向用户私有 Drive 应用文件夹处理该**一个** MP4：上传到 Series/Production 分离目录；从 Drive 下载、媒体流与 SHA256 验证；恢复到独立本地目录再次校验；必须生成 `uploaded_verified_by_download` 与 `downloaded_verified_local_copy` 两条本地审计事件。
6. 同一个 Runner SQLite 上下文、同一条已验证 Drive copy ID，调用 `mirror_verified_drive_receipt(... operator_approved=True)`：仅新建 `drama_drive_receipts_v1` 表（`CREATE TABLE IF NOT EXISTS`）、INSERT **一条**元数据、commit、SELECT 全字段逐项比对。不得将 MP4 二进制、Token、OAuth JSON、小说原文或个人信息写入 Turso。
7. 只上传脱敏 `pr30c-private-drive-turso-receipt-verification` Artifact（保留 3 天）。结果必须 `drive_round_trip_verified=true`、`uploaded_mp4_count=1`、`turso_metadata_inserted=true`、`turso_full_row_readback_verified=true`、`sha256_match=true`、`database_modified=true`、`new_ai_model_generation_calls=0`、`production_sqlite_migrated=false`。

`drive_copy_id`、`drive_file_id`、`series_id`、`production_id`、OAuth Token、Turso Token、数据库 URL 都不能出现在上传的验收 JSON 中。只有脱敏布尔状态、表名和文件大小输出。失败时 CLI 只输出已脱敏的错误类别，不打印 SDK 堆栈和 Token。

## 失败、重试和副作用限制

- **严禁自动重试。** Drive 文件可能已经上传成功、Turso 表可能已经创建/INSERT 成功但报告失败。Runner 临时 SQLite 会销毁，新的 Workflow 运行会产生新的本地 ID，盲目重跑可能多上传一个 MP4、多写一条元数据，与「一次性授权」不符。
- 如果失败，先从失败步骤、脱敏 GitHub Job Logs 和 Turso 只读查询判断真实副作用，再决定是否需要新的人工授权。不要立刻再点击 Run workflow、不要新建 Token、不要清空或覆盖表。
- 工程端 `mirror_verified_drive_receipt` 不用 UPDATE/DELETE/REPLACE，使用主键和 Drive ID 唯一约束保护已有回执，不一致直接拒绝；故障恢复及跨运行幂等仍属未来改造范围。
- 任何权限、生产迁移、正式批量视频调用、公共部署都**不在** PR-30c 范围。

## 离线验证和后续实测证据

本 PR 添加 FakeDrive + SQLite 内存远程 SQL Adapter 单条联调测试、损坏下载阻断镜像、完整写入前置门禁、脱敏异常及 Workflow 手动触发静态约束。FFmpeg 专项 Job 强制运行 `tests/test_turso_canary.py`，正常 Python 3.11/3.13 CI 也运行不需要外部 Secrets 的测试。

PR-30b 真只读成功记录：[Actions #38277564945](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38277564945)，不能替代 PR-30c 的真实写入验收。
