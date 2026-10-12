# PR-26a：给个人 Google Drive 授权，并安全执行一次 MP4 上传 / 下载测试

本短剧工厂已经支持独立栏目与 Series 的 MP4 资产归档。本 PR 只补齐**本机 OAuth 授权 → GitHub Secrets → 手动上传一个原创 2 秒 MP4 → 从 Drive 下载并复核 SHA-256** 的入口。普通 CI 全部 FakeDrive，无 Google API 调用，也不会调用 Gemini 模型。

## 1. Google Cloud Console（仓库拥有者操作）

1. 在 https://console.cloud.google.com/ 建立或选择独立项目 `AI Short Drama Factory`。
2. 在 API Library 中启用 **Google Drive API**：https://console.cloud.google.com/apis/library/drive.googleapis.com 。
3. 进入 Google Auth Platform → Branding / Audience / Data Access。个人 Google 账号通常使用 **External**；Testing 时添加**自己的 Google 邮箱**为 Test user，声明最小 scope `https://www.googleapis.com/auth/drive.file`。不要申请完整 `https://www.googleapis.com/auth/drive`。
4. 进入 Clients → Create Client → **Desktop app**，下载客户端凭证 JSON。仅保存在用户自己的电脑上；不得发送给 ChatGPT 或提交 GitHub。

注意：External + Testing 的 refresh token 通常 **7 天过期**，如果未来希望 GitHub 长期自动同步，应评估 Google OAuth 应用的 In production 发布状态及 Google 当前的验证规定。不要误以为一次测试授权可以永不过期。

## 2. 在自己的 Mac 运行最小权限 OAuth

在仓库根目录执行（无需复制项目里的视频或客户素材）：

```bash
git clone https://github.com/Mrlukahuang/ai-short-drama-factory.git
cd ai-short-drama-factory
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,drive-storage]'
python -m drama_factory.storage.drive_authorize \
  --client-secrets "$HOME/Downloads/credentials.json"
```

最后一行的路径要替换为 Google Cloud 实际下载的 JSON 文件名称。浏览器打开 Google 授权页面后，只允许本应用 `drive.file` 权限。脚本只在 My Drive 顶层创建/复用**由本应用创建的** `AI Short Drama Factory - Private Videos` 文件夹。

脚本输出：**文件夹 ID**、本机凭证文件保存路径和 `0` 个上传文件。默认令牌文件存放于 `~/.config/ai-short-drama-factory/drive-user-oauth.json`，采用权限 0600，不输出令牌正文。已存在凭证文件时会拒绝覆盖，以免误刷新。客户端下载文件与令牌文件都不能提交 GitHub 或发送聊天消息。

为什么不是手动建立文件夹：`drive.file` 默认仅能访问本应用创建或用户通过 Picker 授权的文件。由脚本自动建专属根文件夹，避免人工在 Google Drive 创建了文件夹、应用却无权访问的问题。

## 3. 用户自己把两个值保存成 GitHub Actions Secrets

打开 GitHub 仓库 Settings → Secrets and variables → Actions → **New repository secret**，创建：

- `DRAMA_DRIVE_USER_OAUTH_JSON`：本机 `~/.config/ai-short-drama-factory/drive-user-oauth.json` 的完整内容（包含敏感 refresh token / client secret）。
- `DRAMA_DRIVE_PARENT_FOLDER_ID`：授权脚本输出的专用文件夹 ID（非秘密，但仍存为 GitHub Secret）。

避免复制令牌到浏览器历史或聊天记录，也可以在自己的 Mac 上用已登录 GitHub CLI 直接设置：

```bash
gh auth login
gh secret set DRAMA_DRIVE_USER_OAUTH_JSON \
  --repo Mrlukahuang/ai-short-drama-factory \
  < "$HOME/.config/ai-short-drama-factory/drive-user-oauth.json"
gh secret set DRAMA_DRIVE_PARENT_FOLDER_ID \
  --repo Mrlukahuang/ai-short-drama-factory \
  --body "将授权脚本输出的文件夹ID填在这里"
```

不要把 OAuth 文件内容输出给 ChatGPT，不要将其发送到公开 issue 或 commit。

## 4. 一次真实 Drive 人工冒烟测试

完成上述两个 GitHub Secrets 后，打开仓库 **Actions → Manual private Google Drive MP4 canary → Run workflow**，从最新 `main` 运行，填写确认词 `UPLOAD_ONE_PRIVATE_TEST_MP4`。

此 workflow 具有 `contents: read` 权限，不在 PR 或 push 后运行。它会使用 FFmpeg 创建一个本地原创虚构短剧（2 秒、2 镜头），以正常审核门禁生成**一个**已审查的 MP4，再在个人 Google Drive 的专用私有文件夹里创建这个 MP4，下载后验证 SHA256、视频轨与字幕；GitHub Actions 只上传不含 OAuth 秘钥、Drive file ID 或播放 URL 的简短验证 JSON。不会公开分享文件，不调用 Gemini，不触发付费视频生成。

**潜在费用**：Google Drive 文件会占用 Google 账号剩余配额；Google Cloud/Workspace 可能存在配额和项目计费要求。脚本不会开启 Google Cloud Billing、不会清空其它文件夹，也不会自动删除文件。长期大量视频仍需容量管理。

## 5. 界限与下一阶段

- ChatGPT 中的 Google Drive 插件已经连上，不等于 GitHub Actions 可直接使用其授权；以上 OAuth 和 Secrets 是给独立 Python Worker 的。
- 本代码默认关闭真实 `DRAMA_ENABLE_DRIVE_UPLOAD` 和 `DRAMA_ENABLE_DRIVE_READ`。自动生成短剧 Worker 不因授权成功而开启。
- 此阶段尚未真实上传任何用户 Drive 文件。只有用户手动触发、GitHub Actions 显示成功，并核实 Drive 中存在文件才能说真实链路跑通。
- **Turso 迁移在短剧仓库还没做**。下一阶段会独立规划任务、资产 ID、生成状态与花费的 SQLite → Turso 兼容方案；不能将用户其他项目已有的 Turso 数据库直接复用成这个项目的生产数据库而不规划 schema/权限。

官方文档：
- https://developers.google.com/workspace/drive/api/quickstart/python
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/identity/protocols/oauth2
