# 当前交接状态（2026-10-19 NZT）

## 持久开发 Bible（2026-10-19，G4/R4.4 技术实施指南）

- [开发 Bible 总入口](../DEVELOPMENT_BIBLE.md)：架构、正式 G0–G7 与可交付 W0–W8 的边界、现有真实代码/Artifact 复用原则。
- [成熟开源复用](../development_bible/OPEN_SOURCE_REUSE.md)：OpenMontage/HyperFrames/ViMax/Jellyfish 固定 commit、源码路径、许可与最小移植检查表。
- [阶段交付与验收](../development_bible/STAGE_DELIVERABLES.md)、[多模型无损交接](../development_bible/MODEL_HANDOFF.md)：不同模型换聊天前必须使用统一证据包与明确文件 Owner。
- **本段仅指向技术实施规范，不重排本文件现有“单一下一任务”，不授权 G5/付费模型/冻结区或治理变更。**

## 当前权威状态：W1 零费用端到端验收通过（2026-10-19 NZT）

**Stage: G4 / Req: R4.4 / W1**。开发 Bible `main@ac28e5d` 后实现 W1，#166 与 #167 已合并；核实后的代码主干为 `1792fb387ac907d3da808348128eddce5924f793`。**W1 的 0-call/Fake 部分已用真实旧12镜素材通过，独立付费单镜生成仍禁用且尚未验收。G4 未退出，G5 禁止。**

- [Run39137352545](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39137352545) 全部步骤 success；W1-FAKE Artifact ID `12140422056`，字幕 DRAFT Artifact ID `12140556405`。使用已存在真实 `s04` **仅模拟**替换失败 `s07`，其余11镜 SHA 不变，旧整集 MP4 SHA `f76daf3065796ef847500041648f5dadb1cffa98898c466f11ac3471be9e8887` 不变；新回填+后期 MP4 SHA `de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f`。
- 自治 Scope/Tests 全绿；媒体技术 QA 通过，内容/声线/对白/字幕实际对齐及发布均未通过；**新供应商视频调用0、新 API 费用USD0**。先前一次 USD5 claim 不可再用、真实账单未知。
- W1 标准机器可读 handoff 与下一包输入输出见 [W1_EVIDENCE_20261019.md](W1_EVIDENCE_20261019.md)。
- **下一唯一开发包：W2**（仍 G4/R4.4），按 Bible 开发人物/场景/说话者逐镜资产版本与 Prompt 锚定的离线契约；其输入为 W1 的原视频/剧本 SHA、per-shot repair plan、source receipts 与11镜 SHA，不触碰 W1/后期/合成所有权范围；输出必须确定性、冲突 ID/版本 fail-closed，模型参考图/音频不能谎称已经支持。
- W1 真正单镜有偿请求继续作为**阻塞的后续独立审批任务**：须可证实供应商成本保护、当日支出、新的一次性授权/任务接收回执；本次 W1 Fake 成功不等于收费分支获准。

## 早期施工记录（历史，非当前下一任务）

## 新 Development Bible / W1 当前施工（2026-10-19）

- main 起点 `ac28e5dff9c9ff7035881a4ef2e07f231cc35abf`，PR #165 已合并；Stage **G4** / Req **R4.4** / W1，按 `docs/development_bible/STAGE_DELIVERABLES.md` 的单镜定向修复零付费合同优先。
- 本轮新 `scripts/w1_single_shot_repair.py` 是薄适配：原剧本固定校验 + 单个 failed shot 计划 + 独立收费未批准状态 + 已有本地 Fake 镜头接收 + 复用 `repair_gpt_episode_offline.py` 单镜回填 + `postprocess_gpt_episode_offline.py` 草稿字幕、原生音轨与技术 QA。
- `scripts/repair_gpt_episode_offline.py` 仅加历史 `prior_shot_receipt`，保留被替换片原 Prompt/任务/账单；不修改其它11镜、原媒体或已用 USD5 claim。
- 现有 `gpt-episode-postprocess-offline.yml` 增加一个**明确标记 W1-FAKE** 的只读真实12镜离线回填演练：使用真实旧 s04 模拟 s07 的替代**绝非真实质量修复**。不能冒称新供应商请求完成。
- 验收以本轮 PR 实际 CI、真实 Artifact 成功记录为准；当前不宣称已通过直至工具证实。本轮 **0 新模型调用/费用USD0**。
- 详细 I/O、回滚和 W2 输入输出/禁止重复开发见 [W1_SINGLE_SHOT_REPAIR.md](../W1_SINGLE_SHOT_REPAIR.md)。
- **单一下一任务（待 W1 验收后）**：W2 角色/场景/对话的生产资产 ID/version/固定锚点离线契约，G4/R4.4；禁止动 W1 修镜/现有后期、冻结区和付费生成。W1 后续真实单镜付费生产仍需要独立可核实授权与供应商成本上限评估，未获则保持关闭。

## Stage / Req / 当前交付

Stage: G4 / Req: R4.4。真实 12 镜链路已成功生成+拼接，但用户审片认为人物与配音不合格。**不得把技术通过视为内容通过或 G4 退出。** 仍在 G4，不启动 G5。

## 当前可核实的真实证据

- main 最后由 GitHub PR #157 合并确认 `8bf859bf81f9ef7edbe056b0d0283c82fdc51503`；实际生产 Run [39130058487](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39130058487) 的 `video3` job 为 `success`。
- 12 镜：s01–s03 复用 Run39047208593，s04–s12 新生成 9 镜；原始文本来源 Sol Run39035812309；成片总长 60.177333 秒、360×640 H264/AAC，哈希 `f76daf3065796ef847500041648f5dadb1cffa98898c466f11ac3471be9e8887`，解码通过。
- 最终标记 `technical_preview_passed_pending_human_review`；`all_script_shots_assembled=true`、`g4_duration_range_passed=true`，但 `full_episode_complete=false`、`publish_approved=false`、`dialogue_content_verified=false`、`subtitle_alignment_verified=false`。
- 本次9镜估算 USD4.27173825、一次 USD5 风险确认**已消费**，供应商实际账单仍未知；绝不作为重新执行/重试许可。#158 原批准请求尚需留档收尾；#137 的 F3 原费仍待核。
- 已根据用户实际上传的原版 MP4 逐镜抽取 0.5/2.5/4.5 秒画面。**人物一致性失败**：s03/s09 灰发年长男与 s04/s05/s11/s12 年轻男变化；s07 三格分屏；画面文字/道具不稳。音轨技术存在，但未完成可信语音转写及音色逐镜试听，用户明确报告配音不合格。
- 详细根因与分级见 [GPT_EPISODE_VISUAL_REVIEW_20261019.md](../GPT_EPISODE_VISUAL_REVIEW_20261019.md)。真实路径是 Sol screenplay→prompt-only Omni 独立生成→FFmpeg concat；没有把完整 P/Fake 11步资产/声音/字幕/内容 QA 路径真实打通。
- 原有 Google 文本 Flash400 未修，不阻塞当前 GPT 基线；Sol/Luna/Flash 18 任务盲测尚未执行完整。临时编剧 Sol，不宣称正式主备已定。

## 最新真实后期重放结果（2026-10-19 NZT）

- PR #160 合并 `5212885207c7359f378f298a116edcfa7c77f9b2`：已完成12镜**单镜已有替换视频**离线回填、11镜原文件哈希保持和FFmpeg重拼接/解码。不是付费模型单镜重生成。
- PR #161 合并 `a7f32422add126ab734d5ed3b7043aa4396db3d6`：真实12镜+原 Sol 剧本进入离线 06–10 后期；草稿 SRT/原 H264/AAC 透传/mov_text 封装与 QA；主干自动跑真实 artifact 工作流。
- PR #162 合并 `e594cb8ffa1143e9b369dba47fa4f994ddfc7145`：仅修 Actions `GITHUB_PATH` 延迟生效造成的初次离线任务FFmpeg找不到（首次 Run39133331156 failed before postprocess；没有调用视频模型）。
- **最新真实成功 Run：[39133557599](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39133557599)**，job `postproduce-real` success。读取原文本 Run39035812309 和已成功12镜 Run39130058487，Artifact `12138992023` 名 `gpt-real-12shot-caption-DRAFT-39133557599`（约6.02MB压缩）；真实原始镜头没有重新生成；本次 API 模型调用0、模型费用USD0。
- 此新 MP4 的字幕是**按剧本与真实片段时长估算**并已验证嵌入，不是 ASR 转写/口型或字词对齐验收；原生 AAC 音轨保留，`08_music` 记录 native 透传，**没有单独新音乐**；人物、音色、内容、费用核对及发布审批仍未通过。
- 给所有者的进度估算：最短真实生产到技术后期的链路已通过，G4 MVP **约85%（剩约15%，工程估算非验收百分比）**；G4 尚未正式退出，G5 未启动。

**单一下一任务（仍优先全链路可用性）**：整理真实单镜付费修复的最小授权/失败镜头衔接与可重复交付验收；以现有12镜产物为基线，先做离线流程，费用授权和任何新视频生成必须另外明确批准。内容精修/模型切换延后，但正式 G4 退出仍需符合质量、实际账单及人工审批标准。

## 当前执行方向（所有者 2026-10-19 再次明确）

**优先把生产流水线跑顺，而不是现在精修人物、音色或剧情。** 本轮 Stage: G4 / Req: R4.4 追加一项不收费的真实视频后期能力：使用已有外部 MP4 对完整12镜中的指定一镜进行离线替换，只重拼接、校验，不重生成11个其它镜头。新增脚本 `scripts/repair_gpt_episode_offline.py`、离线真实 FFmpeg 合成测试及 `docs/GPT_EPISODE_COMPLETION.md` 使用说明。生成与真实质量审核仍未因此通过。

**单一下一步**：在此 PR 绿灯合并后，继续打通**真实生成视频到后期**的最短路径（剧本对应的字幕草稿、可选配乐与版本化输出），保留原生中文音轨和严格区分“推定字幕”和“经过转写验证”的标记；先复用已有真实视频离线测通，严禁新增收费调用或冒称内容验收通过。

评估给所有者的进度：最短 Sol/GPT→12镜Omni→FFmpeg→技术QA已经真实成功；G4全流程约75%（主观工程估算，不是自动化量化验收），剩25%主要是完整真实后期接线、单镜实际生成/修复的收费授权衔接、内容/费用最终验收。G4未正式退出。

## 本轮继续接线：真实整集离线后期（G4/R4.4）

在已经成功的 12 镜真实 MP4 + 已验证 Sol 剧本上，不重新生成视频：
- `scripts/postprocess_gpt_episode_offline.py` 新增已完成源素材哈希核对、现有原生音轨 stream copy、按原剧本与实际镜头时长换算的**估算字幕**、SRT→MP4 mov_text 封装与实际 mux 字幕逐字对照、完整媒体解码、`06_dialogue`–`10_qa` 五项落地 JSON。
- **明确没有 ASR、原声音色检验或新增配乐**；单独 `08_music` 只记载 native-audio 透传，字幕虽能入 MP4 也仍需逐字/对齐审查；不宣称 G4 退出、发布或 11 步所有质量门禁满足。
- 使用仓库原视频/文字 artifact 的离线新目录验收；测试用 FFmpeg 合成12镜，零新的模型调用/费用、零密钥。
- 继续采用用户的“先跑通全链路，后调演员及配音”优先级。

**单一下一步：** 本 PR 所有 CI 绿后自合并；下一步核对已通过的真实12镜素材，跑一次这个不收费的后期路径，并再评估 G4 阶段剩余缺口（逐镜付费重生成合法授权/转写内容验收/真实发片质量）。真实供应商账单仍未知。

## 上次审查记录（非本轮开发重点）

**先修“人物/声音生产契约与验收缺口”，不是盲目重生整集。** 复用现有角色及场景资产 Schema，先把每镜头统一角色详细定妆描述、资产 ID 与逐镜 speaker/dialogue 审核字段接入真实请求计划并有离线测试；明确当前 Omni provider 不支持 reference image/audio。随后加真实镜头内容 QA 入口及人工验收记录，考虑 R4.3 视觉跨镜检查。应按每个 G4 Req 单独小 PR 执行，更新交接文件。

只有确认能防止同脸同声漂移、并经过新的所有者费用许可，才测试最小 2–3 镜片段；不重跑12镜，不改冻结 TTS、基础设施、模型选型或发布门禁。

## 约束

AMEND-001 冻结路径不得动；AGENTS/GUARDRAILS/STAGES/AMEND 不经所有者许可不得修改。用户要求加速、减少重复确认但不能跳过收费限制。实际费用仍未知；真实已执行的一次 USD5 标记不可清理；没有新授权不得重新生成视频。
