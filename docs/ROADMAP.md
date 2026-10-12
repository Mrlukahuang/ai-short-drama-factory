# 开发路线图与 PR 切分（2026-10-12）

采用小 PR、独立验收、默认不花费模型费用。以下是计划，不代表已有实现。

## M0：基座（当前）

- [x] 真人 / 2D / 3D 原创建项 API
- [x] 分集 JSON 和基础审核状态
- [x] Fake 模拟（无可播放视频）
- [x] 小说上传、文本解析、章节索引、版权登记与基础门槛
- [x] 本地 Streamlit 原型及模型注册表
- [x] 测试和 GitHub Actions CI 代码
- [x] 私有 GitHub 仓库已建立，main 已提交，离线 CI 通过

## M1：编剧与版权改编分支

- [x] PR-01：Column → Series → Episode 层级、Story/Actor/Scene/Voice/Prop 契约与独立资产库；旧项目自动归入默认栏目、跨剧引用阻断。并发 Worker 仍在 M3。
- [x] PR-02：TextProvider + FakeTextProvider + 结构化校验 + Prompt 版本（模拟草稿，尚无真实 AI 文本生成）
- [x] PR-03：审阅 Drama Skills（MIT/Agent 工作流），建立真人分集/镜头/对白的严格契约、跨剧引用校验和人工提交接口；**真实 AI 创作尚未接入**
- [x] PR-04：小说 `NovelSource`、`SourceSpan`、`PlotEvent`、`CharacterMention`、`SeasonPlan` 独立 Schema 和原文索引偏移校验（非自动拆集）
- [x] PR-05a：小说章节级分块清单、幂等哈希、独立任务准备与初步版权门禁（尚未执行 AI 事件抽取或重试）
- [ ] PR-05b：结构化事件抽取 Provider、结果缓存、失败重试与来源映射（需要真实模型与审批门禁）
- [x] PR-06a：改编权人工审核记录（范围/有效期/语言/第三方 AI），内部只读资格评估，无付费调用
- [ ] PR-06b：改编 SeasonPlan 审核、合同实质核验及权限认证（生产前）

## M2：视觉、声音、Google API

- [ ] PR-07：资产库（演员、妆发、服装、表情、声音、场景和道具）+ 不可变版本
- [ ] PR-08：Google ImageProvider，Nano Banana 角色资产及参考图检查
- [ ] PR-09：Google VideoProvider，Omni 1.1 视频提交/查询/下载/可播放性校验
- [ ] PR-10：AudioProvider（Gemini TTS）；固定角色音色 ID、对白时长和审核
- [ ] PR-11：Seedance / Kling VideoProvider 对照，真实质量盲测报告

## M3：生产与成本

- [ ] PR-12：每镜头 job、provider task_id、状态、错误、实际费用及幂等 key
- [ ] PR-13：独立失败重试、恢复轮询、并发限流、单集/每日/每 Provider 预算
- [ ] PR-14：自动 QA（解码、字幕音长、演员视觉一致性提示及人工审批）

## M4：后期成片

- [ ] PR-15：FFmpeg 音画规范化、双轨混音、字幕、片尾和交付 MP4
- [ ] PR-16：Remotion 时间线及审片 UI；逐镜头替换而无需整集重做

## M5：生产部署

- [ ] PR-17：从 SQLite 迁移可追溯至 Turso 的任务元数据
- [ ] PR-18：R2/S3 对象存储、短期签名下载、加密和生命周期策略
- [ ] PR-19：身份认证、队列 worker、定时任务、审计、版权与 AI 标识合规

## 验收与门禁

1. 每个 PR 至少有测试、Schema/文档及迁移说明。
2. 新增付费 Provider 初期**默认关闭**；测试需要手动显式开启。
3. 视频阶段必须能做到“一个镜头失败、其他通过的镜头原样复用”。
4. 每个真人试镜案例至少测：双人对话、视线反打、微表情、动作交接。
5. 未核准的小说或未经授权的面容/声音不得传给外部服务。
6. 不把模型质量/价格/区域支持的尚未完成测试结果写成既定事实。