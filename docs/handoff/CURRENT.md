# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**G0 → G1**。G0（本文档体系）PR 合并后，进入 **G1 真实视频 A/B 盲测**。

## 下一个任务（按顺序，一次只做一个）

1. **R1.2** `providers/kling_video.py`（Kling 3.0 Omni，模型 ID 可配置）+ Fake + 契约测试；**单独 PR，不与 R1.1 合并**。
2. **R1.4** 2 位主角 6 张定妆照，人工批准、版本化（调用可能产生费用，按 AMEND-004 边界处理）。
3. **R1.5** `scripts/ab_benchmark.py` + G1 手动 workflow（固定镜头×3模型）。
4. **R1.6** 转写/技术 QA 自动指标。
5. **R1.7 / R1.8** 所有者盲测评分、报告、ADR-010 签字（需按 AMEND-004 建立 [需要所有者] Issue）。


## 需要所有者决定的事

- [ ] Seedance / Kling 走官方 API 还是聚合平台（fal / Runware / OpenRouter）？建议：一个聚合平台统一鉴权，少写代码。
- [ ] 批准 G1 预算 30 USD。
- [ ] 提供 Seedance / Kling API Key（放 GitHub Secrets，不进仓库）。

## 最近一次交接

- 时间：2026-10-15
- Agent：GPT-6；Stage: **G1** / Req: **R1.1**
- 工作：新增 `src/drama_factory/providers/seedance_video.py`，官方火山方舟 Seedance 2.5 型式适配 + `FakeSeedanceVideoProvider` + `tests/test_seedance_video.py`；共享 `VideoProvider` 协议，明确无重提单、无额外付费调用。PR [#117](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/117)（CI 全绿后可自主合并）。
- 证据：**仅官方文档 + 注入 Fake SDK/本地 FFmpeg**；没有真实 Seedance API 调用，实际供应商收费未验证，`VideoResult.actual_fee_usd=None`。
- 阻塞：官方/聚合平台选择、账号开通、`ARK_API_KEY` 请所有者在 [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116) 决定，不阻挡 R1.2 离线开发。平台余额/套餐可能超过 AMEND-004 单次 $2，未购买。
- 未做：R1.2 Kling、R1.4 定妆照、R1.5/R1.6 盲测执行、模型真钱验证；无数据库/冻结路径/新工作流变更。
- 下一步：如 #117 全部 CI（含 scope）绿则按 AMEND-004 合并，再处理 **R1.2 单独 PR**。

## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
