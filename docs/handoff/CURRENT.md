# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**P 链路：AMEND-005（2026-10-16，Active）**。G1 三家模型真实盲测及阶段退出条件全部**暂停而非取消**；当前优先补齐“本地原创梗概 → 全 Fake MP4”的离线生产链路。AMEND-005 对旧版 STAGES 的 G2 越级开发门禁构成**明确的、仅限 Fake 的例外授权**，不修改 STAGES 本身。

### 所有者执行边界

- **允许**：P0 文档差距分析；随后 P1–P6/P-final 按 P0 清单 **一个 Req 一个 PR**，使用 Fake Text/Image/Video/Audio、可追溯的 JSON、中间产物和本机 FFmpeg/QA；scope 与全部离线 CI 绿后可按 AMEND-004 自合并。
- **严格禁止**：任何真实收费/AI Provider 调用、生产/线上测试、新 UI、小说改编、AMEND-001 冻结路径与治理文件修改。AMEND-004 小额测试额度**不使用**。
- **继续挂起**：G1/R1.4 真实定妆照、R1.5 实测、R1.7 人工评分及 R1.8 ADR-010；不宣称真实模型效果或 G1/G2/G3/G4 实际阶段验收。

## 下一个任务（按顺序，一次只做一个）

1. **P2（当前 PR）/ STAGES R4.1、R3.1（Fake）**：从 P1 Bible 生成 `FakeTextProvider` ScriptOutline 与符合 `screenplay.zh.v1` 的六镜60–90秒 Fake 中文对白剧本；临时角色/场景 ID 明确 `provisional_asset_ids=true`、`scope_validated_against_database=false`；不提交 Episode、不人工自动批准。
2. **P3 / R2.1、R2.3（Fake）**：将 P2 临时人物/场景关联到现有 SQLite Series 的正式 Fake 资产 ID/版本并查 scope，独立 PR。
3. **P4 / R3.2（Fake）**：逐镜 Fake 调度与媒体哈希/版本 JSON，独立 PR。
4. **P5 / R3.3（Fake）**：Fake 对白音轨、字幕、合成配乐接线，独立 PR。
5. **P6 / R4.4（Fake）**：一命令 CLI、每步 JSON、单步重跑和完整本机 FFmpeg/QA，独立 PR。
6. **P-final / R4.4（Fake E2E）**：60–90秒可播带 Fake 标记 MP4 + 可访问 CI artifact；此 PR 合并后才新建一次 `[需要所有者]` Issue 提议 Omni 360p 全链路真测（预计 ≤ US$3，须主人批准）。


## 需要所有者决定的事（已挂起，到整体真实测试时处理）

- [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116)：Seedance / Kling 官方 API 或聚合平台、账号与新密钥。
- [Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119)：六张定妆照及人工批准。
- [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120)：九镜真实 A/B 的预算和供应商硬上限。

## 最近一次交接

- 日期：2026-10-16；Agent：GPT-6；**Stage: P / Req: P2**（STAGES 映射 R4.1 Fake/R3.1 Fake）。
- 合并基线：P0 [#124](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/124) 与 P1 [#125](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/125) 已全绿合并；P1 main SHA `6f2e7036e3571ce1ace22a50ca04270bba6d9b91`。
- 本 Req 实现：`pipeline/fake_episode_screenplay.py` 使用已有 `FakeTextProvider` 从 P1 `StoryBible` 构造确定性单集 outline、六镜 60–90s 中文 Fake 对白 `Screenplay`，经 `Screenplay.model_validate` 与 `to_episode_draft` 纯结构校验；`tests/test_fake_episode_screenplay.py` 覆盖时间线、角色归属、来源变更及禁止伪造审核。
- **未做**：没有 Series/Bible/演员的真实数据库归属；合成 provisional ID 只能作待 P3 替换的占位，不得用来调用 `/commit`、真实 Provider 或跳过任何审核门禁。无外部模型、无付费。
- CI：本 P2 独立 PR scope + 4 离线 CI 以实际终态为准；不改治理文件/AMEND-001 冻结路径。
- Issue #116、#119、#120 保持挂起，不处理。G1 真人盲测仍暂停。
- 下一步：P2 通过后按 AMEND-005 自主合并，再处理 **P3** 资产引用与 DB 归属映射；P-final 真实 Omni 建议 Issue 要等完整 Fake MP4 artifact 实际存在后才开。


## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
