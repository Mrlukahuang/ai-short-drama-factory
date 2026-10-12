# PR-25：优先使用 Google Drive 保存短剧视频素材

## 为什么选择 Google Drive

系统保持三层分工：

- **Google Drive**：作为实际 MP4 视频素材、技术成片、后续审核素材的文件资产库。
- **Turso（规划中的远端 SQL 层）**：用于镜头、剧集、文件 ID、SHA-256、生成状态和成本索引。当前此短剧仓库实际采用本地 SQLite；**本 PR 不声称已经完成 Turso 迁移**。
- **Gemini**：生成图片/视频；Google Drive 并不会自动与 Gemini 模型输出联通，仍需独立下载和写入资产库。

这条路线能够尽量复用已拥有的 Google Drive 存储空间，但用户的 ChatGPT Drive 连接权限**不是 GitHub Actions 或独立 Python 程序的凭证**。本 PR 不收集、不上传任何用户密钥。

## 能力

- `drive_objects.publish_drive_artifact(db,artifact_id,local_root,parent_folder_id,operator_approved=True,client=...)`：仅上传已在 `stored_artifacts` 中登记且验证通过的 MP4。逐层确认 `ai-short-drama-factory/<series>/<production>/<kind>/<shotJob>/<sha256>.mp4` 文件夹，采用 Google Drive API v3 的**可续传上传**，不更新、覆盖、删除或共享已有文件。
- 每个 MP4 的 `appProperties` 记录本地 Artifact ID 与 SHA-256；上传后必须重新读回整个文件并计算 SHA-256，不能只相信 Google Drive File ID、大小或 MD5。文件或目录碰撞、冒名文件、跨剧集错误路径均拒绝。
- `restore_drive_artifact(db,drive_copy_id,new_local_root,parent_folder_id,operator_approved=True,client=...)`：只可下载自己账本中与父文件夹绑定的文件；再次检查元数据、完整字节哈希与 MP4 格式，写入现有本地不可覆盖资产目录，可再使用 `recompose_from_stored_shots` 重建分集。
- 新的 `drive_artifacts` / 追加式 `drive_artifact_events` SQLite 资产收据保留远端 File ID、视频哈希、剧集归属、存放文件夹、审计动作。
- 默认关闭：`DRAMA_ENABLE_DRIVE_UPLOAD=YES` + 当前调用 `operator_approved=True` 才上传；读取使用独立 `DRAMA_ENABLE_DRIVE_READ=YES` 双重控制。没有运行中的公网入口、后台任务或自动模型调用。
- FakeDriveClient 全部在内存中，CI 无 Google 登录或云请求。真实连接需 `python -m pip install -e '.[drive-storage]'` 和单独授予 `https://www.googleapis.com/auth/drive.file` OAuth scope；代码仅在显式使用时从受控环境变量 `DRAMA_DRIVE_USER_OAUTH_JSON` 读取用户授权信息。**绝不能提交令牌或把 JSON 发送到聊天。**

## 为什么没有采用 Service Account

Google 官方文档说明 Service Account 不能拥有 My Drive 文件；它们需要 Google Workspace 共享云端硬盘或域委派。对于用户当前希望直接利用个人 Google Drive 的情况，应当走用户 OAuth 2.0 授权，且只授权应用自己创建的文件。手动授权和 GitHub Secret 的接入将单独验收，不能自动借用 ChatGPT 连接。

## Google API 使用与限制

Drive API v3 支持 resumable upload 处理网络断线和较大的视频文件；本 PR 的上传适配器采用 `MediaFileUpload(...,resumable=True)`。远端文件允许按 Drive 配额计入存储空间，超过已有存储套餐可能需要另付费用。OAuth、项目配额和 Drive 文件权限限制须在实际账户冒烟测试中核实。

官方资料：

- https://developers.google.com/workspace/drive/api/guides/manage-uploads
- https://developers.google.com/workspace/drive/api/guides/about-shareddrives
- https://developers.google.com/workspace/drive/api/guides/properties

## 尚未完成

本 PR **没有上传任何真实 Drive MP4**，也没有登录你的 Google 帐号、创建你现有 Drive 中的文件夹、生成 OAuth refresh token 或接入 Gemini 云端 Worker。没有公开文件分享、公开 URL、文件自动清理、跨机分布式上传锁、云端故障自动修复、批量容量/流量告警。Google Drive 是当前优先路线；既有 R2/S3 代码保持默认关闭作备选。

## CI

Python 3.11/3.13：防未授权访问、ID 校验和现有全套回归；FFmpeg 作业强制新增真实 MP4 测试：上传/读取回环、删除本地存储后恢复、两个剧集各自独立 Drive 目录并从恢复素材重新合成、远端损坏/不合法元数据拒绝、现有同名对象不覆盖、事件不可篡改。