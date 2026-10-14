# 模型现状（核查日期 2026-10-15）

> 每月核查一次，或在 G 阶段切换前核查。价格是第三方市场观测值，以官方账单为准。
> 机器可读版本：`config/model_registry.json`。

## 视频（G1 盲测对象）

| 模型 | 状态 | 时长 | 音频 | 参考/一致性 | 约价（720p） | G1 |
|---|---|---|---|---|---|---|
| `gemini-omni-1.1-flash` | GA 2026-08-27 | 3–10s | 原生音频；**不支持上传音频参考** | 图像参考、编辑、延长、首尾帧 | ~$0.10–0.11/s | ✅ 测 |
| Seedance 2.5（字节） | 发布 2026-07-31 | ≤30s | 原生音频；可输入音频 | 参考编辑增强 | ~$0.23/s | ✅ 测 |
| Kling 3.0 Omni（快手） | 可用 | ≤15s | 原生音频 | Omni 参考 | ~$0.112/s | ✅ 测 |
| **Kling 4.0 / 4.0 Flash** | **2026-10 发布中**（Flash 内测） | ≤30s（Flash ≤20s） | 立体声；**主体可绑定音色**；中文、粤语、川话 | 15 个参考（10 图 + 5 视频），7 个主体，10 关键帧 | 未公布 | ⏳ 上线即加入 |
| MiniMax H3 | 2026-07-31，开放权重 | ≤15s | 原生立体声 | 统一多模态上下文 | — | 备选 |
| LTX-2.5（Lightricks） | 2026-08-11，开放权重 | — | 音频驱动视频端点 | — | 本地 | 本地草稿备选 |
| Seedance 2.0 Fast / Mini | 可用 | ≤15s | 有 | 有 | ~$0.04–0.12/s | 低成本草稿 |
| `veo-3.1-*-preview` | **2026-10-22 停用** | — | — | — | — | ❌ |
| Sora 2 | **API 已于 2026-09-24 关停** | — | — | — | — | ❌ |

**关键问题**：Omni 无法上传音频参考 → 跨镜头声音一致性无法由模型保证。Kling 4.0 / Seedance 2.5 若能绑定音色，可省掉单独 TTS + 口型同步链路。这是 G1 要回答的核心问题。

## 图像

| 模型 | 状态 | 用途 |
|---|---|---|
| `gemini-nano-banana-2.1` | GA 2026-10-06 | 定妆照、多参考一致性（默认） |
| `gemini-3.1-flash-image` | 已弃用 | ❌ 迁移到 2.1 |
| GPT Image 2 | 可用 | 备选 |

## 声音

| 模型 | 状态 | 用途 |
|---|---|---|
| `gemini-3.8-flash-tts` | GA 2026-09-22 | 路线 B 默认 TTS |
| `gemini-3.8-flash-lite-tts` | GA 2026-09-22 | 便宜档（PR-10f 已真实调用过一次） |
| `gemini-3.5-transcribe` | GA 2026-08-26 | **新用途**：转写生成视频的实际台词，自动比对剧本、对齐字幕 |
| `lyria-3.5` | GA 2026-09-03 | 配乐 |

## 文本

| 模型 | 用途 |
|---|---|
| Claude Sonnet 5.5 | 编剧主模型（G4） |
| `gemini-3.8-flash` | 长篇小说事件抽取（G6） |
| `gemini-4-argon` | GA 2026-10-13，复杂推理，可做剧本结构审稿备选 |
| `gemini-3.7-flash` / `gemini-3.5-flash` | **2026-10-08 弃用**，不得使用 |

## 来源

- [Gemini API release notes](https://ai.google.dev/gemini-api/docs/changelog)
- [AI video model release tracker 2026](https://magichour.ai/blog/ai-video-model-release-tracker-2026)
- [Kling 4.0 (fal)](https://fal.ai/learn/tools/what-is-kling-4-0)、[Kling 4.0 (Runware)](https://runware.ai/kling-4)
- [Seedance release status & pricing (2026-10-04)](https://apimaster.ai/blog/seedance-3-0-api)
