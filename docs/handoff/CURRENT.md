# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**G0 → G1**。G0（本文档体系）PR 合并后，进入 **G1 真实视频 A/B 盲测**。

## 下一个任务（按顺序，一次只做一个）

1. **R1.6** 中文对白转写准确率 + ffprobe 技术 QA；没有真实模型素材时只做离线 Fake/接口测试，结果标注非真实盲测。
2. **R1.4（真实素材阻塞）** Nano Banana 2.1 两位主角定妆照（3 张×2 人）：需 [Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119) 的 Key/素材设定/所有者人工确认。
3. **R1.5（实际执行阻塞）** 九任务 A/B 的真实运行：本 PR #121 仅交付固定计划/手动离线工作流，需 [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120) 预算批准和可验证供应商硬限额，以及 #116 API 密钥；**不得报告 A/B 已完成**。
4. **R1.7 / R1.8** 所有者盲测打分、报告与 ADR-010 签字，必须按 AMEND-004 升级 Issue。


## 需要所有者决定的事

- [ ] Seedance / Kling 走官方 API 还是聚合平台（fal / Runware / OpenRouter）？建议：一个聚合平台统一鉴权，少写代码。
- [ ] 批准 G1 预算 30 USD。
- [ ] 提供 Seedance / Kling API Key（放 GitHub Secrets，不进仓库）。

## 最近一次交接

- 时间：2026-10-15
- Agent：GPT-6；Stage: **G1** / Req: **R1.5（计划及离线工作流部分）**；[PR #121](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/121)。
- 做了：三镜固定中文 A/B 场景 `benchmarks/g1/shots.json`、`scripts/ab_benchmark.py` 精确 3×3×1 计划生成（人工确认词，计划预算≤US$30）、手动 `video-ab-benchmark.yml` 只输出无模型媒体的 JSON，新增拒绝越权/越额 Fake 测试。
- 未做：**没有真实 9 次视频生成**、没有人工批准的六张定妆照、没有真实供应商美元硬账单限制。不能把 plan-level 上限称为已执行的供应商硬上限。无模型调用/媒体上传/新 Secrets，费用 US$0。
- 阻塞：[Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116) 平台与新密钥，[Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119) R1.4 定妆照授权/人工选片，[Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120) 实际 G1 盲测预算/硬限额确认，全部已按 AMEND-004 升级。
- 上一项：R1.1 [#117](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/117) 和 R1.2 [#118](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/118) 已全绿自动合并；两者仅完成官方 wire adapter、Fake/合同测试，未有真实 AI 模型结果。
- 下一步：PR #121 全 CI 绿后自动合并。继续 **R1.6** 不依赖真实素材的转写/QA 部分，未实际测得的数据填 null 并明确标注非真实评分。


## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
