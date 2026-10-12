# PR-23a — R2 / AWS S3 私有视频对象存储（离线合同验证）

## 当前交付、默认门禁

- 用 `drama_factory.storage.cloud_objects.CloudTarget` 描述两种后端：`CloudTarget(provider="r2", bucket="...", r2_account_id="<32 hex>")` 或 `CloudTarget(provider="s3",bucket="...",region="ap-southeast-2")`。R2 endpoint 由官方 account ID 固定拼接；AWS 使用 boto3 标准 S3 区域客户端。不接受调用方自带任意 HTTP URL，避免 SSRF。
- `publish_cloud_artifact(db, artifact_id, local_store_root, target, operator_approved=True, client=...)` 仅允许上传 SQLite `stored_artifacts` 已登记且经本地视频验证的镜头/分集 MP4。上传对象键为 `private/<series>/<production>/<kind>/<id>/<sha256>.mp4`（成片无 shot id）。严格条件 `IfNoneMatch="*"`，目标已有同名对象不得覆盖；若返回预条件冲突，仅完整下载、验证后才能复用该对象。
- 上传先设置对象 `Metadata.sha256`、内容长度和 `CacheControl: private, no-store`；**服务端收到 PUT 成功还不算验收**，系统用 HEAD 核对记录和长度，再用 GET 逐字节读取并核查 SHA-256，最后才写入本地 `cloud_artifacts` 和只追加 `cloud_artifact_events`。
- `restore_cloud_artifact(db, cloud_copy_id, target, local_store_root, operator_approved=True, client=...)` 从私有对象存储流式拉取，验证 SHA-256、MP4 编码和中文字幕轨要求，写进原本的本地持久对象目录；之后仍可调用 PR-22 `recompose_from_stored_shots` 在另一工作目录恢复完整 MP4，**没有新的模型生成请求**。
- 默认 `DRAMA_ENABLE_CLOUD_UPLOAD` / `DRAMA_ENABLE_CLOUD_READ` 均未启用。分别必须精确设置为 `YES`，并在每次内部调用时提供 `operator_approved=True`。未满足任何一重门禁时在创建 SDK 网络客户端之前立即拒绝。
- `FakeS3ArtifactClient` 是离线合同替身，GitHub CI 不配置 AWS/R2 Secrets，不联系真实存储服务，也不会调用 Gemini/Omni 或任何视频模型。

## R2 与 S3 加密、安全设置差异

R2 S3 接口虽兼容 `If-None-Match`、`Content-MD5` 等常见操作，但 **R2 当前不接受 AWS S3 的 `x-amz-server-side-encryption` 等 SSE 请求头**。此适配器对 R2 不发送 AWS SSE 头，依赖 R2 后端默认的静态加密与控制台管理的 Bucket 设置；对 AWS S3 上传明确请求 `ServerSideEncryption="AES256"`。

**必须由运维在真实账户另外验证** Bucket 没有公开域名/公共读权限，密钥最小权限只允许目标 private/ 前缀的 HEAD/GET/PUT，是否设置生命周期/版本控制/灾备/告警。SDK 不带 `ACL` 或公开访问配置，但仅凭这一点无法证明云端 Bucket 绝对私密。AWS SSE-S3 不替代自管密钥的 SSE-KMS，如业务需要 KMS，应在后续独立评审修改。不产生任何预签名下载 URL；尚无工作人员权限体系和可审计的下载批准流程。

官方资料：
- Cloudflare R2 S3 API compatibility: https://developers.cloudflare.com/r2/api/s3/api/
- AWS S3 PutObject conditional requests: https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html

## 本地运行（此阶段只使用 Fake，不要填真实密钥）

```python
from drama_factory.storage.cloud_objects import (
    CloudTarget, FakeS3ArtifactClient, publish_cloud_artifact, restore_cloud_artifact,
)
# 仅用于受信任内部 Python 工具，不能暴露未鉴权 API。
target = CloudTarget(provider="r2", bucket="private-drama-test", r2_account_id="a"*32)
client = FakeS3ArtifactClient()
# 测试中 monkeypatch 设置环境变量 DRAMA_ENABLE_CLOUD_UPLOAD/READ=YES
record = publish_cloud_artifact(db, known_artifact_id, local_root, target,
                                operator_approved=True, client=client)
result = restore_cloud_artifact(db, record["id"], target, new_local_root,
                                operator_approved=True, client=client)
```

真实运行需另外安装 `python -m pip install -e '.[cloud-s3]'`，并在受控机器使用 boto3 的标准 AWS 密钥链（对 R2 用它的独立 S3 API token）。**不要把密钥、Cloudflare Account Token、预签名链接或视频文件提交到 GitHub、聊天记录或仓库。**

## 失败语义与仍然未实现的能力

- 只有完整验证后写入云端资产目录；若 PUT 成功而核验/数据库提交失败，会留下未登记远程对象。同一资产重试时条件写入返回 412，程序检查远端文件 SHA256 一致才补记目录。
- 云端和本地数据库不存在原子跨系统事务。即便是相同 SHA 对象，也不能证明目标 Bucket 从未公开；运维必须设置私有 Bucket 政策及合理删除/版本控制流程。
- 远端文件篡改、长度、元数据或本地镜头 Series 绑定不匹配均拒绝恢复。远端恢复时会发生 S3/R2 网络和存储操作的潜在费用；**代码默认关闭，不代表真实云端免费**。
- 对象存储层不办理素材上传版权授权、公网下载、密钥托管、威胁扫描、跨租户权限、预签名 URL、云账单核对或持续 Worker；这些都放在 PR-23b/后续上线准备中。
- 此 PR 只在 GitHub CI 的 FakeS3 Client 上跑模拟上传/恢复，**尚未验证任何用户 R2 或 AWS 账户的实际连通性。**

## 强制验收

普通 Python 3.11/3.13：配置/域名校验、默认禁止真实云端调用、Fake S3 合同；FFmpeg 专项 CI：用真正生成的 H264/AAC/mov_text MP4 试验 R2/S3 请求头、远端传输前后完整 SHA256、重复上传不覆写、错误返回/重启续传、两部剧隔离、伪造/损坏对象拒绝，以及把两段从模拟云端下载到全新本地对象目录后重新剪出带字幕完整分集。


## PR-24：一次性手动真实私有云端验收（未触发）

单独的 [GitHub Actions 工作流](../.github/workflows/private-cloud-canary.yml) 标题 **Manual private R2/S3 MP4 canary (may incur storage charges)**，仅在管理员从 GitHub Actions UI 显式 Run workflow 并输入 `TEST_ONE_PRIVATE_CLOUD_MP4` 时可能运行真实云操作。PR、push、CI 不会触发这个工作流。Workflow `permissions: contents: read` 且通过 concurrency 序列化执行。

### 仓库所有者手动设置的 Secrets

在私有仓库 Settings → Secrets and variables → Actions 添加：

- `CLOUD_STORAGE_ACCESS_KEY_ID`：该私有 Bucket 的最小权限 S3/R2 access key。
- `CLOUD_STORAGE_SECRET_ACCESS_KEY`：对应 secret key。
- `CLOUD_STORAGE_BUCKET`：新建或已经批准用于测试的**私有** Bucket 名称。
- Cloudflare R2 选择时另加 `CLOUD_R2_ACCOUNT_ID`（32 位十六进制 Account ID）；AWS S3 选择时另加 `CLOUD_AWS_REGION`（如 `ap-southeast-2`）。

**不得把任何密钥发到 ChatGPT、GitHub Issue/PR 或提交到 Git。** 本仓库不要求额外的 `GEMINI_API_KEY`，也不会生成任何收费 AI 视频。

### 手动操作

打开仓库 Actions，选择 `Manual private R2/S3 MP4 canary (may incur storage charges)`，点击 `Run workflow`，选最新 `main`、`provider=r2` 或 `s3`，输入 `TEST_ONE_PRIVATE_CLOUD_MP4`。工作流创建独立测试剧集与双审核分集，用本地 FFmpeg 渲染**一个 2 秒虚构技术成片**，并对这**一个** MP4 执行私有对象上传、远端完整 GET SHA256、恢复下载并重算媒体格式。成功后会提供不含密钥的 `private-cloud-canary-verification` Artifact：包含 SHA256、对象键、真实已读回数据与 `new_ai_model_generation_calls: 0`。

**费用/保留提醒**：R2/S3 的 PUT、GET 和存储及可能的数据传输可能计费；单次只创建一个对象，**不自动删除云端对象**，避免影响其他数据。管理员在确认备份和审计后，自行通过云控制台的正确前缀删除测试对象或启用合适生命周期规则。测试仅证明当前凭证有权限并且上传下载内容一致，**不能证明 Bucket 无公开策略或 IAM 最小权限配置正确**，这些还需用户独立核验。

在没有云 Secrets、没有手动确认时，工作流不运行且云操作代码立即 fail-closed。普通 CI 的 `tests/test_cloud_canary.py` 使用 FakeS3 Client，不接触真实云；另外模拟了手动 live 执行的相同 Python 调用路径、回执验收和默认锁定。

本工作流是操作员触发的私有存储验证，**未提供给最终用户公开上传或下载入口，也没有启用签名 URL 或后台定时任务。**
