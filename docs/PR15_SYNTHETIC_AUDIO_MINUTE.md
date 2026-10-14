# PR-15c — 可下载的 60 秒双音轨混音技术样片

在 PR-15b 的本地 WAV 输入、混音、音轨保留、完整成片 QA 基础上，新增 `python -m drama_factory.pipeline.offline_demo --seconds 60 --synthetic-audio-mix --out artifacts/offline-demo-60-mixed`。

该命令仍从 FastAPI 的 Story Bible/角色/场景/剧本审核/分镜/生产审批走完完整流程，并使用原来的**本地 FFmpeg 合成移动测试画面**和占位分镜；另外产生 **540Hz 人造对白时间占位音**和 **180Hz 人造背景音乐时间占位音**两条 PCM WAV，走 PR-15b 的真实两轨混音，按 0.16 倍衰减背景音并对单条 AAC 输出限幅，保留软字幕轨。实际没有说话的声音、演员授权素材、AI 画面或联网请求。

GitHub `offline-video` CI 另外实际生成、独立校验并上传 `offline-one-minute-two-tone-audio-mix` Artifact（7 天）：60 秒左右 H.264 9:16 竖屏 + AAC 混音 + `mov_text` 字幕；只有整片 `technical_qa` 的解码/字幕 SHA256/镜头完整性全通过，才允许保留技术预览 `offline_preview_finished`。结果 `spoken_dialogue_generated=false`、`voice_license_independently_verified=false`、`genuine_ai_video_verified=false`、`publish_approved=false`、`production_ready=false`、`paid_api_calls=0`。

GitHub CI 另外用 6 秒版本执行 E2E 测试，验证新开关必须是真正 boolean，不能偷偷将错误参数解释为真实音轨。旧默认 CLI 行为保持不变，原 60 秒普通技术样片也继续生成。

这一步验证了**两条本地音频 stem 确实可以与 60 秒剧情预览视频一起合成、上传并回检**。它不验证嘴型、语义台词、真人声音一致性或正式发行许可；真实 TTS 与视频生成仍未连接，不应称为 AI 短剧成片。
