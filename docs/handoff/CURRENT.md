# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**G0 → G1**。G0（本文档体系）PR 合并后，进入 **G1 真实视频 A/B 盲测**。

## 下一个任务（按顺序，一次只做一个）

1. **R1.1** `providers/seedance_video.py`（Seedance 2.5）+ Fake + 契约测试。
2. **R1.2** `providers/kling_video.py`（Kling 3.0 Omni，模型 ID 可配置）+ Fake + 契约测试。
3. **R1.4 / R1.5 / R1.6** 定妆照 + `scripts/ab_benchmark.py` + 手动 workflow（≤ 30 USD 硬上限，需确认词）。
4. 所有者手动触发 → **R1.7** 盲测打分 → **R1.8** 报告 + ADR-010。

## 需要所有者决定的事

- [ ] Seedance / Kling 走官方 API 还是聚合平台（fal / Runware / OpenRouter）？建议：一个聚合平台统一鉴权，少写代码。
- [ ] 批准 G1 预算 30 USD。
- [ ] 提供 Seedance / Kling API Key（放 GitHub Secrets，不进仓库）。

## 最近一次交接

- 时间：2026-10-15
- Agent：GPT-6（GitHub Provider-only 分支）
- Stage / Req：**G1 / R1.3**；[PR #114](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/114)，**等待 CI 与所有者合并**。
- 做了：新增 `providers/video_provider.py` 的 `VideoProvider`、`VideoRequest`、`VideoResult`；现有 Google Omni 与 Fake 实现 `generate_video`，旧接口不变；新增离线 SDK/FFmpeg 契约测试。SDK 未返回任务 ID / 未核实实际收费一律 `None`，不伪造；不支持的 Omni 参考图、音频引用或比例在发送前拒绝。
- 没做：**R1.1 Seedance、R1.2 Kling**（独立 PR）；**三个真实 Provider 均实现协议的 G1/R1.3 整体验收仍待后续 PR**。没有真实模型调用、费用支出、账本变更、UI/冻结路径改动。
- 下一步：所有者审阅及合并 #114 后，由下一 Agent 只处理 CURRENT 首项 **R1.1**，遵循独立 Req/PR 和 AMEND 门禁。
- 基线：此前 main #38570869325 全绿；此 PR CI 以 GitHub Checks 最终回执为准。

## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
