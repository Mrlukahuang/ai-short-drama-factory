# Google Video / Image / Audio: baseline evaluation, 2026-10-12

> 这是公开接口能力评估，而不是本团队完成的质量盲测报告。模型接入暂未启用，不会产生 API 费用。

## Google 当前建议

| 模态 | 优先模型 | 原因 | 注意事项 |
|---|---|---|---|
| 视频默认 | `gemini-omni-1.1-flash` | 2026-08-27 GA、3–10秒、9:16、原生音频、视频编辑及延长 | 中文对白/口型尚未实测；已有音色不能直接在视频里编辑 |
| 视频旧接口 | `veo-3.1-fast-generate-preview` | 首尾帧、电影控制及原生音频 | **2026-10-22 停服，禁止新生产依赖** |
| 虚拟演员资产 | `gemini-nano-banana-2.1` | 最高 14 张参考图、最多 4 角色相似度支持 | 身份一致性仍需多场景 A/B 检验 |
| 固定演员音色 | `gemini-3.8-flash-tts` | 支持持久声音角色、中文、多角色表演风格 | 需要对声音 ID、授权、台词音频版本建档 |
| 批量旁白 | `gemini-3.8-flash-lite-tts` | 低成本、大规模 | 情绪饱满度与主力 TTS 盲测对比 |
| 配乐 | `lyria-3.5` | 音乐生成，适合片头配乐候选 | 商用条款和风格一致性检查 |
| 小说理解 | `gemini-3.8-flash` 或其他长文本模型 | 用于章节事件/人物关系/冲突/季度规划 | 先本地分块索引，按章处理，不要每集重复发送整书 |

## 价格与成本注意

- Omni 1.1 720p 官方输出 token 折算约 USD 0.10 / 秒，不是固定按秒计价：具体总额还包括所有输入及模型消耗。
- 官方展示 Veo Fast 720p USD 0.10 / 秒、Veo Lite USD 0.05 / 秒，但停服期限使它们无法作为新业务长期依赖。
- Gemini 3.8 Flash TTS 输出约 USD 0.00225 / 10 秒音频，Lite 约 USD 0.0015 / 10 秒（截至 2026 年底促销期）。
- Lyria 3.5 公开报价 USD 0.08 / 首；音乐长度和创作效果按模型实际响应决定。
- 将 `360p` 预览放入后续适配层，先选定适合镜头后再升分辨率，避免每一版都高分辨率生成。

## 四类对照镜头，每家同条件

1. **双人争执**：两位虚构主演同框，一人 6 秒中文台词，另一人表情和视线不漂移。
2. **反打连贯**：前一镜头客厅近景，下一镜头同服装同人物反打，不得改变脸型或场景道具。
3. **微表情**：女主 6 秒由克制到流泪，眼睛、鼻翼和面部纹理自然。
4. **动作互动**：男主递手机，女主接住，手部接触、手机朝向和动作路径连贯。

每个镜头对 Omni 1.1 / Seedance 2.5 / Kling 3.0 Omni 用相同的主演参考图、同样的时长目标、相同次数上限。按照匿名视频编号打分：主演一致性 30%、中文对白口型 25%、动作空间连续性 20%、画质 15%、实际合格镜头成本 10%。保留原始 prompt、模型版本、原始 MP4、API 响应、费用及人工审查结论。不要用单个 demo 决定所有镜头的模型路由。

## 当前不能贸然假设的能力

- Omni 的原生视频音频与 Gemini TTS 固定音色，并不天然保证同一个演员声音无缝一致；如果独立 TTS 配音，需要专门解决同步问题。
- Gemini Omni 1.1 的声音编辑与上传外部声音作为参考目前受限。
- `1080p` / `4K` 在 Omni 1.1 属于 upscale 输出，不意味着原始生成具备对应的物理细节。
- 社区反馈同时有角色一致性改进与真实感不足的意见，不能直接认定 Google 一定强于 Seedance/Kling。
- Google AI Studio、Gemini App、Flow 的订阅额度不应误算为可供 Python 批量调用的免费 API。

## 官方证据

- https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash
- https://ai.google.dev/gemini-api/docs/omni
- https://ai.google.dev/gemini-api/docs/deprecations/
- https://ai.google.dev/gemini-api/docs/changelog
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts
- https://ai.google.dev/gemini-api/docs/models/lyria-3.5
