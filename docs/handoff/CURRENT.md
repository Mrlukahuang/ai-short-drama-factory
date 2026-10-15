# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**P 链路：AMEND-005（2026-10-16，Active）**。G1 三家模型真实盲测及阶段退出条件全部**暂停而非取消**；当前优先补齐“本地原创梗概 → 全 Fake MP4”的离线生产链路。AMEND-005 对旧版 STAGES 的 G2 越级开发门禁构成**明确的、仅限 Fake 的例外授权**，不修改 STAGES 本身。

### 所有者执行边界

- **允许**：P0 文档差距分析；随后 P1–P6/P-final 按 P0 清单 **一个 Req 一个 PR**，使用 Fake Text/Image/Video/Audio、可追溯的 JSON、中间产物和本机 FFmpeg/QA；scope 与全部离线 CI 绿后可按 AMEND-004 自合并。
- **严格禁止**：任何真实收费/AI Provider 调用、生产/线上测试、新 UI、小说改编、AMEND-001 冻结路径与治理文件修改。AMEND-004 小额测试额度**不使用**。
- **继续挂起**：G1/R1.4 真实定妆照、R1.5 实测、R1.7 人工评分及 R1.8 ADR-010；不宣称真实模型效果或 G1/G2/G3/G4 实际阶段验收。

## 下一个任务（按顺序，一次只做一个）

1. **P1 / STAGES R4.1（Fake，当前 PR）**：本机原创梗概文件 → 确定性 Story Bible JSON；调用已有 `FakeTextProvider`/Series schema，独立 PR。
2. **P2 / R4.1、R3.1（Fake）**：Story Bible → 分集剧本 → 经过现有 `Screenplay` 结构校验的含对白分镜，独立 PR。
3. **P3 / R2.1、R2.3（Fake）**：演员/场景/声音版本资产以及精确镜头引用，独立 PR。
4. **P4 / R3.2（Fake）**：逐镜头 Fake 调度与版本/媒体哈希 JSON，独立 PR。
5. **P5 / R3.3（Fake）**：Fake 时间音/字幕/合成配乐接线，独立 PR。
6. **P6 / R4.4（Fake）**：本地一命令 CLI、每步 JSON、可单步重跑、整集 FFmpeg + QA，独立 PR。
7. **P-final / R4.4（Fake E2E 验收）**：实际生成可播放且带 Fake 标记的 60–90 秒 MP4、保留 CI artifact；**仅合并后**建一次 `[需要所有者]` Issue 提议 Omni 360p 单次全链路真测（目标估算 ≤ US$3，须主人批准）。

## 需要所有者决定的事（已挂起，到整体真实测试时处理）

- [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116)：Seedance / Kling 官方 API 或聚合平台、账号与新密钥。
- [Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119)：六张定妆照及人工批准。
- [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120)：九镜真实 A/B 的预算和供应商硬上限。

## 最近一次交接

- 日期：2026-10-16；Agent：GPT-6；**Stage: P / Req: P1**（STAGES 映射 **R4.1 Fake 切面**）。
- 交付：P0 文档 [PR #124](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/124) 全绿合并，main SHA `321c98a84b1772927b2fd92b45b69edd9cec43e8`。P1 新增 `pipeline/fake_story_bible.py`：本地 UTF-8 原创梗概文件→现有 `StoryBible` Schema 有效、来源 SHA256 确定性 Fake JSON，可用 `python -m drama_factory.pipeline.fake_story_bible <input.txt> --output <new.json>`；明确仅为模板，0 模型、0 费用、0 自动批准。
- 测试：`tests/test_fake_story_bible.py` 覆盖稳定复跑、Schema、中文 UTF-8、越界/非法文件、符号链接、输出不覆盖等；PR 的 scope/离线 CI 以实际终态为准，绿灯可自合并。
- **没有做**：人物推理/图像/真实编剧、Series DB 写入、视频、商业版权核验（留给 P2/P3 及后续）；G1 实测仍暂停。
- 之前 #116 平台密钥、#119 定妆照、#120 真实 A/B 的 Issue 保持打开不处理。AMEND-001 冻结路径和治理文件未改。
- 下一项：**P2** Story Bible→分集剧本→结构化含对白分镜（Fake），独立 PR。P-final 后才提 Omni 360p 真测 Issue，**目前不能发真实调用**。


## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
