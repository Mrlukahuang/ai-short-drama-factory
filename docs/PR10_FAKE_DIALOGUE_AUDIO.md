# PR-10a — 声音 Provider 离线合同、已审核台词约束和 FakeDialogueAudioProvider

此前 PR-15b/15c 已成功将本地 WAV 对白与配乐混入真实 60 秒技术 MP4，但未来真正 Gemini TTS 不能仅凭一个任意 WAV 路径就绕过版权/角色归属/审批。

**新的严格声音生成合同**：`DialogueGenerationSpec` 绑定 Series、Production、Shot、同一 Series 内版本化 Voice Asset、语言、准确的已审核台词以及不超过目标镜头时长的长度。生产 Run 必须已经通过剧本和角色双重审批；台词必须与同一个镜头的已批准 `EpisodeDraft.shots[].dialogue` 逐字相同。声音资产必须为 `kind=voice`、属于该 Series，并填写来源同意证据引用，且本次测试必须 `operator_confirmed_voice_rights=True`。这些只验证技术登记，不代替音色/形象/商用许可的法律审核。

`FakeDialogueAudioProvider.synthesize(...)` 使用纯 Python 标准库在本地输出可播放单声道、48kHz、16-bit PCM WAV。音频是可听见的正弦时间占位音，**绝不是语言对白/TTS/真人声纹**。根据已审核输入、声音资产版本/记录哈希、文本 SHA256 和长度生成稳定幂等 fingerprint；若同一文件的 WAV 或 SHA256 marker 损坏则安全重建，输入或声音版本变化重新命名/生成，不重新收费。输出收据 `real_spoken_dialogue_generated=false`、`voice_consent_independently_verified=false`、`publish_approved=false`、`paid_model_calls=0`，绝不返回台词明文。

`GeminiDialogueAudioProvider` 目前只保留一个**始终拒绝**的明确入口，不调用 Google SDK；真实 Gemini TTS 的当前模型、接口、地区、单音色权利、实际账单和供应商任务恢复仍需未来独立实测与付费控制。不能将 FakeAudioProvider 宣称为真实 TTS 已接入。

CI 实际覆盖跨 Series 声音资产拒绝、缺失来源同意、未审核生产、未批准台词、缺失镜头、过长镜头、声音版本/台词变化导致 fingerprint 变化、可播放 WAV 重用与损坏重建；强制 FFmpeg Job 再将 Fake Provider 输出 WAV 输入 PR-15b 的真实视频混音并通过 PR-14 QA。没有远端 SQL、Drive 或付费模型操作。
