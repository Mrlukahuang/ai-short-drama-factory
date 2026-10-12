# PR-19：Google 已生成视频的镜头级安全恢复

此模块 `drama_factory.jobs.google_recovery` 是针对**已经完成真实生成并取得 Google Files 文件 ID** 的结果下载桥接，不是新的视频生成 Worker。

## 运行流程

`双审批 Production → 既有 Google shot_jobs → 三层预算预留 → generation_intent → provider_task_id → 人工绑定 Google Files ID → 仅下载既有 MP4 → ffprobe 校验时长和来源 SHA256 → shot_jobs.succeeded → 以已有镜头为输入合成 MP4`

主要内部函数：

- `bind_existing_google_file(db, job_id, file_id, operator_reviewed=True)`：仅供受信任本地操作者。仅在当前 Job 属于 Google、已有提交意图及供应商 Task ID、模型与状态符合时，可登记一次文件 ID；之后只能重用同一 ID。
- `recover_existing_google_shot(db, job_id, root, operator_reviewed=True, provider=...)`：使用 Google `recover_existing`（get/download）抓取**以前已生成**的视频。独立验证媒体是否可解码、持续时间、SHA256 与供应商回执。发生文件下载完成后进程退出的情况，可继续从校验过的本地文件完成入库，无需二次下载。
- `unlock_stale_google_recovery(..., operator_reviewed=True)`：崩溃导致持久下载锁未释放时的人工解锁。**不要在另一个下载仍运行时解锁**。
- `compose_recovered_google_shots(db, production_id, root)`：确认属于当前 Production 的成功镜头文件路径和哈希，再交给现有 FFmpeg 合成器；其他尚未恢复的镜头保留占位画面。返回并持久化 `new_model_generation_calls=0`、`historical_vendor_charge_unverified=true`，不把过去已经计费的生成误当本次零成本。

## 真实界限和安全风险

本 PR **没有运行任何 Google 真实生成或下载**，所有下载交互均为本地 Fake SDK Stub。未开启公开 API、未导入凭证或密钥、未自动处理 PR #14 以前没有记录文件 ID 的历史失败。

由于 Google 文件 ID 和镜头 Job 的语义关联暂不能从账单或平台端自动验证，绑定要求人工审核。这是受信任本机服务，不是多租户生产级身份鉴权。生产场景应新增独立云存储、权限与加密、防病毒/恶意视频隔离、真实账单核对、经供应商任务句柄核实的文件关联、R2/S3 生命周期。

**严禁**在镜头恢复失败后自动重新调用 Google `interactions.create`；如果来源视频已被 Google 清理，必须交由人工处理。既有付费调用仍可能已计费，下载模式只保证不提交**新的生成请求**。

## 离线验收

`pytest -q tests/test_google_recovery.py`

CI 在 FFmpeg 环境强制验证真实测试视频的下载恢复与镜头入库、镜头缓存、完整 H.264/AAC/mov_text MP4、跨剧隔离、错误模型与文件 ID 拒绝、伪造回执及下载后崩溃恢复。
