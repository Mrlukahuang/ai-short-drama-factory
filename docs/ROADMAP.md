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
- [ ] PR-31：旧 SQLite 生产任务/审批/预算完整迁移及远端交易、幂等与并发验收（**尚未实施，禁止真实切换**）。
  - [x] PR-31a：完成离线只读源数据库体检、未完成租约/预算/供应商提交状态阻断、安全迁移分期计划；不读取真实 Turso 数据，不开放迁移入口。详见 [PR31_MIGRATION_READINESS](PR31_MIGRATION_READINESS.md)。
  - [x] PR-31b0：为**现有本地 SQLite** 新增真实并行 Worker 抢单、并行预算预留和故障回滚基准测试（与真实 Turso 并发测试不同）。
  - [x] PR-31b1：离线交易后端接口 `LedgerBackend` 与仅限本地 sqlite3 的候选适配器，使用现有镜头/预算业务函数重新执行并发安全回归；**不是远端 Turso 验证**。
  - [x] PR-31b2a（仅离线代码）：为单独新建的 `ai-short-drama-factory-txlab` 提供严格隔离的手动 libSQL 事务回滚、双独立连接竞争和唯一约束工作流，Fake CI 已准备；**新实验库、独立两项 Secret 和真实一次写入均尚待用户配置/授权**，原短剧 Turso 禁止使用。详见 [PR31_LIBSQL_TXLAB](PR31_LIBSQL_TXLAB.md)。
  - [x] PR-31b2b（真实诊断阶段）：独立 TxLab 一次真实双连接事务测试 [Actions #38342320367](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38342320367) **失败**；后续两次只读 [#38358995649](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38358995649) / [#38362170364](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38362170364) 成功确认实验表中一条记录计数=1，**未通过真正并发事务验收**，不可据此迁移。
  - [x] PR-31b2c（离线安全修复）：已用尽的一次性 TxLab 写入工作流锁止；未来写入失败提供安全的事务阶段/类别枚举并有 Fake SQLITE_BUSY 回归，无新的云端写入。
  - [x] PR-31b2d（仅离线）：复现本地两连接 `BEGIN IMMEDIATE` 非等待锁冲突，确认单次提交不等于数据库丢失更新；定义只有证实前置锁拒绝时可考虑一次有界重试、所有 COMMIT/网络结果不明禁止自动重发的纯判定契约。
  - [x] PR-31b2e（仅离线开发）：隔离 TxLab v2 事务探针，分开验证无竞争串行提交与并发写锁争抢，只计入已确认提交；新手动 Workflow 默认锁止，尚未再次真实写入。
  - [x] PR-31b2f（真实 TxLab v2 单次运行已结束，**未通过并发事务验收**）：经明确授权启动 [Actions #38380555425](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38380555425)，第一次执行历史门禁通过、真实事务步骤在 `worker_read / busy` 失败；部分测试数据可能已提交，禁止重跑。
  - [x] PR-31b2g（仅离线安全诊断代码）：现有 TxLab SELECT-only Workflow 扩展至 v2 技术表，仅回传 0/1/2/3/4/other 汇总计数、无身份/Token/SQL 写入；真实 v2 状态仍待一次新的只读报告核实。
  - [x] PR-31b2h（真实只读对账 + 离线候选）：[Actions #38383515455](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38383515455) 已核实 v1=1、v2=3；v2 两次串行加一次并发提交持久化、另一并发在 worker_read/busy 阶段失败，**未通过完整远端并发验收**。本地 16 线程原子条件 UPDATE/RETURNING 对比候选完成，不自动远程重试、不替换生产账本。
  - [x] PR-31b2i（纯离线生产业务原子性基线）：直接复用现有镜头/三级预算/提交意图/人工对账函数，注入审计失败及第二表更新失败、双审核员争抢同一费用；要求任务、费用与审计同提交或同回滚。**只证明本地 SQLite，不代表远程 Turso 验收**。详见 [PR31_LEDGER_MULTITABLE_CONTRACT](PR31_LEDGER_MULTITABLE_CONTRACT.md)。
  - [x] PR-31b2j（仅本地只读）：检查真实镜头/预算账本关键表、提供商 Task ID 的非空唯一索引、同镜头唯一预留、5 条外键和四个 append-only 审计触发器；损坏或遗漏一律阻断，输出脱敏 Schema 指纹。**尚未执行远端 Turso Schema 导入/验证**。详见 [PR31_CRITICAL_SCHEMA_GUARD](PR31_CRITICAL_SCHEMA_GUARD.md)。
  - [x] PR-31b2k（仅离线 v3 兼容性准备）：学习官方 libSQL/Turso 引擎与事务差异；新增以 `pr31_v3_*` 为隔离前缀的五表、外键/部分唯一索引、审计触发器和多表核销回滚测试；验证 COMMIT 回执丢失不自动重发。严格只新建临时本地文件，**没有真实 TxLab v3 运行或新写入授权**。详见 [PR31_TXLAB_V3_MULTITABLE_PLAN](PR31_TXLAB_V3_MULTITABLE_PLAN.md)。
  - [x] PR-31b2l0（真实 SDK 本地合同）：审阅 libsql-python `0.1.11` 源码、特别防范 `executescript` 未抛错误/连接未显式关闭/foreign_keys 按连接生效；新增**真实 libSQL Python 二进制，仅本地 SQLite 文件**的第四项 CI，覆盖 5 表 DDL、三次跨表回滚、COMMIT 后独立连接读回、外键/唯一索引/审计触发器和 ACK 丢失不重放。只安装 SDK、不用任何 TxLab Secrets、不接触远端。详见 [PR31_LIBSQL_SDK_SOURCE_REVIEW](PR31_LIBSQL_SDK_SOURCE_REVIEW.md)。
  - [x] PR-31b2l1（仅离线准备）：增加隔离 v3 五表事务候选执行器、逐条 DDL + Schema 回读、FK/唯一索引/审计约束、提交后独立连接核对和失败不自动重试；独立手动 Workflow **if:false 锁止**，当前没有 v3 云端写入授权。详见 [PR31_TXLAB_V3_EXECUTION_GATE](PR31_TXLAB_V3_EXECUTION_GATE.md)。
  - [x] PR-31b2l2（仅离线、只读代码）：现有 TxLab SELECT-only 检查提前扩展 v3，核实零/部分/全部十个预期对象，以及临时预算/任务费用/审计**汇总**；即使写入半途失败也不补建、不重试、不泄露行 ID 或密钥。所有真实 v3 写入仍未获新授权。
  - [x] PR-31b2l3（授权/解锁阶段历史记录）：仅启用独立 TxLab v3 首次人工调用与 Actions 运行历史门禁；当时尚未执行的描述已经被以下 PR-31b2l 真实验收结果更新。详见 [PR31_TXLAB_V3_EXECUTION_GATE](PR31_TXLAB_V3_EXECUTION_GATE.md)。
  - [x] PR-31b2l（**真实远端隔离多表验收已通过**）：单次授权 [Actions #38417337745](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38417337745) 返回 `isolated_v3_lab_verified=true`、10 个新实验 Schema 对象、跨表回滚/提交后独立连接读回、FK/部分唯一/append-only 审计约束均通过；`remote_multiworker_concurrency_verified=false`、`full_production_schema_verified=false`、`live_cutover_permitted=false`。此次授权已消耗。
  - [x] PR-31b2l4（安全收尾）：单次真实 TxLab v3 成功后，**硬锁止**旧手动写入工作流，固定真实报告和未验收边界，防止重复运行/误报迁移完成。
  - [x] PR-31b2m（离线生产差距门禁）：以真实 [TxLab v3 Actions #38417337745](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38417337745) 通过的五表串行合同为基准，新增**本地只读**完整生产 Schema/额外云资产/Drive 审计、租约/预算政策等结构与运行状态差距评估；生产 Schema 远端导入、多 Runner 并发、网络 ACK 丢失、资产恢复及迁移回滚继续标记未验收。详见 [PR31_PRODUCTION_V3_GAP_MATRIX](PR31_PRODUCTION_V3_GAP_MATRIX.md)。
  - [x] PR-31b2n（仅离线真实 SDK 子集）：从**现有 db.SCHEMA** 中提取九张实际业务表、六个索引、四个审计触发器，在真正 `libsql==0.1.11` 本地 SDK 中逐条 CREATE 并执行真实业务字段的三步核销回滚和外键/唯一/不可变事件测试。明确证实 SDK `fetchone()` 的 tuple 与现有 `row["status"]` 不兼容，必须先有独立 Row 适配器；**无远端真实验证、生产迁移仍关闭**。详见 [PR31_REAL_LEDGER_LIBSQL_SDK_CONTRACT](PR31_REAL_LEDGER_LIBSQL_SDK_CONTRACT.md)。
  - [x] PR-31b2o0（离线 native libSQL Row/Transaction 适配器）：对真实 SDK tuple 结果按 Cursor description 转换为支持列名/整数的只读 Mapping，重复同名列或非测试标记的数据库直接拒绝；在真实 SDK 本地测试库里复用现有镜头领取、三级预算预留、提交意图及费用核销业务函数并注入审计故障，验证回滚；**不改生产 Worker、不连接远端**。详见 [PR31_LIBSQL_LOCAL_ROW_ADAPTER](PR31_LIBSQL_LOCAL_ROW_ADAPTER.md)。
  - [x] PR-31b2o1（仅真实 SDK 本地试验）：在专用临时数据库运行已有镜头 Worker 8 线程争抢、两 Worker 三级预算上限 0.60 美元竞争，以及实际 SDK COMMIT 已持久化但回执丢失的模拟。核实审计/幂等与禁止自动重试，未知异常不掩盖。**仍不是远端 Turso/跨 Runner 验收**。详见 [PR31_NATIVE_SDK_LOCAL_CONCURRENCY](PR31_NATIVE_SDK_LOCAL_CONCURRENCY.md)。
  - [x] PR-31b2o2（仅离线合同）：为真实 native libSQL SDK 的**隔离标记本地账本**新增 SELECT-only 脱敏恢复摘要（intent / held / reconciled / stale lease / 审计一致性）、ACK 丢失和审计失败测试，以及 attempt + worker + lease + epoch 的纯 fencing 预检查；不改变正式 Worker、无远端认证或付费授权。同期硬锁止已消耗的 v2 TxLab 手动写入入口；v1/v3 同样保持锁止。跨 Runner 的原子 CAS/生产级真实验收**尚未实现**，需新单次授权。详见 [PR31_OFFLINE_RECOVERY_AND_FENCING](PR31_OFFLINE_RECOVERY_AND_FENCING.md)。
  - [x] PR-31c0：离线 SQLite 快照→恢复至新的本地文件→完整性、结构和 SHA-256 逻辑对账；仅 Fake/本地 CI，禁止真实生产输入或云端上传。
  - [x] PR-31c1：离线三方（源库、备份、恢复副本）完整性/未结状态证据审查与源库变更检测；拟定 Durable Writer Fence、权限与回滚的明确验收契约。**没有真正停写或开放切换**。
  - [x] PR-31c2：隔离本地 SQLite 模拟持久 fencing epoch，12 个 Fake Worker 与暂停并发、事件失败回滚及旧令牌失效测试。**仅本地实验，不控制真实 Worker**。
  - [x] PR-31b2o3（仅真正 native libSQL SDK 本地）：在**带隔离 marker 的临时生产形状账本**上提供独立的 writer epoch gate，镜头领取与 attempt 递增、审计原子提交、未付费意图的 fenced CAS 更新，以及 pause/resume、同名旧 Worker、过期租约、并发和模拟 COMMIT ACK 丢失测试。**仅供离线实验，不接入当前生产 Worker、不代表跨 Runner/Turso 真实验收**。详见 [PR31_NATIVE_FENCED_JOB_ATOMIC_LAB](PR31_NATIVE_FENCED_JOB_ATOMIC_LAB.md)。
  - [ ] PR-31c3：真正跨 Runner 的持久写入闸门、恢复/权限与外部供应商计费中断验收（需另外授权）。
  - [ ] PR-31d：独立 TxLab v3 串行多表/约束已经真实通过；**完整生产 Schema 兼容、跨 Runner 并发、网络故障恢复和正式迁移/回滚仍未验证**，需要后续分阶段明确授权，生产切换继续关闭。
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