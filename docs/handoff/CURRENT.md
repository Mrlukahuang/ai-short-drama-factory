# 当前交接状态（2026-10-19 NZT）

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

## 当前执行方向（所有者 2026-10-19 再次明确）

**优先把生产流水线跑顺，而不是现在精修人物、音色或剧情。** 本轮 Stage: G4 / Req: R4.4 追加一项不收费的真实视频后期能力：使用已有外部 MP4 对完整12镜中的指定一镜进行离线替换，只重拼接、校验，不重生成11个其它镜头。新增脚本 `scripts/repair_gpt_episode_offline.py`、离线真实 FFmpeg 合成测试及 `docs/GPT_EPISODE_COMPLETION.md` 使用说明。生成与真实质量审核仍未因此通过。

**单一下一步**：在此 PR 绿灯合并后，继续打通**真实生成视频到后期**的最短路径（剧本对应的字幕草稿、可选配乐与版本化输出），保留原生中文音轨和严格区分“推定字幕”和“经过转写验证”的标记；先复用已有真实视频离线测通，严禁新增收费调用或冒称内容验收通过。

评估给所有者的进度：最短 Sol/GPT→12镜Omni→FFmpeg→技术QA已经真实成功；G4全流程约75%（主观工程估算，不是自动化量化验收），剩25%主要是完整真实后期接线、单镜实际生成/修复的收费授权衔接、内容/费用最终验收。G4未正式退出。

## 上次审查记录（非本轮开发重点）

**先修“人物/声音生产契约与验收缺口”，不是盲目重生整集。** 复用现有角色及场景资产 Schema，先把每镜头统一角色详细定妆描述、资产 ID 与逐镜 speaker/dialogue 审核字段接入真实请求计划并有离线测试；明确当前 Omni provider 不支持 reference image/audio。随后加真实镜头内容 QA 入口及人工验收记录，考虑 R4.3 视觉跨镜检查。应按每个 G4 Req 单独小 PR 执行，更新交接文件。

只有确认能防止同脸同声漂移、并经过新的所有者费用许可，才测试最小 2–3 镜片段；不重跑12镜，不改冻结 TTS、基础设施、模型选型或发布门禁。

## 约束

AMEND-001 冻结路径不得动；AGENTS/GUARDRAILS/STAGES/AMEND 不经所有者许可不得修改。用户要求加速、减少重复确认但不能跳过收费限制。实际费用仍未知；真实已执行的一次 USD5 标记不可清理；没有新授权不得重新生成视频。
