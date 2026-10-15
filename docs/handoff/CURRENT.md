# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**P 链路：AMEND-005（2026-10-16，Active）**。G1 三家模型真实盲测及阶段退出条件全部**暂停而非取消**；当前优先补齐“本地原创梗概 → 全 Fake MP4”的离线生产链路。AMEND-005 对旧版 STAGES 的 G2 越级开发门禁构成**明确的、仅限 Fake 的例外授权**，不修改 STAGES 本身。

### 所有者执行边界

- **允许**：P0 文档差距分析；随后 P1–P6/P-final 按 P0 清单 **一个 Req 一个 PR**，使用 Fake Text/Image/Video/Audio、可追溯的 JSON、中间产物和本机 FFmpeg/QA；scope 与全部离线 CI 绿后可按 AMEND-004 自合并。
- **严格禁止**：任何真实收费/AI Provider 调用、生产/线上测试、新 UI、小说改编、AMEND-001 冻结路径与治理文件修改。AMEND-004 小额测试额度**不使用**。
- **继续挂起**：G1/R1.4 真实定妆照、R1.5 实测、R1.7 人工评分及 R1.8 ADR-010；不宣称真实模型效果或 G1/G2/G3/G4 实际阶段验收。

## 下一个任务（按顺序，一次只做一个）

1. **P0（当前 PR，文档-only）**：`docs/PIPELINE.md` 盘点梗概→Story Bible→剧本→分镜→角色资产→逐镜视频→对白→字幕→配乐→合成→QA；列仓库可复用路径、ViMax/Jellyfish 真实对应源码及 **P1–P6/P-final 缺口**。全部 CI 通过后合并。
2. **P1 / STAGES R4.1（Fake）**：本机原创梗概文件 → 确定性 Story Bible JSON；调用已有 `FakeTextProvider`/Series schema，独立 PR。
3. **P2 / R4.1、R3.1（Fake）**：Story Bible → 分集剧本 → 经过现有 `Screenplay` 结构校验的含对白分镜，独立 PR。
4. **P3 / R2.1、R2.3（Fake）**：演员/场景/声音版本资产以及精确镜头引用，独立 PR。
5. **P4 / R3.2（Fake）**：逐镜头 Fake 调度与版本/媒体哈希 JSON，独立 PR。
6. **P5 / R3.3（Fake）**：Fake 时间音/字幕/合成配乐接线，独立 PR。
7. **P6 / R4.4（Fake）**：本地一命令 CLI、每步 JSON、可单步重跑、整集 FFmpeg + QA，独立 PR。
8. **P-final / R4.4（Fake E2E 验收）**：实际生成可播放且带 Fake 标记的 60–90 秒 MP4、保留 CI artifact；**仅合并后**建一次 `[需要所有者]` Issue 提议 Omni 360p 单次全链路真测（目标估算 ≤ US$3，须主人批准）。

## 需要所有者决定的事（已挂起，到整体真实测试时处理）

- [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116)：Seedance / Kling 官方 API 或聚合平台、账号与新密钥。
- [Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119)：六张定妆照及人工批准。
- [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120)：九镜真实 A/B 的预算和供应商硬上限。

## 最近一次交接

- 日期：2026-10-16；Agent：GPT-6；**Stage: P / Req: P0**。
- 交付：仅新增 [`docs/PIPELINE.md`](../PIPELINE.md) 全十一阶段复用/差距表、MIT ViMax 与 Apache-2.0 Jellyfish 源码实路径/许可证来源，规划 P1–P6/P-final 对应 `docs/STAGES.md` Req，**未写任何功能代码**。
- 当前 PR：本 P0 文档分支，scope/离线 CI 全绿后根据 AMEND-004 自动合并。
- 决策依据：AMEND-005 明确允许仅限 Fake 地提前开发原 G2/G3/G4 的 R2.1/R2.3、R3.1–R3.4、R4.1/R4.2/R4.4；**删除此前「不要因链路优先进入 G2」约束**，改为严格跟随 AMEND-005 的 P 链优先级，G1 真人关卡仍 pending。
- 挂起 Issue：#116 平台/密钥、#119 定妆照、#120 真实九镜预算，全部保留打开、**不处理、不调用**。
- 下一步：P0 CI 全绿合并后立刻执行 **P1**，每个 Req 单独 PR；不运行任何真实付费模型。


## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
