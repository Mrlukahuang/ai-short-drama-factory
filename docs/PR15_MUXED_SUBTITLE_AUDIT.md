# PR-15e｜最终 MP4 内嵌字幕逐字逐时核验（只读技术 QA）

## 背景

PR-15d 已把演员与经审核的起止秒数写进 SRT，并校验本地 sidecar 文件 SHA256 文本摘要、时槽及整片 MP4 `mov_text` 编码存在。然而**只检查外部 SRT 正确、MP4 带字幕轨，并不证明实际播放器读到的 MP4 内部文字和时间正确**。如果成片被二次封装成另一条字幕轨，即使有人重新计算 MP4 文件 SHA256，原有检查可能误判。

## 修复

在 `inspect_offline_delivery` 的单一只读技术 QA 路径中，先对本地 SRT 与经审核 manifest 检查，再使用真正的 FFmpeg 将成片 `0:s:0` mov_text 字幕解码回 SRT 文本（命令中不含 shell，不触发 Provider/上传/写数据库），重新独立解析序号、时间、文本。对比**每一条** sidecar 与 MP4 内部轨的完整文字和起止毫秒，不允许少一条、多一条、顺序错乱、时间偏移、重复/重叠或字句变化。限制输出和 sidecar 各 128KiB、最多 96 条字幕、FFmpeg 解码 45 秒超时；抛错只返回固定错误，不泄露个人剧本、文件路径或 FFmpeg stderr。

新 QA 只在全部通过时返回 `muxed_subtitle_content_verified=true` 和 `muxed_subtitle_cues_checked=N`；原有 `subtitle_sidecar_timing_passed`、`approved_subtitle_schedule_verified` 和 `publish_approved=false` 继续保留。没有新读写外部数据库、付费模型或者新的发行权限。

## 故障注入与真实视频验收

强制 FFmpeg CI 执行新测试：创建已审核双角色 6 秒 H264/AAC/mov_text MP4，**另用 FFmpeg 替换其内嵌字幕文字或起止时间**，对伪造新 MP4 的 SHA256 和 manifest 自行重算，但本地审核 SRT 不动；新 QA 必须拦截两类篡改。对原版 6 秒片验证内嵌字幕确与 sidecar 一致，检查旧单镜头字幕样片兼容。所有 60 秒测试 Artifact 的 CI 强制要求新的 `muxed_subtitle_content_verified=true`，并把已解码条数与审核时间表条数逐一核对。

此阶段验证技术性文本/时序一致，不承诺播放器字体渲染、其他字幕流、真实嘴型/语义同步或商业授权。原有 AI 视频和真人 TTS 未实测，不能把离线技术样片称为已发布的 AI 剧集。
