# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**G0 → G1**。G0（本文档体系）PR 合并后，进入 **G1 真实视频 A/B 盲测**。

## 下一个任务（按顺序，一次只做一个）

1. **R1.4** 两位原创主角定妆照：Nano Banana 2.1 每人正脸/侧脸/半身各三张，须人工批准并锁定资产版本；真实付费/密钥按 AMEND-004 Issue 处理。
2. **R1.5** `scripts/ab_benchmark.py` + G1 手动工作流：固定 3 镜×3模型×1次，≤30 USD 总预算；无需在缺 Key 时运行付费任务。
3. **R1.6** 中文对白转写与媒体技术 QA。
4. **R1.7 / R1.8** 所有者盲测打分、报告与 ADR-010 签字（必须 Owner Issue）。


## 需要所有者决定的事

- [ ] Seedance / Kling 走官方 API 还是聚合平台（fal / Runware / OpenRouter）？建议：一个聚合平台统一鉴权，少写代码。
- [ ] 批准 G1 预算 30 USD。
- [ ] 提供 Seedance / Kling API Key（放 GitHub Secrets，不进仓库）。

## 最近一次交接

- 时间：2026-10-15
- Agent：GPT-6；Stage: **G1** / Req: **R1.2**
- 交付：[PR #118](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/118) — 新增 `providers/kling_video.py` 内 `KlingVideoProvider`、`FakeKlingVideoProvider`；模型 ID 可配置（当前 `kling-v3-omni`），使用已公开的 Kling Omni REST 任务格式、一次提交+有限轮询、SHA/MP4 技术检查、无效参数提前拒绝。新增 `tests/test_kling_video.py` 离线 SDK 形状/假输出测试。
- 证据：**仅官方文档 + Fake HTTP + 本机 FFmpeg**，未提交真实 Kling API 任务、实际费用未知且 `actual_fee_usd=None`。R1.3/R1.1 已先完成；不存在真实三模型 A/B 结果。
- 需要所有者决定：平台/新 `KLING_API_KEY` 和 `ARK_API_KEY` 通过 [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116)，不阻塞离线代码；未充值/未传真人素材。
- 没做：R1.4 定妆照/付费图像生成、R1.5 盲测执行、R1.7 评分，亦未改 Schema、UI、冻结路径或账本。
- 下一步：PR #118 scope、Python 3.11/3.13、native libSQL、offline-video 全绿后自主合并；然后处理 CURRENT 第一项 **R1.4**，付费/新 Key 按 AMEND-004 Issue 处理。


## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
