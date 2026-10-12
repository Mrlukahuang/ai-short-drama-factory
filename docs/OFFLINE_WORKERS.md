# PR-18：真实离线镜头 Worker（只使用 Fake Provider）

此阶段接通 `ShotJob → 原子领取 → 本地 FFmpeg/Pillow 静态分镜镜头 → 视频文件验收 → 哈希入账 → 状态 succeeded → 整集 MP4`。多个不同 Series 可在同一 SQLite WAL 数据库中由有界线程池并行执行；每个 Production 的镜头和缓存路径完全独立。

主要内部函数：

- `run_offline_production(db, production_id, media_root, worker_id=...)`：准备由脚本/角色双审批通过的镜头任务、原子领取属于该 Production 的全部 `fake` 工作项，然后复用原有 `render_approved_preview` 生成真正可解码的视频，并逐镜校验、计算 SHA256、记录完成。
- `run_offline_multi_series(db, [production_a,production_b], media_root, max_workers=2)`：最多 4 个同时执行的 Fake Worker，最多 10 个不同 Production；不能重复提交同一个 ID。
- 完成过的镜头再次执行时复用缓存和完成状态，不再增加模型调用或任务尝试次数；同一部剧内某镜头失败，其他剧集不受影响。
- FFmpeg 或素材验收异常：尚未完成的本地任务会记录 `failed`；只有明确操作人员确认并通过 `restore_failed_job` 才能重排。已经完成的镜头不重复生成。
- Fake Provider 的 Job 可以直接从 `leased` 状态经严格 MP4 验收进入 `succeeded`，**无需付费提交意图或预算预留**。真实 Provider 不允许使用这条快捷路径。
- 每个 Fake 任务写入 `paid_model_calls:0` 的事件，供应商实际费用仍为 `NULL`（不存在对外供应商调用，不应冒充账单已核实）。
- 没有增加未经身份验证的 HTTP Worker 接口。文件输出仅保存在本机工作目录，不上传到 GitHub 仓库中的 Git 历史。

## 验收

CI 在装有固定哈希 FFmpeg/FFprobe 二进制的 Runner 上**强制**执行新媒体测试：两部剧并行独立成片、重复执行的幂等缓存、人工批准门禁、一部剧失败另一部继续、失败后需人工恢复、拒绝让真实 Provider 绕过付费保护、重复 Production 拒绝。

**还没有接通：**真实 Google 云端 Provider 的自动任务提交、轮询、预算账单核对、数据加密和身份认证；线程池仅是本地离线端到端验证，不能当作持久化生产队列或多机分布式调度。
