# PR-10h — Gemini TTS 本地逐句回执落库二次字节核验

## 不信任上游的校验声明

PR-10g 建立有审核和三级预算的本地逐句 TTS 任务，`record_offline_verified_tts_wav` 接收 `InspectedGeminiSpeech` 元数据。但该 Python dataclass 可由任意代码直接构造，即使其 SHA256 与文件内容相等，也**不表示已经独立解码为合法 24kHz、单声道、16-bit PCM、导演批准时长内的 WAV**。

PR-10h 在最终 SQLite 元数据写入事务前对传入的 **原始 WAV bytes 再次调用受控校验器**，检查 Base64 严格内容、RIFF PCM 格式、24kHz 采样率、声道数、帧数、实际解码时长、该镜头已批准的最大秒数；并要求检验得到的 SHA256 与时长均与预先传入的结果一致。损坏、采样错误、长度伪造、用真实 WAV 冒充错误播放秒数等，全部拒绝，保留已有任务为 `acknowledged`，不会生成 `verified` 记录或额外提交费用。

## 跨 Cue 防重复供应商回执

`acknowledge_tts_provider_interaction` 在一个 `BEGIN IMMEDIATE` SQLite 事务内查找已有的相同 Provider/Interaction ID，若已绑定到其他 Cue，就产生固定、脱敏的拒绝错误。数据库仍有 UNIQUE INDEX 作最后一道防线。没有自动重新提交模型、没有释放已锁预算。用户原文、API 响应、Google 凭据或未审核声音不进入 GitHub 日志。

## 回归与边界

新 CI Fake 测试故意直接构造伪造的 `InspectedGeminiSpeech`：非 WAV 数据但正确 SHA、8kHz 错格式、超出已批准时槽的 WAV、实际 0.75 秒却填写 0.66 秒；均必须禁止落库。两个有分别批准声音资产的演员共享同一个伪供应商 Interaction ID 时，第二个不得绑定；使用独立 ID 后正常登记。正常通过的 24k PCM 模拟内容只存哈希和时长，`publish_approved=false`。

**本 PR 不调用 Google、不重复已消耗的单句付费 TTS、不读取用户小说或声纹，也不对生产 Turso 执行任何写入。** 这里保证技术格式和引用唯一性，仍不保证真人听感、供应商账单准确或商业授权许可。
