# G4/R4.4｜真实12镜成片人工画面审查（2026-10-19 NZT）

> Scope: **已有成片的只读、离线审查**。不生成/重生成视频、不调用模型、不改密钥、不发布、不改变资产/音频策略。Stage: G4 / Req: R4.4。

## 1. 证据与结论

- 主视频成功 Run: https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39130058487 ，`video3` job conclusion=`success`，执行 SHA `8bf859bf81f9ef7edbe056b0d0283c82fdc51503`（PR #157）。
- 复用原 s01–s03；新生成 s04–s12 共 9 镜；12 镜进入 FFmpeg 原音轨无转码拼接。
- 用户提供的完整 MP4 的 SHA256 为 `f76daf3065796ef847500041648f5dadb1cffa98898c466f11ac3471be9e8887`，与前次交接记录相同。
- ffprobe：60.177333 s 封装总时长，360×640，H.264/AAC，存在音轨；技术链路通过。**技术通过不是内容通过**。
- 真实供应商最终费用未核实；原预算 USD4.27173825 是估算，USD5 为一次风险确认额，非硬上限。一次性生成批准已经用过，严禁将其视为后续重试授权。
- 本轮 **0 新 API 调用/0 新视频生成**。可发布状态：**未通过/待人工音频与内容校验**。G4 阶段未退出，不进入 G5。

## 2. 画面问题（对用户提供的原始视频分别抽取每镜头 0.5/2.5/4.5 秒画面）

| 等级 | 镜头/大致时点 | 可复核观察 | 影响 |
|---|---|---|---|
| P0 | s03（10–15s）、s09（40–45s） vs s04/05/11/12 | 绿围裙男角色的脸型、头发年龄感明显分化；s03 甚至有灰发及胡须，而后续出现年轻形象 | 同一角色身份失守，优先处理 |
| P0 | s07（30–35s） | 5 秒镜头生成三格上下分屏，与前后单镜式叙事不一致 | 镜头指令/成片内容冲突 |
| P1 | 全片 | 女角色头发/面部细节与相对比例多次变化；杯子大小、外观、图案有跨镜变化 | 角色/道具连续性不足 |
| P1 | s03/04/06 等 | 画面里零星出现人名标签/似中文文字，非稳定对白字幕 | 提示词的“无文字叠加”未获得成片端验证 |

**声音审查边界**：AAC 音轨确实存在且能解码；本次仅离线核查音轨存在、时长、幅度，**没有完成可靠的中文 ASR/逐句对照或完整主观试听**。用户明确反馈配音不合格，应作为待复核的 P0 质量阻断，而非宣称已独立测得具体错词/错声/口型。

## 3. 现行真实生成路径的代码证据与结构缺口

1. `scripts/run_gpt_video_three.py::load_plan` 从原 Sol response + `case_inputs("misunderstanding")` 构造请求；`scripts/prepare_writer_comparison.py::case_inputs` 的 `characters` 仅为短的服装/性格描述（阿杰：森林绿围裙、米色上衣；小雨：淡黄外套），并无稳定的发色/脸型/五官等定妆要素。
2. `src/drama_factory/pipeline/screenplay_video_plan.py::build_screenplay_video_plan` 每镜头注入的是 `context.story_bible_json["characters"]` 文本，`config/style_presets/felt_diorama.json` 只使用 `style_prompt` 而非该文件更完整的 `characters`/ `consistency_rule`。其 `production_assets_verified=False` 明示尚未通过生产资产绑定。
3. `scripts/run_gpt_video_three.py::run_live` 每镜头创建 `OmniVideoSpec(prompt=..., min_duration_seconds=3, ...)`。实际 `src/drama_factory/providers/google_omni_video.py::generate` 仅以 `input=spec.prompt` 发送独立视频请求；当前适配器明确未实现参考图输入，并拒绝音频参考。**没有同脸 reference-image / 同音色 reference-audio 的真实跨镜绑定**。
4. 该提示词虽含镜头 `dialogue`，视频原生音轨却由各次独立生成决定；没有逐演员音色标识的真实注入、实录转写对照、口型/字幕人工验收。不能把音轨存在等同对白正确。
5. `scripts/complete_gpt_episode.py` 复用3镜/生成9镜，再调用 `scripts/assemble_gpt_video_three.py` 顺序 stream-copy；其 QA 只确认媒体格式、hash、时长、解码，`subtitle_alignment_verified=False`、`dialogue_content_verified=False`、`full_episode_complete=False`。没有 R4.3 的相邻镜头真实视觉预检接入此流程。
6. 完整11步 Fake P 链已搭建，但本次真实 Run **不是**将 Fake 的角色审批、资产版本、对白、字幕、配乐、内容 QA 全链依次落地；它是“GPT 剧本→逐镜 Omni→拼接”的最小真实路径。勿混写 Fake 与实际生产能力。

## 4. 无额外费用的修复优先级

1. **P0 先规范角色圣经与跨镜资产锚点（离线）**：统一阿杰/小雨每个镜头完全相同的身份、年龄感、发色、发型、脸型、服装、声音特征描述，明确出场清单；复用已有 `felt_diorama` 风格资料，禁止同一角色来自两套互相矛盾的文字定义。编剧/分镜预检按角色 ID 比对和阻断不完整外观定义；只产出请求预览与测试，无收费生成。
2. **P0 先建立声音验收标准（离线）**：要求逐镜保留 speaker_id、期待台词、预计时间段；补**审片所需**的“实际音轨→ASR（后续需能力/费用授权）→脚本比较”设计与人工试听表。先评估模型原生语音 A 路线可否通过稳定音色提示词/实测；若不行才提议由所有者决策 TTS+口型路线 B。不得自行修改冻结的 `jobs/tts_*`。
3. **P1 加入真实逐镜内容 QA 门禁**：外观/声线/台词/文字噪声/镜头语言/道具接续逐镜判定；失败只标记镜头，不自动重跑；支持原片、末帧与相邻镜头的审片对照。R4.3 自动评分是后续增强，不能在当前无证据时冒称实现。
4. **P1 参考图能力先查适配器/供应商支持再选实现**：当前 Omni provider 没有参考图入参。先做不收费的协议能力核查与精准接线方案；不能假定文字强化必能解决同脸。
5. **P2 仅在所有者按金额授权后做 2–3 镜的小范围质量复验**：验证年龄/脸型、同声/中文发音、对白与动作、画面文字；通过门禁再扩大范围。不能借本次一次性 USD5 授权或 Actions rerun 生成。
6. 本轮先**不**做云存储、UI、数据库改造、整集重生成、全面模型切换或 G5。优先复用已有代码，按 G4 / 单 Req / 小 PR 规则推进。

## 5. 状态判定

- `technical_preview_passed_pending_human_review`: 是（技术）
- `all_script_shots_assembled`: 是（12镜）
- `g4_duration_range_passed`: 是（60.177333s）
- `visual_character_consistency`: 失败（至少 s03/s09 相比其他镜头）
- `voice_consistency_verified`: 否（用户报告不合格，独立语音审查未完成）
- `dialogue_content_verified`: 否
- `subtitle_alignment_verified`: 否
- `publish_approved`: 否
- `G4_exited`: 否

本报告仅存文字观察与引用，不提交媒体文件、密钥或个人素材。
