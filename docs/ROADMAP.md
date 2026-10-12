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

- [x] PR-07a：人物/场景/声样媒体参考版本、来源许可与审核记录（只登记元数据，无二进制存储）
- [ ] PR-07b：安全媒体上传、对象存储、真正的妆发/服装/表情资产编辑界面与审片工作台
- [x] PR-08a：Google Nano Banana 2.1 受控 SDK Provider + Fake + 门禁测试；未实际调用、未存储媒体、尚无参考图条件输入
- [x] PR-09a：手动单张 Google 图片冒烟测试工作流、私有 Secret 和零调用默认模式；**真实 API 调用尚未执行**
- [ ] PR-08b：Google 图片生成端到端真实试片、参考图载入、审核后保存资产版本（需用户设置 Secret 并确认预算）
- [x] PR-13a：Omni 1.1 VideoProvider + Fake、URI/内联交付模拟测试及一次性手动付费工作流（尚未真实试片）
- [ ] PR-13b：真实 Omni 单镜头试片及端到端合成、账单实测（需用户手动触发）
- [ ] PR-09：生产级 Omni 视频任务状态记录、恢复轮询/下载和可播放性校验
- [ ] PR-10：AudioProvider（Gemini TTS）；固定角色音色 ID、对白时长和审核
- [ ] PR-11：Seedance / Kling VideoProvider 对照，真实质量盲测报告

## M3：生产与成本

- [x] PR-16a：镜头级持久化任务、Provider Task ID、幂等 SHA256、前置付费提交意图、Worker 租约、人工失败恢复和不可变事件审计（零 API 调用）
- [ ] PR-16b：真实任务调度 Worker、Google 提交/轮询/恢复接入和可验证结果（仍需费用及权限门禁）
- [ ] 镜头实际美元费用确认与供应商账单对账（不是简单填写成本估算）
- [x] PR-17：栏目/剧集/Provider 当日预算和并发预留、手工带证据费用核对、付费意图必须有额度预留（离线门禁）
- [x] PR-18：两条以上独立 Series 的有界并行 Fake Worker、镜头任务状态回写、真实 FFmpeg MP4、按镜头缓存及失败隔离（不调用云端视频）
- [x] PR-19：既有 Google Files 视频与提交过的镜头任务人工绑定、仅下载恢复、校验入库、缓存与真实 MP4 重合成（不生成新视频）
- [x] PR-20：只读多栏目/剧集任务状态及三级预算概览、异常恢复告警（内部函数，无公开接口）
- [x] PR-21：独立本地 MP4 内容寻址存储、镜头/成片归属账本、SHA256 与文件检验、跨剧集隔离和重复发布（无云端存储）
- [x] PR-22：验证独立存储对象、恢复到全新工作目录、从已完成镜头无付费重新合成分集（本地，非云端）
- [x] PR-23a：R2/S3 私有对象存储 SDK Adapter + FakeS3 回归、条件写入/全量 SHA256 上传后验收、远程恢复、本地审计（默认关闭，未连真实账户）
- [x] PR-24：人工单次 R2/S3 私有 Bucket 冒烟测试工作流、原创技术 MP4 上传/读取完整验证、失败禁用默认模式（仅 Fake 已测试）
- [ ] PR-23b：真实 R2/S3 私有 Bucket 连通性、最小权限与加密策略外部验证（需操作者配置凭证）、签名下载及受鉴权工作人员权限检查
- [x] PR-25：Google Drive 用户 OAuth、MP4 分剧集上传/下载、哈希回读、FakeDrive 测试和独立 Drive 文件账本（未连接真实用户 Drive）
- [x] PR-26a：本机 OAuth 引导、应用创建专用 My Drive 根文件夹、手动 GitHub Actions 单 MP4 上传下载验收入口与 FakeDrive CI（尚未连接真实用户账户）
- [x] PR-26b：用户手动 OAuth 授权并成功运行真实 Google Drive 单 MP4 上传、下载、SHA256 验收（2026-10-13，GitHub Actions #38263456798）
- [x] PR-29：Drive 双向验证完成的 MP4 文件 ID、剧集/分集/镜头归属、SHA256 安全映射到专用 Turso 元数据表（仅离线兼容测试，未连接真实 Turso）
- [x] PR-30a：引擎区分、严格独立数据库域名与只读 Turso 连通性手动 GitHub Actions 工作流（仅离线 Fake 测试）
- [x] PR-30b：用户已新建 Sydney 区域的专用 libSQL 数据库、配置两项专用 GitHub Secrets，并通过手动真实只读验收（[Actions #38277564945](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38277564945)：`reachable=true`、`read_only=true`、`database_modified=false`、`metadata_table_exists=false`）。工作流仅执行 SELECT，**不能据此声称所用 Full Access Token 被限制为只读，或已验证远端写入**。
- [x] PR-30c：一次私有测试 2 秒 MP4 → Drive 上传、下载 SHA256 验证 → 短剧专用 Turso `drama_drive_receipts_v1` 建表、单条 INSERT、完整 SELECT 回读。**已完成真实验收**：[Actions #38279948391](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38279948391)，`turso_metadata_inserted=true`、`turso_full_row_readback_verified=true`、`uploaded_mp4_count=1`、`new_ai_model_generation_calls=0`。这次一次性测试授权已用完，**不得重复触发**；生产 SQLite 仍未迁移。详见 [TURSO_PR30C_WRITE_CANARY](TURSO_PR30C_WRITE_CANARY.md)。
- [ ] PR-31：旧 SQLite 生产任务/审批/预算完整迁移及远端交易、幂等与并发验收（未实现）
- [ ] PR-24：正式云端持续 Worker 与 Google 视频任务 ID 调度（仍需付费审批）
- [ ] 后续 PR：受鉴权的工作人员任务列表与审片工作台、按生产线可视化调度
- [ ] 后续 PR：正式付费 Worker 的请求前持久化、供应商任务句柄对接、自动轮询与受控预算实测
- [ ] 正式调度 Worker 与供应商任务/账单/授权接入（真实视频自动化批量生产仍未实现）
- [ ] 真实多 Worker 调度、按单集和每日预算告警、Provider 账单自动核对与失效凭据管理（仍需鉴权与正式调度环境）
- [ ] PR-14：自动 QA（解码、字幕音长、演员视觉一致性提示及人工审批）

## M4：后期成片

- [x] PR-12：本地视频素材导入、逐镜替换/缓存与统一规格编码（支持 MP4/MOV/WEBM/MKV，零 AI 费用）
- [x] PR-11：离线 Story Bible → 剧本/审核 → 镜头技术卡片 → FFmpeg H.264/AAC/字幕轨 → 可播放 MP4 + QA + 单镜头缓存（无 AI 视频/配音）
- [ ] PR-15：正式镜头的 FFmpeg 音画规范化、双轨混音、字幕、片尾和交付 MP4
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