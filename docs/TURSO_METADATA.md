# PR-29 — Google Drive 验收后的 Turso 元数据索引（已于 PR-30c 完成真实单条写入验收）

## 实测进展（2026-10-13）

已在独立短剧 Turso libSQL 库通过 PR-30b 真只读验收 [Actions #38277564945](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38277564945)，并通过 PR-30c 一次实际 Google Drive MP4 双向校验 → 远端表创建、单条 INSERT、全字段回读验收 [Actions #38279948391](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38279948391)。后者报告 MP4 大小 62,676 字节、SHA256 匹配、`turso_metadata_inserted=true`、`turso_full_row_readback_verified=true`，AI 调用次数为 0。**这是专用元数据表的实际写入，不是旧 SQLite 整库迁移或生产并发验收。** 详见 [TURSO_PR30C_WRITE_CANARY](TURSO_PR30C_WRITE_CANARY.md)。

## 目标与边界

目前 AI 短剧工厂在 GitHub Actions 上的 SQLite 工作目录会随 Runner 结束而删除。2026-10-13 已经通过用户私有 Google Drive 的真实 2 秒 MP4 上传、下载、SHA256 验收（Actions #38263456798），但那个测试产生的临时 SQLite Drive 文件 ID 目录**不会自动保存到远端**。

本 PR 首先实现单条**已经通过 Google Drive 双向验收的资产回执**向独立 Turso 数据库的安全同步，不贸然把全量镜头/预算/审核事务迁到远端。

- 本地 SQLite 仍是审核、生产、预算和恢复流程的**当前唯一权威数据库**；不改动现有 Worker，不会触发真实生成。
- 专用表 `drama_drive_receipts_v1` 记录 `drive_copy_id`、`artifact_id`、`series_id`、`production_id`、`episode_id`、`shot_job_id`、`kind`、`object_key`、`sha256`、`size_bytes`、`drive_file_id`、`parent_folder_id`、`remote_folder_id`。
- **不保存**视频二进制、OAuth token/secret、个人邮箱、提示词、版权原文、临时本地文件路径、Google API 回执正文。
- 源数据必须有两条审计事件 `uploaded_verified_by_download`、`downloaded_verified_local_copy`。再次检查已恢复到本机持久对象目录的真实 MP4 字节、媒体轨、SHA256、Series/Production 归属；任一失败则 **不发起远端 SQL**。
- 插入仅允许一次，重复运行只读回校验。已有记录不一致或同个 Drive File ID 企图重复登记时直接失败；**无 UPDATE/REPLACE/DELETE**。
- 执行成功以后还要在 Turso 远端完整 `SELECT` 并逐字段核对；只返回脱敏状态摘要，没有远程存储密钥、File ID 或其他账号数据。
- 模块 `drama_factory.storage.turso_receipts` 是内部 Python 接口，**没有公网 FastAPI 写接口或无鉴权后台自动任务**。

## 两种 Turso 引擎必须明确区分

Turso 现有 **libSQL（原 Turso Cloud）** 与新版 **Turso Database** 的 Python 远程 SDK 不一样，官方推荐如下：

- 已存在 **libSQL 数据库**：`python -m pip install -e '.[turso-libsql]'`，`TursoMetadataTarget(url="libsql://ai-short-drama-factory-<org>.<region>.turso.io",engine="libsql")`，使用 `libsql.connect(database=...,auth_token=...)`。
- 新建 **Turso Database**：`python -m pip install -e '.[turso-serverless]'`，`TursoMetadataTarget(url="https://ai-short-drama-factory-<org>.turso.io",engine="turso")`，使用 `turso_serverless.connect(...,auth_token=...)`。

见 Turso 官方 Python Quickstart：https://github.com/tursodatabase/turso-docs/blob/main/sdk/python/quickstart.mdx 。

用户其他项目已经存在的 Turso 数据库和表**不能复用**：为避免触及其他产品，适配器强制域名是 `ai-short-drama-factory-<org>.turso.io` 或 Turso 官方实际返回的 `ai-short-drama-factory-<org>.<region>.turso.io`。域名仍须使用短剧专用数据库前缀，禁止其他项目的域名；路径、端口、查询字符串和 URL 内凭据继续拒绝。如果数据库名称不同，需要先人工确认该数据库确实独立属于本短剧项目，再决定是否修改这一限制，不应为了连通先去取消安全校验。

## 默认关闭及环境变量

独立部署时仅在操作者**明确选择**镜像某个经过验证的 Drive copy ID 后调用；GitHub 普通 CI 不提供 Turso Token，不联网：

- `TURSO_AUTH_TOKEN`：仅放进私有执行环境的 Secret；不要发送给聊天、提交 GitHub 或印在日志里。
- `DRAMA_ENABLE_TURSO_METADATA_WRITE=YES`：明确开启写入。
- `DRAMA_TURSO_WRITE_CONFIRM=MIRROR_VERIFIED_DRIVE_METADATA`：人工操作确认。
- Python 函数仍需 `operator_approved=True` 和明确 `TursoMetadataTarget`。

模块不自动从其他项目的环境变量查找数据库 URL，也不根据凭证去枚举数据库。手动只读查看专用数据库/权限之前，不会执行真远端 SQL。

## 本轮测试

`pytest -q tests/test_turso_receipts.py`

- 按真实 FFmpeg MP4 和 FakeDrive 上传下载生成 **Series A/Series B** 的独立回执；向内存 SQLite 模拟 Turso SQL 协议，无 HTTP、凭证、视频模型调用。
- 认证门禁、引擎 URL 约束、双向 Drive 验证不可缺、远端字段逐项复核、同内容重复运行幂等、冲突/跨剧隔离、文件损坏拒绝。
- 在 GitHub 的 FFmpeg 专项 CI **强制运行**相关测试。这个结果证明的是镜像逻辑，而非真实 Turso 云端数据库的兼容性；PR-30 将用独立新库实测引擎及权限后才能称为云端可用。

## 仍待完成的项目

PR-30b/PR-30c 已在独立短剧数据库真实验收一条 metadata mirror。但短剧工作流仍依赖 Runner 临时 SQLite 生成源回执，完成后 Runner 本地账本不作跨运行持久化承诺。下一阶段 PR-31 需另行规划生产数据库的原子交易、租约、预算审核迁移与断线恢复，**不能将这一步的 metadata mirror 说成整套短剧生产数据库已经迁移**。本次一次性云写入授权已使用，不得未经新授权重复触发上传或写入。
