# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**G1 真实视频 A/B 盲测：先把离线调用链路接通；真实测试按所有者 2026-10-16 最新指示全部暂停。**

### 所有者最新执行边界（不修改 AMEND 治理文件）

- **继续**：独立 Req 的代码和 Fake/Stub、无密钥契约测试、合成媒体的本机 FFmpeg/ffprobe 技术测试、JSON 结果流转；scope + 纯离线 CI 全绿后按 AMEND-004 可以合并。
- **暂停**：任何真实 AI 模型/供应商请求、收费/真实账户或 Secret 验证、真人素材上传、真实九镜盲测、Gemini 实际转写、生产环境或正式发布。即使 AMEND-004 允许 US$2/次，也不得在用户回来前发起。
- 实际测试结果、真实账单、人工审核和 G1 阶段退出条件保持 **pending**；Fake/技术 MP4 不能冒充真实 AI 视频验收。

## 下一个任务（按顺序，一次只做一个）

1. **R1.6（当前）** 中文 CER + FFprobe 媒体 QA + 结果 JSON：离线接口与独立测试已提交 [PR #待填写](https://github.com/Mrlukahuang/ai-short-drama-factory/pulls)。完成后不自动执行真实 Gemini Transcribe。
2. **R1.4（真实素材/人工审核阻塞）** Nano Banana 2.1 六张定妆照：等所有者回来统一实测、批准资产，[Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119)。
3. **R1.5（真实执行阻塞）** 九镜三模型真实 A/B：此前 #121 仅 PLAN-ONLY；硬预算与授权在 [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120)。
4. **R1.7 / R1.8（人工评分/阶段退出阻塞）** 等真实测试结束后再评分、ADR-010 签字；不得伪造 G1 退出。

上述 G1 尚无其它独立未开发的离线 Req。**不要因“链路优先”擅自修改 STAGES 阶段退出规则或进入 G2。** 如需跨阶段提前开发须先遵照 AMEND-004 的所有者升级机制。

## 需要所有者决定的事（已挂起，到整体真实测试时处理）

- [Issue #116](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/116)：Seedance / Kling 官方 API 或聚合平台、账号与新密钥。
- [Issue #119](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/119)：六张定妆照及人工批准。
- [Issue #120](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/120)：九镜真实 A/B 的预算和供应商硬上限。

## 最近一次交接

- 日期：2026-10-16；Agent：GPT-6；Stage: G1 / Req: **R1.6**。
- 交付：`src/drama_factory/pipeline/g1_benchmark_metrics.py` 中文 CER、静音镜头不评分、合成视频 FFprobe 和 Mock 台词诊断；`scripts/g1_metrics.py` 产出九任务 pending 结果；`benchmarks/g1/results.json` 明确九项媒体/费用/真实转写均未运行；测试 `tests/test_g1_benchmark_metrics.py`。
- 不包含：真实 Gemini 3.5 Transcribe、真实视频质量、费用/人脸声线/口型评测。**真正 R1.6 完整真实效果验收仍待用户回来实测**，本 PR 只打通 Fake 数据路径。
- 用户当前要求：**暂停全部真实测试，先接通链路**；每小时自动任务已更改为 Fake-only。R1.4/R1.5 和 G1 人工评分保持挂起，不触发真实测试。
- 治理：不修改 AMEND.md/STAGES.md/GUARDRAILS.md/AGENTS.md、AMEND-001 冻结路径、数据库表或付费工作流；仍按一个 Req 一个 PR。
- 下一步：PR 通过 scope+离线 CI 后可自动合并；到 G1 阶段门禁时停住真实执行与 G2 越级开发，等待所有者批准后整体实测。

## 异议栏（Agent 对方向有不同意见时写这里，等所有者裁决）

（空）
