# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**AMEND-006（Active）— F1 → F2 → F3**。ADR-010 已 Accepted：固定 `gemini-omni-1.1-flash` + 原生中文对白 + 奥克兰毛毡微缩 `config/style_presets/felt_diorama.json`。PR #133 已执行真实 3 镜风格试验，#132 已由所有者确认采用。P0–P-final 完成（最终 PR #131）。依据 AMEND-006，本方向的真实调用从 AMEND-005 暂停中解除，但仍受 AMEND-004 每次≤US$2、当天累计≤US$5 控制。

### 不变边界

- 每个 F 单独分支/PR；scope+全部 CI 全绿自行合并，更新本文件和 LOG；无需中途等待。
- **不修改** AMEND-001 冻结路径或治理文件，不新增 UI、不改小说、不解锁 TTS / TxLab canary。
- F3 实际费用须与预估分开记录；若供应商账单或可信费用上限不可核对，停止该付费测试并开 `[需要所有者]` Issue。不得拆分超预算请求。

## 下一个任务（按顺序，一次只做一个）

1. **F2（本 PR）**：`scripts/fake_episode.py --provider omni --style felt_diorama`；Fake 默认不变；沿用 P-final 11步 JSON、纯合成前四步、六镜原生音轨、逐镜哈希+拒绝未知付费任务自动重试。
2. **F3（本 PR #138，真实执行 BLOCKED）**：六镜360p工作流、保留原生音轨、成本/任务/ffprobe验收报告以及上传步骤的实现；AMEND-004 每次US$2预检确认可能超过预算，**不执行任何真实请求**。已有 [需要所有者] Issue #137；真实MP4、人工角色/对白评价、每镜实际账单和审片 Issue 待此决定后处理。

## 需要所有者决定的事（现状）

- #116 Seedance/Kling、#119 定妆照及 #120 多模型九镜仍保留备选，不阻塞毛毡方向。
- #132 已按 AMEND-006 接受三镜风格试片结论（预计 US$0.70，实际账单未在仓库中独立核实）。

## 最近一次交接

- 2026-10-17，GPT-6，F3 临时预算接线修复：所有者在 ChatGPT 明确批准 **仅本次 Issue #137** 单次最高 **US$2.50**、当天累计 **US$5.00**；默认 AMEND-004 **US$2.00 不变**。此分支在 `scripts/f3_omni_report.py`、`scripts/felt_omni_episode.py` 与 `scripts/fake_episode.py` 显式串接临时额度、每日已花费声明、六镜总输出10秒上界 + 保守输入/文本余量预估；**这只是费用估计，不是 Google 供应商硬限价**，真实账单仍须复核。
- 手动 F3 工作流新增 `reported_spend_today_usd` 必填参数；预算预检与 Secret 有效性检查通过后，**先在 #137 写入一次性 Actions 运行标记，再允许首次付费请求**；新运行或 rerun 会在提交 API 前停止。失败时仅上传任务收据供人工核对，不得盲目重新执行。尚未执行任何新模型生成；整集 MP4 / 看片 Issue 尚无。
- 已知限制：当前 GitHub 连接器能改 PR/读 CI，但**没有 workflow_dispatch 操作**；即使 PR CI 全绿合并也不能从本对话直接触发手动收费工作流。需要本人在 Actions 填入真实当日 Google 账单已花费金额并执行一次，不能猜测为零；只在对费用上界有合理把握时执行。此前失败的 Run #38922439695 0付费，FFmpeg 已通过 PR #140 修复。

- 2026-10-17，GPT-6，F3 CI 环境修复 PR #140：所有者手动触发的 Run #38922439695 在 `ffmpeg: command not found` (exit 127) 停止；**预算检查、读取 Gemini Secret、全部真实生成均 skipped，因此该 run 0 次付费调用**。PR #140 使用仓库现有 SHA256 锁定 FFmpeg/ffprobe 包配置 GitHub Runner，离线 CI 通过前不得合并。
- 已收到所有者聊天授权本次限额 USD2.50、日限额 USD5；**但目前 F3 代码仍使用单次 USD2.00 门禁，真实六镜仍不可执行**，需先核对可验证费用上限，不因环境修复重复手动触发。#137 先保留，#116/#119/#120 保持不变。

- 2026-10-16，GPT-6，**Stage: F / Req: F3**，对应 G4/R4.4；F1 #135 已合并、F2 #136 已 CI 全绿合并 SHA `e47a2489d0f477a15a2059298bfc4661f339e89b`。
- **F3 [PR #138](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/138)**：手动六镜 Omni 360p + 原生音频 workflow；读取 Gemini Secret/供应商收费请求前必须先进行严格单次费用预检；实际六镜视频音频 + task ID + 时长宽高和真假费用分别记录、如真实成功才上传 Artifact。该 PR 只交付可检查的代码/离线测试，不宣称已经有六镜真实成片。
- **[需要所有者] Issue #137** 是 AMEND-004 合法阻塞：Google 官方36/60? 视频360p输出为1931 tokens/秒、US$17.50/百万 token；六镜若各10s就是 US$2.02755，未含 prompt；目前 Interactions API Omni 旧适配器不提供经核验的严格时长或账单硬限额。52s的提示词总时长只是期望值（约US$1.75721输出），不能取代最高费用保证。**F3 没有发出任何真实调用，实际收费 US$0。**
- 下一步：仅在所有者于 #137 批准超额预算或确认供应商可实施的费用/时长硬门禁后，才能运行真正 F3，并核实每镜实际费用、总费用及人工看片。#116/#119/#120 不处理；无其它新 Req。

## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
