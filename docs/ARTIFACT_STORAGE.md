# PR-21：视频资产独立发布与本地内容寻址目录

**解决的问题：**之前 `work/<series>/<production>/preview.mp4` 和镜头缓存只保留在 FFmpeg 制作目录里，清理临时文件会把成果一起删掉。现在可选把已通过媒体校验的 MP4 发布到另一套目录和数据库资产账本，作为以后衔接 R2/S3 的基础。

## 能力范围

- 内部函数 `publish_episode_preview(db, production_id, work_root, store_root)`：核查原 Production 已经过剧本和人物审批且处于 `offline_preview_finished`，从保存的 manifest 比对生产 ID、剧集 ID、路径、SHA256、目标时长和 H.264/AAC/mov_text 流，再将 MP4 发布到独立目录。
- `publish_shot_video(db, shot_job_id, work_root, store_root)`：要求镜头任务处于 `succeeded`，来源 MP4 位于该 Production 的工作目录之下，源文件与 Job 哈希和镜头时长一致。
- `verify_stored_artifact(db, artifact_id, store_root)`：读取独立存储对象，不依赖工作目录；核对数据库目录、文件大小、SHA256、视频/音频编解码器、分辨率以及成片字幕轨。发现篡改立即拒绝。
- 存储路径为受限 ID 及 SHA256 生成，不采用外部上传文件名。例如 `<series>/<production>/shot_video/<job>/<sha256>.mp4`、`<series>/<production>/episode_preview/<sha256>.mp4`。先复制到独占临时文件，计算实际写入的字节哈希并 `fsync`，再以硬链接不可覆盖地发布，同一对象的重复调用返回既有目录记录。
- `run_offline_production(...,store_root=...)`、`run_offline_multi_series(...,store_root=...)` 与 `compose_recovered_google_shots(...,store_root=...)` 均为可选接入；没有显式传入 `store_root` 则保持旧行为、不改变外部费用和审核规则。
- 新增 SQLite `stored_artifacts`，按 Series/Production/Shot Job 关联每个已验证的对象及哈希，统一查询可追溯。

## 本地样例

```python
from pathlib import Path
from drama_factory.storage.artifacts import publish_episode_preview, verify_stored_artifact

saved = publish_episode_preview(
    db, production_id,
    work_root=Path("artifacts/offline-preview"),
    store_root=Path("data/persistent-video-objects"),  # 必须位于不同的磁盘管理生命周期
)
checked = verify_stored_artifact(db, saved["id"], Path("data/persistent-video-objects"))
assert checked["verified"]
```

## 明确界限

- **不是云端持久存储**。这一步是独立的本机路径 + SQLite 账本；原机器损坏、磁盘丢失、未备份，都可能导致资产丢失。建议 `store_root` 保持在不被清理的持久卷，不放入 Git，也不要放在临时的工作目录下。
- 仅信任内部受控 Python 进程和本地磁盘目录，**不接受公网 URL、不提供未认证访问接口**。不等同恶意上传文件隔离沙箱、云 KMS 加密、S3/R2 多副本、签名下载和 RBAC。上述部分尚需 PR-22 开发。
- `episode_preview` 明确代表已完成的技术预览，不能被解读为正式 AI 真人成片、人工审片批准发布或版权检查完成。
- 仅发布已经存在的视频，**不调用 Google Omni、TTS、图像模型或任何付费供应商**。账单与预算行为没有变化。
- SQLite 账本与磁盘操作不可能完全共用一个事务。若写完对象后数据库写入失败，可能留下合法未登记对象；相同参数再次执行可验证并登记，而不会覆写对象。

## 测试

CI 在具备真实 FFmpeg/FFprobe 的作业强制运行 `tests/test_artifact_storage.py`，验证工作目录删除后的可恢复读取、镜头+整集重复发布、被篡改的原始文件及独立存储对象的拒绝、符号链接路径阻断、两部剧并行发布各自隔离以及未审核任务无法发布。
