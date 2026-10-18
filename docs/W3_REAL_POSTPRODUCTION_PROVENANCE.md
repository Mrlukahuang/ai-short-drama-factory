# G4/R4.4 W3 — 已有真实 12 镜的后期时间轴及来源收据

Stage: G4 / Req: R4.4 / Owner: M3 / W3.1 (P0).

## 重用而非重新开发

- `scripts/postprocess_gpt_episode_offline.py::render_draft_postprocess`：复用既有 DRAFT SRT、mov_text、H264/AAC stream-copy、全部音视频解码。
- `scripts/assemble_gpt_video_three.py::probe/sha`：既有每镜 FFprobe、媒体 SHA 与拼接输出检测。
- `drama_factory.pipeline.offline_qa._verify_muxed_subtitles`：逐 cue 实测 MP4 字幕和 SRT 对比。
- W1 单镜替换脚本及 W2 资产绑定**保持原样**。HyperFrames Apache-2.0 的 mediaTiming/renderRequest 只借验收维度；本仓库没有移植第三方源码。

## 数据契约与真实媒体操作

原始 12 镜（现有一切输出均独立新目录）：

```bash
python scripts/postprocess_gpt_episode_offline.py \
  --writer-dir artifacts/original-writer \
  --episode-dir artifacts/original-episode/episode \
  --delivery-dir artifacts/original-episode/delivery \
  --output-dir artifacts/draft-postproduction
```

对**已由 W1 生成**的 FAKE 修镜版本另做 W3.1 严格父版本校验：

```bash
python scripts/postprocess_gpt_episode_offline.py \
  --writer-dir artifacts/original-writer \
  --episode-dir artifacts/w1-offline-simulation/repair/episode \
  --delivery-dir artifacts/w1-offline-simulation/repair/delivery \
  --parent-episode-dir artifacts/original-episode/episode \
  --parent-delivery-dir artifacts/original-episode/delivery \
  --output-dir artifacts/w3-repaired-provenance
```

两种输入都复用原 Writer 的固定 Sol 回执 SHA `c5665e198eb3d30110a0bb6dc30d5f2cfadf74979eb5e6e0596d64751ff1a6f9`。绝不重新请求 Writer/Omni。**对于修镜版本，只有同时提供父 episode + 父 delivery，`parent_source_crosschecked` 才能为 true；不能仅凭当前 report 里的 SHA 字符串断言父素材已逐字节核实。**

新增 `09_render.json` 版本 `g4-w3-render-provenance.v1`：
- 12 个按顺序 ffprobe 实测 `start_ms/end_ms/duration_ms`，以及每镜源视频 SHA、从实测长度推算的 DRAFT 字幕轨；
- 已读取源 report SHA、delivery manifest SHA、原 preview SHA、固定 screenplay response SHA；
- 如有 W1 修镜：s07 旧/新 SHA、旧镜收据摘要、是否以父 report、全部12镜及父 MP4 字节交叉核实；
- 最终 MP4 SHA、SRT SHA、FFmpeg remux route/config 和音轨保留方式；
- `asset_manifest_sha256=null`、`production_assets_verified=false`、`prompt_anchor_only`：这条旧片没有 W2 真实生产资产 Manifest 锁定证据。

`10_qa.json` 附 `render_receipt_sha256`（即 **独立输出** 09_render.json 文件字节的 SHA256）。旧 MP4、原 JSON、W1 receipt 只读，输出存在/父来源错/11镜源变更/错误哈希时拒绝并保留旧版本。时间轴和 SRT 是基于实测 clip 时长与剧本估算，**不等于 ASR/真实中文对白匹配**。

## W3.2/W3.3 范围裁决

- W3.2：本任务未收到任何本地获合法授权 WAV 及其许可证据，故**不启用**本地配乐、不改 `offline_audio.mix_local_stems` 通用 helper；默认保留现有 AAC stream copy。现有 helper 使用整数秒 `-t`，未经进一步专项验证不得直接用于约 60.177s 原片以免裁尾。未来单独提供已获授权音乐后，才可批准小增量；任何混音都须使用已有 Omni 声轨为原声并标 `audio_reencoded=true`，不得把外部 dialogue WAV 覆盖原片。
- W3.3：没有可实证锁定的 W2 production asset manifest，不构造、不猜测、不强行关联。只有后续真实版本产出并可验后才能增列真实 SHA。

## QA 与批准范围

按工作流 `.github/workflows/gpt-episode-postprocess-offline.yml`（原有 workflow）再次只读下载 Run39035812309 的 Writer 与 Run39130058487 的真实媒体；独立生成原版、W1 Fake 后版两份 MP4/SRT/receipt，上传本次 GitHub Run Artifacts。Run/Artifact/最终 SHA **以当次成功回执为准**，不得在 CI 尚未完成时抄旧版本数字。

技术通过不提升 `dialogue_content_verified`、`subtitle_alignment_verified`、`visual_quality_verified`、`publish_approved`、`full_episode_complete`。原始历史真实 Omni 账单仍需人工核；本次新模型 API 调用=0、本次新增费用USD0。W4（Stage G4/Req R4.3）消费每镜 SHA/时间轴、DRAFT SRT 和旧版/FAKE 来源，开展逐镜人物、声线、字幕/对白与人审，不提前开启 G5。
