# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**P 链路：AMEND-005（2026-10-16，Active）**。G1 三家模型真实盲测及阶段退出条件全部**暂停而非取消**；当前优先补齐“本地原创梗概 → 全 Fake MP4”的离线生产链路。AMEND-005 对旧版 STAGES 的 G2 越级开发门禁构成**明确的、仅限 Fake 的例外授权**，不修改 STAGES 本身。

### 所有者执行边界

- **允许**：P0 文档差距分析；随后 P1–P6/P-final 按 P0 清单 **一个 Req 一个 PR**，使用 Fake Text/Image/Video/Audio、可追溯的 JSON、中间产物和本机 FFmpeg/QA；scope 与全部离线 CI 绿后可按 AMEND-004 自合并。
- **严格禁止**：任何真实收费/AI Provider 调用、生产/线上测试、新 UI、小说改编、AMEND-001 冻结路径与治理文件修改。AMEND-004 小额测试额度**不使用**。
- **继续挂起**：G1/R1.4 真实定妆照、R1.5 实测、R1.7 人工评分及 R1.8 ADR-010；不宣称真实模型效果或 G1/G2/G3/G4 实际阶段验收。

## 下一个任务（按顺序，一次只做一个）

1. **P4（当前 PR）/ STAGES R3.2（Fake）**：从已审核的本机 Fake Production 调用现有 `jobs/offline_worker.py`，校验逐镜 task/input/媒体 SHA256、资产版本，输出 `05_shots` Fake manifest；真实 Provider 不调用。
2. **P5 / R3.3（Fake）**：复用 `providers/dialogue_audio.py`、字幕和 `offline_audio.py`，接通非人声提示音/合成配乐。
3. **P6 / R4.4（Fake）**：一命令 CLI、每步 JSON、可单步重跑、完整离线合成和 QA。
4. **P-final / R4.4（Fake E2E）**：从原创梗概 CLI 实产带 Fake 标签的 60–90s MP4 + GitHub 可访问 artifact；全绿合并**之后**建一次 `[需要所有者]` Issue 提议 Omni 360p 单次真测（预估 ≤US$3，需明确批准，不自动运行）。


## 需要所有者决定的事（已挂起，到整体真实测试时处理）

- [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116)：Seedance / Kling 官方 API 或聚合平台、账号与新密钥。
- [Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119)：六张定妆照及人工批准。
- [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120)：九镜真实 A/B 的预算和供应商硬上限。

## 最近一次交接

- 日期：2026-10-16；Agent：GPT-6；**Stage: P / Req: P4**（STAGES R3.2 Fake 切面）。
- 合并基线：P0 #124 → P1 #125 → P2 #126 → P3 [#127](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/127) 已全绿合并；P3 main SHA `8660a08fdd81a724ca2015447c189965cbadffbc`。
- 交付：新增 `pipeline/fake_shot_manifest.py` 通过**既有已通过双人工审批的 Production** 调用 `run_offline_production`、`jobs/shots.py`；已登记每镜 Fake job、输入哈希、媒体 SHA256、演员/场景具体版本规格哈希；强制`generation_intent_recorded=0`且`actual_vendor_charge_usd=null`，不发任何真实收费请求。复用现有缓存重跑而不自建任务调度。
- 测试：`tests/test_fake_shot_manifest.py` 用程序化生成的假角色和真实 FFmpeg 验证六镜60秒、缓存重读、无付费、跨剧和审批门禁。不增加新的审核入口；Fake 测试才通过现有 API 显式执行审批。
- 尚未实现：P5 的独立 Fake 音轨/字幕/配乐接线；P6 的一个 CLI 和 JSON 连续恢复；P-final 的 CI Fake MP4 artifact。现有 worker 虽合成技术预览，但不宣称是真实 AI 视频。
- Issue #116/#119/#120 仍挂起不处理，G1 实测不启动。此 P4 独立 PR 需 scope 与四项 CI 完全全绿才能自合并，下一项仅 P5。


## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
