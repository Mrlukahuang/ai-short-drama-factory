# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**G0 → G1**。G0（本文档体系）PR 合并后，进入 **G1 真实视频 A/B 盲测**。

## 下一个任务（按顺序，一次只做一个）

1. **R1.3** 统一 `VideoProvider` 协议：从现有 `providers/google_omni_video.py` 抽出接口（输入：prompt、参考图列表、可选音频参考、时长、比例；输出：MP4 路径、provider task_id、实际费用）。让 Omni 实现它。只改 Provider 层，不碰账本。
2. **R1.1** `providers/seedance_video.py`（Seedance 2.5）+ Fake + 契约测试。
3. **R1.2** `providers/kling_video.py`（Kling 3.0 Omni，模型 ID 可配置）+ Fake + 契约测试。
4. **R1.4 / R1.5 / R1.6** 定妆照 + `scripts/ab_benchmark.py` + 手动 workflow（≤ 30 USD 硬上限，需确认词）。
5. 所有者手动触发 → **R1.7** 盲测打分 → **R1.8** 报告 + ADR-010。

## 需要所有者决定的事

- [ ] Seedance / Kling 走官方 API 还是聚合平台（fal / Runware / OpenRouter）？建议：一个聚合平台统一鉴权，少写代码。
- [ ] 批准 G1 预算 30 USD。
- [ ] 提供 Seedance / Kling API Key（放 GitHub Secrets，不进仓库）。

## 最近一次交接

- 时间：2026-10-15
- Agent：Claude（claude.ai 会话）
- 做了：G0 全部文档；AMEND-001~003；scope guard CI；model_registry 更新。
- 没做：任何功能代码改动。
- 基线：`pytest -q` 应全绿（本 PR 未改 src）。

## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
