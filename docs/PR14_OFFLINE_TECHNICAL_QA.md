# PR-14a｜离线技术质检（不等于 AI 正式成片）

增加纯本地 `inspect_offline_delivery(manifest, media_path)` 作为下游审片前的**技术证据**，不修改数据库、不调用外部供应商、不批准发布。

技术验收：必须属于给定 manifest 的原始 MP4、哈希逐字节匹配、文件大小有界、纵向 H.264/AAC 和 mov_text 软字幕流、真实 FFmpeg 完整视频/音频解码；每一镜头的 SRT sidecar 时间从 0 开始、逐段连续、与 manifest 的镜头时长相同，字幕文本必须非空。检验结果只返回技术布尔量及镜头数量/秒数，不返回对白文本、资源路径、文件指纹或角色隐私信息。

严禁混淆：现阶段离线 preview 使用图片卡片、合成音调或用户本地现有视频，不等于真正 AI 视频；即使 `placeholder_visuals=false` 也不能证明外部媒体的来源、授权或真实性。因此 `genuine_ai_video_verified=false`、`spoken_dialogue_verified=false`、`visual_continuity_verified=false`、`copyright_scope_verified=false`、`operator_review_required=true`、`publish_approved=false`、`production_ready=false` 永久保留。参数 `require_real_footage=True` 会主动拒绝，而不是把离线文件误认成真实剧集。

专用免费 CI 中对真正由 FFmpeg 生成的预览 MP4 执行完整解码和字幕时序验收，此外覆盖腐败 MP4、hash 错误、字幕损坏或丢失、重复镜头、长度不一致、错误付费声明、冒充生成对白及错误媒体路径。普通测试矩阵仍兼容没有 ffmpeg 的环境；第四个 `offline-video` Job **显式包含**新测试文件、不可偷偷跳过。

剩余 PR-14 后续范围：与演员视觉参考一致性、连续性以及人工审片 UI 对接。这些不能仅凭 FFmpeg 格式和散列检验就声称完成；正式成片、收费镜头账单和实际发行都未在本阶段启动。

## PR-14b 实际成片提交前门禁

`render_approved_preview(...)` 在真实 FFmpeg H264/AAC + mov_text MP4 编码之后、**首次更新**生产状态/结果 JSON 及写入 manifest 文件之前，强制调用只读 `inspect_offline_delivery(manifest, final)`。所有 QA 字段（含 `operator_review_required=true`, `publish_approved=false`）写入生成结果和数据库，后续审片工作台可追溯技术证据。技术质检失败转为固定 `PreviewError`，数据库保持原 `ready_for_video_generation`，不得声称成片已完成；再次经过本地校验通过后可复用已有的离线镜头缓存，不额外请求任何付费 Provider。

这是**技术预览状态**，不能以 `offline_preview_finished` 或 `technical_decode_passed` 替代真人视觉一致性、人类授权、版权或生产上线审核。此次操作没有任何真实云端写入。测试覆盖故障注入和恢复、真实数据库状态/JSON/manifest 同步及重复渲染离线缓存。

## PR-14c 镜头缓存完整性修复

离线镜头按审核剧本和来源视频 SHA256 生成稳定 cache key，但是原复用逻辑只运行 `ffprobe`，**另一个同样时长/编码的视频即使被错误复制到缓存路径，仍可能被复用**。本 PR 给每段真正渲染完成的 H264/AAC clip 另存 SHA256 完整性 marker（在同目录使用原子文件替换）；每次命中缓存先独立重新计算视频字节 SHA256，对不上或 marker 丢失就只重建相应镜头。渲染 manifest 另存每镜 `clip_sha256`，PR-14b 的总片 QA 再逐一核对实际 clip 是否与交付时的指纹相符。所有检查都只读已有视频字节，发现问题后重建的是**本地缓存**，不会产生外部 Provider 调用。

新增真实 FFmpeg 测试用 B 镜头完整替换 A 镜头（两者都是**有效且等时长的 MP4**），确认只重建 A，B 继续复用且总片 SHA256 恢复原值；另测试删除 marker、总片生成后单个 clip 被替换时被最终 QA 阻断。此哈希 marker 只是检测本地事故/非授权修改的完整性线索，**不是签名与最小权限机制**，不能防止可同时修改 clip 和 marker 的恶意攻击者；正式云端对象/团队权限仍需独立验收。
