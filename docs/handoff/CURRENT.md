# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**P 链路：AMEND-005（2026-10-16，Active）**。G1 三家模型真实盲测及阶段退出条件全部**暂停而非取消**；当前优先补齐“本地原创梗概 → 全 Fake MP4”的离线生产链路。AMEND-005 对旧版 STAGES 的 G2 越级开发门禁构成**明确的、仅限 Fake 的例外授权**，不修改 STAGES 本身。

### 所有者执行边界

- **允许**：P0 文档差距分析；随后 P1–P6/P-final 按 P0 清单 **一个 Req 一个 PR**，使用 Fake Text/Image/Video/Audio、可追溯的 JSON、中间产物和本机 FFmpeg/QA；scope 与全部离线 CI 绿后可按 AMEND-004 自合并。
- **严格禁止**：任何真实收费/AI Provider 调用、生产/线上测试、新 UI、小说改编、AMEND-001 冻结路径与治理文件修改。AMEND-004 小额测试额度**不使用**。
- **继续挂起**：G1/R1.4 真实定妆照、R1.5 实测、R1.7 人工评分及 R1.8 ADR-010；不宣称真实模型效果或 G1/G2/G3/G4 实际阶段验收。

## 下一个任务（按顺序，一次只做一个）

1. **P3（当前 PR）/ STAGES R2.1、R2.3（Fake）**：将 P2 临时人物/场景/声音引用写入已有本机 SQLite Series/Bible/资产版本，保持事务幂等、范围校验和零真人授权，不修改表结构。
2. **P4 / R3.2（Fake）**：调用已有逐镜 Fake worker，按镜头登记状态、资产版本哈希与技术媒体数据。
3. **P5 / R3.3（Fake）**：连接虚构对白提示音、字幕与本机合成配乐。
4. **P6 / R4.4（Fake）**：一命令 CLI、每步 JSON、单步重跑和完整本机 FFmpeg/QA。
5. **P-final / R4.4（Fake E2E）**：实产可播放带 Fake 标记的60–90秒 MP4 + 可访问 CI artifact；合并后才建一次 `[需要所有者]` Issue 提议 Omni 360p 单次全链路真测（预计 ≤US$3，须主人批准）。


## 需要所有者决定的事（已挂起，到整体真实测试时处理）

- [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116)：Seedance / Kling 官方 API 或聚合平台、账号与新密钥。
- [Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119)：六张定妆照及人工批准。
- [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120)：九镜真实 A/B 的预算和供应商硬上限。

## 最近一次交接

- 日期：2026-10-16；Agent：GPT-6；**Stage: P / Req: P3**；STAGES 映射 **R2.1/R2.3 的纯 Fake 部分**。
- 合并基线：P0 [#124](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/124)、P1 [#125](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/125)、P2 [#126](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/126) 均全绿 squash 合并；P2 main SHA `2ccd7ca1aff270435e43b17f5e924d301397377b`。
- 交付：新增 `pipeline/fake_cast_assets.py`，完全复用现有 SQLite `projects` / `story_bibles` / `series_assets` 表、`ActorBible/VoiceBible/SceneBible` 和 `check_screenplay_scope`；将经重新计算验证的 P1/P2 Fake 输入绑定成 2 演员+2 虚构声线+1 场景的确定性 v1 资产，单事务且重复调用幂等。新增 `tests/test_fake_cast_assets.py` 验证版本、跨剧隔离、冲突拒绝和不自动生成 Episode/Production。
- 权利边界：只有 `fake_only` 模拟资产，未生成人脸/声音，`approval_granted=false` / `approved_for_real_model=false`；这只是本机 SQLite 归属，不是人工审核或商业使用授权。0 外部模型、0 费用、无既有表迁移。
- 本次 PR 需 scope + Python 3.11/3.13 + native libSQL + FFmpeg 全绿才自合并；之后执行 P4（独立 Req/PR）。
- G1 真测和 Issues #116/#119/#120 均继续暂停、不处理。P-final 真测提议 Issue 仅在 Fake MP4 artifact 可查且已合并后创建。


## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
