# PR-10c｜多角色、多句台词的结构化配音时间线（离线测试音）

## 解决的问题

原来结构化 Screenplay 已有 `DialogueCue.speaker_actor_id`，但审核后存入 `EpisodeDraft` 时只有 `actor_id: text` 字符串；后续配音只能按“一镜头一行/单声线”处理。PR-10c 把有明确演员来源的有序 `dialogue_cues` 一同持久写入审核后的 ShotDraft，保持旧 `dialogue` 字符串供字幕等兼容读取；两者不一致、说话人不属于镜头演员表会直接拒绝。

## 执行合同

`build_fake_cast_dialogue_timeline(db, production_id, voice_assets_by_actor, output_root, operator_confirmed_voice_rights=True)` 严格核对：剧本和人物审批、同一 Series 的演员、各演员 `voice_asset_id` 与用户明确传入的映射一致、版本化声音来源同意记录、每镜头说话人和逐字批准台词、每句序号与秒数。这些操作全部发生在**写入本地 WAV 之前**。每镜头最多 8 行、每行至少占 1 个整秒（超过时长则拒绝，不能任意压缩真实 TTS）；同一镜头多行按均匀整秒拆分，保持既定台词顺序。无台词镜头写入等长静音；全片仅允许最多 12 镜头、90 秒。

不同演员及相同文本的重复台词必须产生不同可审核指纹；每句使用既有 PR-10a 48kHz 单声道 PCM **正弦测试音**，最后按镜头/台词顺序无损拼接为 1 条 WAV，保留 SHA256 marker 和损坏重建。新样例里 2 个演员在第一镜头轮流发言，第二镜头另一个人发言，第三镜头静音；配乐仍是本地原创合成背景测试音，再经 PR-15b FFmpeg 完整混音并通过 PR-14 视频/字幕技术 QA。

## 测试与边界

第四项强制 FFmpeg CI 包含真实 6 秒多演员分镜技术 MP4 测试，并产出可下载的 60 秒 `offline-one-minute-two-actor-fake-cues` 技术 Artifact（7 天）。普通 Python 测试覆盖 2 位演员说相同台词、声音串用、缺失/多余声音映射、未确认使用权、结构化台词被篡改、无声镜头真实 0 PCM、缓存损坏重建和不支持参数。

本方案只分配可计算的**整数秒测试音段**，不做自然语言朗读、音节/语速预测、真人声纹身份确认、口型同步或商用授权；`genuine_ai_video_verified=false`、`real_tts_generated=false`、`voice_consent_independently_verified=false`、`publish_approved=false`，没有联网、收费 Provider 或旧 TxLab 实验写入。**旧 v0.1 没有结构化说话人字段的 Episode 仍可正常预览，但不能凭字符串猜测说话人后自动进入多演员 FakeVoice。**
