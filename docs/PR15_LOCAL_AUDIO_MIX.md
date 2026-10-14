# PR-15b — 本地对白音轨与背景音乐混音（离线）

现在已存在经剧本和人物审核的 Episode → 分镜 → 可播放 H.264/AAC/字幕 MP4 以及 SHA256/FFmpeg QA。本 PR 增加在**最终拼接、质检之前**选择本地 PCM WAV 对白和背景音乐的交付链路，不下载任何媒体、不使用 TTS、不调用视频服务。

**输入合同：** `render_approved_preview(..., dialogue_audio=Path(...), music_audio=Path(...), operator_confirmed_audio_rights=True)`；对白或音乐可任选一个或同时提供，但需要明确的声音使用权自我确认。仅支持本机存在、非符号链接、≤32MiB、单条音频流的 PCM WAV（16/24 位整数或浮点，16–96kHz，单声道或立体声）。对白不得超过目标时长 0.25 秒以上，短对白将补静音；背景音乐须覆盖整个目标时长。两条 stem 均对内容计算 SHA256，混音前再次核验未被替换。

**混音策略：** 若有外部对白，用它**替代**原片音轨，避免同时播放原始视频自带对白造成重叠；没有外部对白则保留原始音频。背景音轨按 0.16 倍音量衰减并与对白/原音轨合并，经限幅输出单条 AAC；已有 H.264 图像流与 `mov_text` 字幕轨不重新编码。最终整体重新计算 MP4 SHA256，并重新执行 PR-14 的整片完全解码、字幕逐镜时间轴、镜头缓存哈希与原始角色/剧集审核门禁。对白/配乐变动只修改最终混音，不使已经校验过的镜头缓存失效。

**安全与边界：** `operator_confirmed_audio_rights=True` 只是技术上的自我确认，不是经律师核验的商业授权；回执始终标记 `voice_license_independently_verified=false`、`spoken_dialogue_generated=false`、`publish_approved=false`、`production_ready=false`。没有将本地音频上传云端。完整音画同步、演员声线授权、TTS 供应商真实调用、付费账单、人工审片和正式发行仍未完成。

**验证：** GitHub `offline-video` 专项用本机 FFmpeg 合成不同频率的 WAV，通过两 stem 混音、音乐单独覆盖、字幕轨保留、整片技术 QA、失效音频预检、授权确认、声音内容变化后仅更新最终音轨、缺少真实声音使用权无法自动发布等测试。其他 CI 完全不需要云端凭据或收费模型。该离线能力不是 PR-10 真人/AI TTS 已完成。
