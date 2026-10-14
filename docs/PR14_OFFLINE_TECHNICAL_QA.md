# PR-14a｜离线技术质检（不等于 AI 正式成片）

增加纯本地 `inspect_offline_delivery(manifest, media_path)` 作为下游审片前的**技术证据**，不修改数据库、不调用外部供应商、不批准发布。

技术验收：必须属于给定 manifest 的原始 MP4、哈希逐字节匹配、文件大小有界、纵向 H.264/AAC 和 mov_text 软字幕流、真实 FFmpeg 完整视频/音频解码；每一镜头的 SRT sidecar 时间从 0 开始、逐段连续、与 manifest 的镜头时长相同，字幕文本必须非空。检验结果只返回技术布尔量及镜头数量/秒数，不返回对白文本、资源路径、文件指纹或角色隐私信息。

严禁混淆：现阶段离线 preview 使用图片卡片、合成音调或用户本地现有视频，不等于真正 AI 视频；即使 `placeholder_visuals=false` 也不能证明外部媒体的来源、授权或真实性。因此 `genuine_ai_video_verified=false`、`spoken_dialogue_verified=false`、`visual_continuity_verified=false`、`copyright_scope_verified=false`、`operator_review_required=true`、`publish_approved=false`、`production_ready=false` 永久保留。参数 `require_real_footage=True` 会主动拒绝，而不是把离线文件误认成真实剧集。

专用免费 CI 中对真正由 FFmpeg 生成的预览 MP4 执行完整解码和字幕时序验收，此外覆盖腐败 MP4、hash 错误、字幕损坏或丢失、重复镜头、长度不一致、错误付费声明、冒充生成对白及错误媒体路径。普通测试矩阵仍兼容没有 ffmpeg 的环境；第四个 `offline-video` Job **显式包含**新测试文件、不可偷偷跳过。

剩余 PR-14 后续范围：与演员视觉参考一致性、连续性以及人工审片 UI 对接。这些不能仅凭 FFmpeg 格式和散列检验就声称完成；正式成片、收费镜头账单和实际发行都未在本阶段启动。
