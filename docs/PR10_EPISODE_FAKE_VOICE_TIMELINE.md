# PR-10b — 已审核逐镜头台词 → Fake WAV → 60 秒合并对白时间线

在 PR-10a 的受审核音色资产/来源同意门禁、镜头台词幂等 FakeDialogueAudioProvider 和 PR-15b/15c 的本地音乐混音上，再打通**整个 Episode 的逐镜头 Fake 音轨时间线**。这仍是离线占位音技术测试，不是真人演员对白或 TTS。

`build_fake_episode_dialogue_timeline(db, production_id, voice_asset_id, output_root, operator_confirmed_voice_rights=True)` 会先检查 Production 双审批、镜头时长之和、≤12 镜头/90 秒。当前样例合同仅允许**每个镜头一行已批准台词**，若多行则拒绝，避免擅自决定哪一位演员何时说话。对每个 Shot 调用 PR-10a 的预检：同一 Series 的版本化 Voice Asset、非空声音来源同意引用、逐字批准台词、时间预算；全部通过后才在本地生成音频。

逐镜头输出 48kHz/单声道/PCM WAV 原始合成正弦时间占位音，带 SHA256 和稳定指纹；主时间线按镜头顺序拼接 WAV 帧，并通过总帧数等于目标秒数、内容哈希 marker 验证。重复输入命中已验证缓存；破损文件会重建。镜头台词、声音资产版本和顺序影响最终 fingerprint。回执没有台词原文，且一直标记 `real_spoken_dialogue_generated=false`、`voice_consent_independently_verified=false`、`publish_approved=false`、`paid_provider_calls=0`。

新增 `offline_demo --seconds 60 --fake-voice-timeline`：通过项目/人物/声音/分镜/剧本/生产审核后，调用此逐镜头 Fake provider，得到完整 60 秒 WAV，再生成原创无授权风险的本地背景测试音，经真正的 FFmpeg 混音、H.264/AAC/`mov_text` 拼接和 QA。独立 GitHub Artifact `offline-one-minute-fake-voice-script-timeline` 保存 MP4 与 manifest（7 天）。另外有 6 秒强制 FFmpeg 集成测试以及普通 Python 的负面权限/缓存测试。

**仍未完成的部分：** 多角色多声音同一镜头、多句台词和时间戳精确对齐、真实语义朗读与声纹一致性、口型、真人配音合同校验、Google Gemini TTS 官方 API/成本及第三方授权。不得将此 Fake 时间线视为真实短剧成片或发行审批。
