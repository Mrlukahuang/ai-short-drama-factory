# 可借鉴的开源项目（2026-10-15 核查）

> 动手实现任何环节之前先看这里。许可证决定能否借代码：
> - **MIT / Apache-2.0**：可借鉴代码，保留原版权声明，在 PR 里注明来源文件。
> - **CC BY-NC / Elastic / 专有模型许可**：**只借思路，不复制代码**（本项目可能商用）。
> - 星数和许可证会变，借代码前重新核实 LICENSE 文件。

## 1. 全链路短剧项目（按与我们的相似度排序）

| 项目 | 星数 | 许可 | 技术栈 | 值得借的 | 对应阶段 |
|---|---|---|---|---|---|
| [HKUDS/ViMax](https://github.com/HKUDS/ViMax) | 12.6k | **MIT** | Python 3.12 | Idea2Video / Script2Video / **Novel2Video**；参考图与首帧编排、镜头相机连续性、并行生成；已接 Google Omni、Seedance 2.0 Fast | G1–G4、G6（**首选参考**） |
| [Forget-C/Jellyfish](https://github.com/Forget-C/Jellyfish) | ~6k | **Apache-2.0** | FastAPI + React + MySQL/Redis | 镜头工作台：章节→拆镜→抽取人物/场景/道具/服装→逐镜准备→批量生成；统一异步任务中心 | G2–G4 UI 与任务模型 |
| [chatfire-AI/huobao-drama](https://github.com/chatfire-AI/huobao-drama) | 15.8k | CC BY-NC-SA（**禁商用**） | Hono + Nuxt + SQLite | `@character` 引用自动映射参考图；批量生成前的费用确认弹窗；一键重试 | 只借思路：G2 参考注入、G4 确认流程 |
| Toonflow-app (HBAI-Ltd，GitHub 搜索) | ~15k | 待核实 | — | 小说→动画短剧、画布式剧本/制作 Agent | G6 思路 |
| [waooAI/waoowaoo](https://github.com/waooAI/waoowaoo) | 13.4k | Elastic 2.0（只借思路） | Next.js + **Temporal** + MinIO | 用 Temporal 做 durable execution（崩溃恢复、幂等）——**正是 PR31 手写的东西** | G5 评估 |
| ArcReel | ~4k | 待核实 | — | 小说→资产→分镜→视频→剪辑草稿，**带成本追踪** | G4 成本面板 |
| [drasstry/shortdrama-pipeline](https://github.com/drasstry/shortdrama-pipeline) | ~100 | 待核实 | Python | 中文短剧后端流水线（已在 README 中作为架构参考） | — |

## 2. 编剧 / 分镜 Skills

| 项目 | 许可 | 借什么 |
|---|---|---|
| [zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills) | MIT（PR-03 已审） | 分层：人物→大纲→分集→分镜，独立审核步骤 |
| shuohao-skills (eternityspring) | 待核实 | 短剧钩子、反转、结尾悬念的提示结构 |
| worldwonderer/drama-skills、OnlyShot | 待核实 | Claude Code 用的五步短剧 Skill |

用于 **G4 R4.2**。

## 3. 声音

| 项目 | 许可 | 说明 |
|---|---|---|
| [index-tts/index-tts](https://github.com/index-tts/index-tts)（IndexTTS-2.5，2026-08） | bilibili 模型许可，**商用需联系** | 零样本克隆、情绪控制、语速控制、拼音纠音；中文最强开源之一 |
| CosyVoice 3 | 待核实 | 阿里开源多语种 TTS |
| [TTS-Audio-Suite](https://github.com/diodiogod/TTS-Audio-Suite) | 待核实 | ComfyUI 多引擎 TTS 节点，适合本地对比 |

仅在 G1 选择音频路线 B 时使用；默认先用 Gemini 3.8 TTS。

## 4. 口型同步（音频路线 B 才需要）

| 模型 | 说明 |
|---|---|
| **LatentSync 1.6** | 对已有视频替换口型的首选基线 |
| KeySync | 最接近的备选 |
| MuseTalk | 速度优先的备选（权重许可需单独核实） |

注意：公开评测都不是中文，G1 必须用中文镜头实测。

## 5. 合成 / 剪辑

| 项目 | 说明 |
|---|---|
| FFmpeg（现有） | 继续作为主力 |
| [Remotion](https://github.com/remotion-dev/remotion) | 进阶字幕动效、模板化片头（注意其公司许可条款） |
| heygen-com/HyperFrames | 用 HTML 写视频，Agent 友好 |

## 6. 可视化导演界面（G4 之后才考虑）

- [storytold/artcraft](https://github.com/storytold/artcraft)：已有对照报告 `docs/ARTCRAFT_BENCHMARK_2026_10_13.md`
- Jellyfish 前端、open-ai-canvas、open-storyboard-canvas

## 7. 借鉴登记

借了代码的在这里登记：

| 日期 | 来源仓库@commit | 来源文件 | 我们的文件 | 许可 |
|---|---|---|---|---|
| — | — | — | — | — |
