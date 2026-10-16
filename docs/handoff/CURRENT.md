# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**P 链路：AMEND-005（2026-10-16，Active）**。G1 三家模型真实盲测及阶段退出条件全部**暂停而非取消**；当前优先补齐“本地原创梗概 → 全 Fake MP4”的离线生产链路。AMEND-005 对旧版 STAGES 的 G2 越级开发门禁构成**明确的、仅限 Fake 的例外授权**，不修改 STAGES 本身。

### 所有者执行边界

- **允许**：P0 文档差距分析；随后 P1–P6/P-final 按 P0 清单 **一个 Req 一个 PR**，使用 Fake Text/Image/Video/Audio、可追溯的 JSON、中间产物和本机 FFmpeg/QA；scope 与全部离线 CI 绿后可按 AMEND-004 自合并。
- **严格禁止**：任何真实收费/AI Provider 调用、生产/线上测试、新 UI、小说改编、AMEND-001 冻结路径与治理文件修改。AMEND-004 小额测试额度**不使用**。
- **继续挂起**：G1/R1.4 真实定妆照、R1.5 实测、R1.7 人工评分及 R1.8 ADR-010；不宣称真实模型效果或 G1/G2/G3/G4 实际阶段验收。

## 下一个任务（按顺序，一次只做一个）

1. **P6 / STAGES R4.4（Fake）**：一个 `scripts/fake_episode.py` CLI 从原创梗概文件依次接 P1–P5；写每步 JSON、输入哈希与可单步重跑的本机 MP4/QA 结果；绝不发真实 Provider。
2. **P-final / STAGES R4.4（Fake E2E）**：用原创合成梗概运行单命令，产出60–90秒明确 Fake 的 MP4 和可下载 CI artifact，重复跑验证幂等；绿灯合并后创建一次「[需要所有者]」Issue，提议 Omni 360p 真测（预计≤US$3，需先批准）。

## 需要所有者决定的事（已挂起，到整体真实测试时处理）

- [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116)：Seedance / Kling 官方 API 或聚合平台、账号与新密钥。
- [Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119)：六张定妆照及人工批准。
- [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120)：九镜真实 A/B 的预算和供应商硬上限。

## 最近一次交接

- 日期：2026-10-16；Agent：GPT-6；**Stage: P / Req: P5**；STAGES 映射 R3.3（Fake）及 R2.1 假声线引用。
- 已完成 P0 #124、P1 #125、P2 #126、P3 #127、P4 #128；P4 scope + 四项 CI 绿灯合并，main SHA `110a504556d99de8ea5150c9c3628eb8dbb384d5`。
- P5 交付：`pipeline/fake_episode_audio.py` 从已完成 P4 Fake Production/预览哈希和已批准 Cue 时间槽生成 **06_dialogue 非语音 WAV**、**07_subtitles 原 SRT 时间表+哈希**、**08_music 纯合成 WAV+已存在混音器产出 MP4**。调用原 ffprobe、`offline_audio.mix_local_stems`、字幕 QA，不修改 TTS/Voice 权限；Fake 声线没有真实来源同意，不伪造授权。
- 测试 `tests/test_fake_episode_audio.py`：实际本机合成媒体、音轨和字幕，篡改/跨剧拒绝。0 外部模型、0 USD、没有真实说话、真人肖像或出版批准。此 PR 必须 scope + 四项 CI 完全成功才能自合并。
- 下一步仅 **P6**：接 P1–P5，CLI + JSON 哈希缓存/单步重跑/全片 QA。P-final artifact 后才发 Omni 真测提议 Issue。#116/#119/#120 保持挂起。

## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
