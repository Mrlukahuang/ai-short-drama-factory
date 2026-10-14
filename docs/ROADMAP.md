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
- [x] PR-07b1（**仅本地离线审片子阶段**）：Streamlit 新增基于当前栏目/剧集 Production 的离线 MP4 生成和本地播放器；每次先核对单剧集归属、DB 与磁盘 manifest、原 MP4/缓存哈希、字幕和完整 FFmpeg 技术 QA，禁止路径跨越/符号链接；绝不代表 AI 真实画面或发行许可。**未实现鉴权、上传/资产编辑、公网部署、真实收费媒体 Worker**。详见 [PR07B1_LOCAL_OFFLINE_REVIEW](PR07B1_LOCAL_OFFLINE_REVIEW.md)。
- [x] PR-07b2（**仅本机人工原创分镜→制作审批交互流程**）：Streamlit 新增「分镜与审批」页，使用本剧现有 Story Bible/演员/场景创建人工编辑草稿、严格服务端 Screenplay 校验、SHA256 失效检查和人工确认后提交 Episode；随后分别复核剧本与人物并推进既有 Production 状态机，再交给 PR-07b1 离线 MP4 审片。包含零付费真实 API→FFmpeg→QA 集成测试；**仍不是真实 AI 成片、公网认证或发行审批**。详见 [PR07B2_LOCAL_STORY_WORKFLOW](PR07B2_LOCAL_STORY_WORKFLOW.md)。
- [x] PR-07b3（**可视化逐镜头分镜编辑子阶段**）：Streamlit 默认提供逐镜长短、动作、摄影方式、本剧演员/场景、连续性与多对白行的表单和可编辑时槽；纯 Python 合同保护镜头 ID/顺序/对白和 90s 本机技术预览长度，应用修改会使旧人工验证失效。高级 JSON 编辑保留。**无真实 AI 画面、用户鉴权/公网部署或付费调用**。详见 [PR07B3_VISUAL_STORYBOARD_EDITOR](PR07B3_VISUAL_STORYBOARD_EDITOR.md)。
- [x] PR-07b4（**本地导演时间轴与连续性提示，非发布门禁**）：在可视化分镜页增加从已应用草稿读取的镜头/对白分轨整数秒时间轴，标明实际指定时槽与离线均分时槽；只读提示相邻镜头状态文本变化、草稿占位、场景/出镜演员更换及未定时对白超长。修复嵌套 Streamlit Expander。**无自动断言穿帮、无剧本修改/审批、无真实 AI 画面或收费调用**。见 [PR07B4_DIRECTOR_TIMELINE](PR07B4_DIRECTOR_TIMELINE.md)。
- [x] PR-07b5（**本机原创镜头视频登记→现有 MP4 渲染**）：Streamlit「本机审片」可上传并绑定本剧已审批 Production 镜头的本地 MP4/MOV/WEBM/MKV（每段≤32 MiB），明确自述版权确认、哈希存储、逐镜哈希+媒体重验和按镜头恢复，交由现有 FFmpeg 渲染器生成混合**真实提供的视频画面与占位**的技术 MP4。没有公网媒体服务、抗病毒沙盒、独立许可核验或真实 AI 生成，不代表 PR-07b 整体完成。见 [PR07B5_LOCAL_SHOT_MEDIA_WORKBENCH](PR07B5_LOCAL_SHOT_MEDIA_WORKBENCH.md)。
- [x] PR-07b6（**本机演员、场景、道具资产版本参考图库**）：Streamlit 追加素材可视化上传/缩略图，限制 8MiB JPEG/PNG/WEBP 和 1200 万像素，Pillow 仅存去 EXIF/GPS 等元数据的缩放 RGB PNG；将 SHA256 收据不可覆盖地绑定至本剧资产 ID/版本/规格哈希，每次展示重新核验，拒绝跨剧、声样、非法文件和符号链接。**仅操作者自述素材权利，未接真实收费模型或独立版权认证/公网上传服务。**见 [PR07B6_LOCAL_ASSET_REFERENCE_GALLERY](PR07B6_LOCAL_ASSET_REFERENCE_GALLERY.md)。
- [x] PR-07b7（**本机导演逐镜参考图明确选择及相邻镜头对照**）：按精准 Screenplay 指纹 + Series/Shot/Asset 版本选择已登记图片，手动确认原子持久化；相邻镜头同一资产版本选择不同图或缺失给出非权威人工复查提示，图片每次读取重新验证归属与 SHA256；道具仅做导演注释，不修改既有剧本及发布许可。无模型调用或公网服务。见 [PR07B7_SHOT_REFERENCE_DIRECTOR_BOARD](PR07B7_SHOT_REFERENCE_DIRECTOR_BOARD.md)。
- [x] PR-08a：Google Nano Banana 2.1 受控 SDK Provider + Fake + 门禁测试；未实际调用、未存储媒体、尚无参考图条件输入
- [x] PR-09a：手动单张 Google 图片冒烟测试工作流、私有 Secret 和零调用默认模式；**真实 API 调用尚未执行**
- [ ] PR-08b：Google 图片生成端到端真实试片、参考图载入、审核后保存资产版本（需用户设置 Secret 并确认预算）
- [x] PR-13a：Omni 1.1 VideoProvider + Fake、URI/内联交付模拟测试及一次性手动付费工作流（尚未真实试片）
- [ ] PR-13b：真实 Omni 单镜头试片及端到端合成、账单实测（需用户手动触发）
- [ ] PR-09：生产级 Omni 视频任务状态记录、恢复轮询/下载和可播放性校验
- [x] PR-10a（**离线 FakeDialogueAudioProvider**）：新增 Series 内版本化 Voice Asset 与来源同意记录门禁、Production 审核、镜头已批准台词逐字核验、可验证 48kHz PCM WAV 正弦时间占位音、SHA256 幂等内容缓存与破损重建，输出直连 PR-15b 视频混音与技术 QA；真实 Gemini TTS 入口继续硬拒绝、收费调用 0，不能视为真人配音或声音版权最终授权。详见 [PR10_FAKE_DIALOGUE_AUDIO](PR10_FAKE_DIALOGUE_AUDIO.md)。
- [x] PR-10b（**离线逐镜 FakeVoice 整集音轨**）：从审核过的 Production、Series 内音色资产/来源同意记录出发，按镜头逐字核对批准台词、版本和时长，生成 SHA256 幂等 Fake WAV，合成不超过 90 秒的完整单声道 PCM 时间线；再与本地合成背景音经 PR-15b 混音、PR-14 QA，FFmpeg CI 实际编码并上传 60 秒 MP4 技术样片。严格要求每镜一行台词，其余复杂对话拒绝；**并非真实 TTS/演员声音/声线商用授权**，收费 0。详见 [PR10_EPISODE_FAKE_VOICE_TIMELINE](PR10_EPISODE_FAKE_VOICE_TIMELINE.md)。
- [x] PR-10c（多角色**离线测试音**）：人工审核的 Screenplay 将有序 `dialogue_cues`（actor_id + 原台词）同步存到 EpisodeDraft，防止丢失说话人身份；新多角色 Fake PCM 时间线根据演员绑定的同剧集声音资产、版本/同意记录、精确台词和句序逐条检查，再按整数秒槽拼接每镜多句、无声镜头静音与 60 秒真实 FFmpeg MP4，继续使用全片 QA。多声线文本不是口型同步或真实 TTS，不能自动商用发行。详见 [PR10_MULTI_ACTOR_FAKE_TIMELINE](PR10_MULTI_ACTOR_FAKE_TIMELINE.md)。
- [x] PR-10d（**导演审核精确对白时槽，离线 PCM**）：为多角色 ShotDraft 的有序台词加入可选 `start_second/end_second` 整秒起止，审批和持久 EpisodeDraft 双重拒绝部分填写、时间重叠、越界或乱序；未填写的旧剧本保留原平均分配。新 Fake 多角色时间线遵循批准的开始/结束，实际插入 PCM 静音空档并把时槽纳入 SHA256 缓存，CI 对 60 秒样片逐帧检查多段静音、有声片段、整轨长度和最终 MP4 QA。仍非真实 TTS、毫秒级 lip-sync 或发行授权。详见 [PR10_APPROVED_CUE_TIMING](PR10_APPROVED_CUE_TIMING.md)。
- [x] PR-10e（**Gemini 3.8 TTS 官方格式离线合同，真实提交保持关闭**）：根据 Google 当前 Interactions API 规范准备仅内存中的单角色已批准台词/声线请求、SHA256 幂等指纹和 <=2 USD 自我承诺（非供应商硬上限）；校验模拟 API 的 Base64 unary 24kHz mono 16-bit RIFF WAV 格式及时长，走既有 FFmpeg 混音/字幕 QA。**从未实际调用 Google TTS**，`GeminiDialogueAudioProvider` 仍硬拒绝；正式计费前必须补真实提交与任务恢复/账本、声线许可。详见 [PR10_GEMINI_TTS_DRY_RUN](PR10_GEMINI_TTS_DRY_RUN.md)。
- [x] PR-10f（**真实 Gemini 3.8 Flash-Lite TTS 一次性成功，授权消耗**）：2026-10-14 [Actions #38525869818](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38525869818) 已真实调用 Google `gemini-3.8-flash-lite-tts` 一次，固定原创虚构英文短句、预设 Kore 声音，收到 **3.56 秒**有效 24kHz mono PCM WAV，SHA256 为 `5a314b80d25cc9baa33939499b96de77574e0fdbea56a541fbf9a8cb8ce7db10`，私有 [WAV Artifact #11875741551](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38525869818/artifacts/11875741551) 保留 3 天。确认一次请求、没有用户原文、没有生产数据库；**未核实 Google 实际账单和硬成本上限、真人声音许可或商业发布**，不能作为多角色真实 TTS 生产验收。原 Workflow 随后 `if:false` 永久硬锁，严禁重跑。详见 [PR10_ONE_USE_TTS_CANARY](PR10_ONE_USE_TTS_CANARY.md)。
- [x] PR-10g（**离线逐句 TTS 持久化付费意图与三层预算联控**）：新增本地 SQLite 的 `tts_tasks`/`tts_budget_reservations`/不可改写事件审计；已审核 Series/镜头/演员/声音资产/精确 cue 指纹唯一。与现有视频生成预算共同占用 Column/Series/Provider 日额和并发数；先原子预留再提交一次性 paid intent，回执不明隔离且保留额度，不允许再发第二次；已有供应商 ID/WAV 只读登记与人工发票凭证核对均不授权商用。**离线 Fake 合同，无 Google SDK 调用、无真实账单或生产 DB 切换**。参见 [PR10_TTS_PERSISTENT_INTENT](PR10_TTS_PERSISTENT_INTENT.md)。
- [x] PR-10h（**TTS 最终回执二次验证**）：在本地 SQLite `tts_tasks` 的已确认 SDK interaction 写入 WAV hash/时长前，重新独立解析准确的 Base64/24k mono 16bit PCM WAV 原始字节，拒绝伪造 `InspectedGeminiSpeech` 对象、错误采样率、超时长或假元数据；供应商 interaction ID 跨 Cue 唯一，重复绑定明确拒绝并回滚。强制 CI 与真实 Fake 响应格式测试验证，**不产生额外付费模型调用**。参见 [PR10_TTS_RECEIPT_TAMPER_AUDIT](PR10_TTS_RECEIPT_TAMPER_AUDIT.md)。
- [x] PR-10i（**严格离线 TTS 一次性 Fake 编排**）：复用 PR-10g/h 的已审核逐句请求与共享三级预算，原子提交不可重用付费意图后仅允许一次本地 Fake SDK 调用；成功登记唯一 Interaction ID、经再次核验的 24k PCM WAV hash；ACK 丢失/非法或重复 ID 保留 held 额度并隔离，已 ACK 但音频损坏保留 acknowledged 等待人工恢复。双线程争抢只允许一个进入 Fake 调用；任意真实 Google SDK/HTTP 客户端均禁止。**不接触真实 Google 或云数据库、不表示真正跨 Worker 计费恢复完成**。参见 [PR10_FAKE_DISPATCH_RECOVERY](PR10_FAKE_DISPATCH_RECOVERY.md)。
- [x] PR-10j（**TTS 崩溃后只读对账和恢复分类**）：使用同一本地 SQLite 读取事务独立交叉校验 `tts_tasks`、三级预算 reservation、不可变审计事件序列和唯一 Provider ID/WAV SHA256，明确分开“尚未提交”“持久付费意图但结果未知”“ACK 丢失隔离”“已有 Interaction 只需取回原结果”“WAV 已验但账单/权益待核”。伪造 ID/哈希/发票/遗漏预算/乱序审计一律 fail closed；不返回任何私人台词或账单凭证，**永远无自动重试和远端调用**。详见 [PR10_TTS_READONLY_RECOVERY](PR10_TTS_READONLY_RECOVERY.md)。
- [x] PR-10k（**已 ACK 的原始 TTS 音频安全恢复，严格离线 Fake**）：对持久 `acknowledged` + 原 Provider Interaction ID、原 held/reconciled 费用记录进行只读取回模拟；重新确认 ID 完全相同、24k mono PCM WAV/时长和最终持久元数据二次验收，成功标记 verified。超时、错 ID、损坏 WAV 一律保持已有 ACK 与预算，不请求第二次付费生成；原 `quarantined`/未知 ACK 不能伪装已确认 ID 进行恢复。只接受确切 Fake 类、没有真实 Google SDK/网络请求或商业发布许可。详见 [PR10_EXISTING_AUDIO_RECOVERY](PR10_EXISTING_AUDIO_RECOVERY.md)。
- [x] PR-10m（**整集 TTS 只读恢复清单**）：在一个本地 SQLite 读事务中逐个核对已审核 Episode 的所有 `shot_id + cue_index`、持久 TTS 任务、三级预算预留与不可变审计链；任何缺少句子、未知分镜、审计伪造会整集 fail-closed。输出仅脱敏数量及未知 ACK/既有音频回读分类，始终禁止自动重发、发布和生产切换。没有 Google 真实调用。详见 [PR10_EPISODE_RECOVERY_TRIAGE](PR10_EPISODE_RECOVERY_TRIAGE.md)。
- [x] PR-10n（**原始 Google Interactions GET 的纯离线合同**）：核实官方 `interactions.get(id=...)` 与交互存储保留期；新增仅 exact Fake 可调用的原始持久 ID 单次 GET、已 ACK 状态/预算/审计只读核对、WAV 二次格式校验、重用音频拒绝和全套权限/失效/超时回归。**真实 Google GET、账号/项目归属、权限、真正音频可恢复性仍未实测**，不持久化新结果、不允许付费提交、原 canary 继续硬锁。详见 [PR10_GOOGLE_ORIGINAL_GET_CONTRACT](PR10_GOOGLE_ORIGINAL_GET_CONTRACT.md)。
- [x] PR-10o（**本地 TTS 原始 Google 项目/身份指纹不可变绑定**）：新建仅离线 `tts_google_origin_scopes` 一任务一行，只有 `prepared` 状态可登记非秘密原始项目/主体引用摘要，数据库触发器禁止覆盖/删除；PR-10n Fake 原 ID GET 进一步要求记录与读取 Fake 的两个上下文指纹严格相符，旧无绑定任务和串号前置阻断。**来源仍只是不可信本地声明，真实凭据/项目身份、Google GET/账单、生产账号权限均未验收**，无联网和付费。详见 [PR10_GOOGLE_ORIGIN_SCOPE](PR10_GOOGLE_ORIGIN_SCOPE.md)。
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
  - [x] PR-31b2o4（真实 native libSQL SDK 的本地隔离账本）：在同一个临时 SQLite 事务内校验 writer epoch/attempt/租约和栏目、剧集、Provider 三级预算，原子完成 held 预留、预算审计、镜头生成意图与镜头/gate 审计；验证同额度并发竞争、过期 token、审计回滚与 COMMIT 回执丢失不重试。**只验证本地，未开启收费请求与远端跨 Runner**。详见 [PR31_NATIVE_FENCED_BUDGET_INTENT](PR31_NATIVE_FENCED_BUDGET_INTENT.md)。
  - [x] PR-31b2o5（仅真实 native SDK 的隔离本地模拟回执）：带标记的测试 SQLite 上校验真正持久的付费意图/held 预算事件后，用 **SYNTHETIC_ Task ID** 做 Worker attempt+epoch+租约条件回填、同供应商 Task ID 唯一、防旧 Worker 抢写和 COMMIT 回执丢失不重放。没有真实供应商请求/账单/远端测试或生产切换。详见 [PR31_NATIVE_SYNTHETIC_TASK_FENCING](PR31_NATIVE_SYNTHETIC_TASK_FENCING.md)。
  - [x] TxLab v4（**真实远端隔离子集验收通过、单次授权已消耗**）：2026-10-14 [Actions #38505044059](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38505044059)，首次/唯一 workflow_dispatch、run_attempt=1、success；远端回执 `isolated_v4_lab_verified=true`，`schema_objects_verified=22`、`synthetic_three_scope_budget_held=true`、`synthetic_claim_intent_task_atomic=true`、`rollback_and_independent_readback_verified=true`、`local_or_serial_epoch_pause_verified=true`。**并非完整生产 Schema、跨 Runner、多 Worker 或网络 ACK 恢复验收**，生产未迁移，Provider 收费调用 0。此轮将 v4 手动工作流 `if:false` 硬锁止，禁止再次远端写入。详见 [PR31_TXLAB_V4_ONE_USE_REAL_SCHEMA_SUBSET](PR31_TXLAB_V4_ONE_USE_REAL_SCHEMA_SUBSET.md)。
  - [x] PR-31c3a（**仅离线跨进程**）：使用真正 `libsql==0.1.11` SDK、不同 Python OS 进程及已标记的同一临时 SQLite 测试文件验证镜头抢领、三级预算并发上限、pause/旧 epoch 失效、真实 COMMIT 前后强制进程崩溃及只读对账、pause/intent 竞争；**不代表多台 GitHub Runner、远端 Turso 网络事务或生产权限验收**，四个已消耗 TxLab workflow 保持锁止。详见 [PR31_NATIVE_MULTIPROCESS_FENCING](PR31_NATIVE_MULTIPROCESS_FENCING.md)。
  - [x] PR-31c3b（仅本地 SELECT-only，零远端网络）：追加暂停恢复前的 `quiescence` 检查，独立只读事务交叉核对 writer epoch/audit、旧租约、未清付费意图、Provider Task ID、held 预算与账本异常；即使全部通过也不自动授权真实 Worker 恢复/付费请求/生产切换。详见 [PR31_OFFLINE_WRITER_QUIESCENCE](PR31_OFFLINE_WRITER_QUIESCENCE.md)。
  - [x] PR-31c3c：v5 候选协议的**纯离线 720 种执行顺序穷举**（双 Worker、合成预算、模拟 Task ID、pause/resume）+ **30 个实际 libsql 0.1.11 本地事务顺序差分测试**；逐步断言 audit、预算、epoch、Task 和旧 Worker 失效。**既不是两台远端 GitHub Runner，也没有 Turso v5 写入授权**。详见 [PR31_V5_OFFLINE_SCHEDULE_ORACLE](PR31_V5_OFFLINE_SCHEDULE_ORACLE.md)。
  - [x] PR-31c3d（仅离线合成证据合同）：未来 TxLab v5 的双 Runner 实验须具备**两个不同 GitHub job/同一首次 run、同一批次摘要、第三个只读观察者、预算/意图/epoch 审计、没有重复 Task 和模糊 COMMIT**等完整记录；拒绝伪造或不一致输入，**即使结构完整也不能自行把 `remote_multi_runner_verified` 置为 true**。没有云端连接或写入、没有 v5 自动工作流。详见 [PR31_V5_DUAL_RUNNER_EVIDENCE_CONTRACT](PR31_V5_DUAL_RUNNER_EVIDENCE_CONTRACT.md)。
  - [ ] TxLab v5（**单次远端写入已执行、授权已消耗，终验尚未通过**）：2026-10-14 [Actions #38509779430](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38509779430)，main 首次 push/run_attempt=1；setup 已在隔离库建 6 个新 `pr31_v5_*` 对象，actor-a **denied**、actor-b **accepted**（GitHub Job IDs 分别 115675529609 / 115675529344），seal 已成功暂停 epoch；第三独立 `v5-observer-read-only` 因 `stage=observe, category=unknown` 失败（Job 115675757454），本次原始 workflow **failure，不能宣称原 v5 工作流完整成功**；但另一次全新 SELECT-only 诊断 [#38510686538](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38510686538) 已独立确认 gate=paused/epoch2、ready=2、held=1、intent_audit=1、gate_audit=1、pause_audit=1、FK/读事务快照全部一致。诊断发现远端 `PRAGMA query_only=ON` 不兼容（`query_unavailable`），是原观察者失败的强相关线索。真实**预算竞争及最终状态获得分离的独立只读证据**，但服务端时钟、网络丢失 COMMIT、只读最小权限与生产迁移仍未验收。禁止重跑。立刻将 v5 Workflow `if:false` 永久锁止，后续只允许新的受控 SELECT-only 诊断并独立审查其权限，不得重写 v5 表。免费预算上限此前预计 <$2，实际账单未查询。详见 [PR31_TXLAB_V5_DUAL_RUNNER_PLAN](PR31_TXLAB_V5_DUAL_RUNNER_PLAN.md)。
  - [x] PR-31v5只读诊断（**成功，授权已消耗并锁止**）：2026-10-14 [Actions #38510686538](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38510686538) 真实隔离库固定 SELECT/PRAGMA 检查，`ledger_probes_consistent=true`；`query_only_pragma=query_unavailable`，其他全部 `ok`（包括新只读事务快照与外键）；`additional_remote_writes=0`、`paid_provider_calls=0`。专用诊断 Workflow 随后改为 `if:false`，不能再触发；原 v5 写入 Workflow 不得重跑。
  - [x] PR-31v5c：基于真实远端只读诊断证据修正 v5 独立 Observer 的 SQL 兼容性：不再调用远端不支持的 `PRAGMA query_only=ON` 或参数设置，而以固定 `BEGIN`、`SELECT`、`PRAGMA foreign_key_check` 完成可复核只读快照，保留完整外键、预算、审计和回执核验；**不声称只读数据库凭据已验证，也不重开已消耗 v5 Workflow**。本地 SQLite 和 pinned native SDK 都有拒绝连接参数/DML 的回归测试。详见 [PR31_V5_OBSERVER_COMPAT](PR31_V5_OBSERVER_COMPAT.md)。
  - [ ] PR-31c3：真正跨 Runner 的持久写入闸门、恢复/权限与外部供应商计费中断验收（需另外授权）。
  - [ ] PR-31d：独立 TxLab v3 串行多表/约束已经真实通过；**完整生产 Schema 兼容、跨 Runner 并发、网络故障恢复和正式迁移/回滚仍未验证**，需要后续分阶段明确授权，生产切换继续关闭。
- [ ] PR-24：正式云端持续 Worker 与 Google 视频任务 ID 调度（仍需付费审批）
- [ ] 后续 PR：受鉴权的工作人员任务列表与审片工作台、按生产线可视化调度
- [ ] 后续 PR：正式付费 Worker 的请求前持久化、供应商任务句柄对接、自动轮询与受控预算实测
- [ ] 正式调度 Worker 与供应商任务/账单/授权接入（真实视频自动化批量生产仍未实现）
- [ ] 真实多 Worker 调度、按单集和每日预算告警、Provider 账单自动核对与失效凭据管理（仍需鉴权与正式调度环境）
- [x] PR-14a（纯离线**技术**质量验收）：新增 MP4 文件哈希、FFmpeg 完整音视频解码、H264/AAC/mov_text、逐镜 SRT sidecar 时间对齐、披露标签与不可冒充真 AI 视频/真人对白/已审核发布的只读 QA。第四个强制 FFmpeg CI 执行本地成片实际 QA；不自动改 production 状态或生成任何外部请求。详见 [PR14_OFFLINE_TECHNICAL_QA](PR14_OFFLINE_TECHNICAL_QA.md)。
- [x] PR-14b（本地实际成片门禁）：将 PR-14a 技术质检真正接入 `render_approved_preview`：MP4 完整解码、哈希、字幕对齐全部通过**之后**才允许更新 `productions.status=offline_preview_finished` 并记录 `technical_qa`；质检失败不改 DB 状态、不发布 manifest，不调用供应商；技术通过也仍需人工审核，不代表真人视频/正式上线。新增真实 FFmpeg 故障注入回归测试。详见 [PR14_OFFLINE_TECHNICAL_QA](PR14_OFFLINE_TECHNICAL_QA.md)。
- [x] PR-14c（离线逐镜缓存内容完整性）：缓存镜头不仅须可解码/时长正确，还必须与独立持久的 SHA256 marker 匹配才可复用；缓存丢失 marker 或被**其他仍可播放的视频替换**时安全重建指定镜头，其他镜头仍命中缓存。预览 manifest 增加逐镜 `clip_sha256`，最终 QA 独立验证本地 clip 内容，测试用真实 H264/AAC 视频互换模拟缺陷。此 marker **不能替代签名、访问控制或对抗可同时篡改文件/marker 的攻击者**，不涉及外部供应商。详见 [PR14_OFFLINE_TECHNICAL_QA](PR14_OFFLINE_TECHNICAL_QA.md)。
- [ ] PR-14：自动 QA（解码、字幕音长、演员视觉一致性提示及人工审批）

## M4：后期成片

- [x] PR-12：本地视频素材导入、逐镜替换/缓存与统一规格编码（支持 MP4/MOV/WEBM/MKV，零 AI 费用）
- [x] PR-11：离线 Story Bible → 剧本/审核 → 镜头技术卡片 → FFmpeg H.264/AAC/字幕轨 → 可播放 MP4 + QA + 单镜头缓存（无 AI 视频/配音）
- [x] PR-15a（**60 秒离线竖屏技术样片**）：使用同一审批/剧本/资产/分镜/FFmpeg/PR-14 逐镜哈希缓存与强制技术 QA，提供 `python -m drama_factory.pipeline.offline_demo --seconds 60 --out artifacts/offline-demo-60`；专用 GitHub offline-video CI 实际编码、校验及上传 60 秒 MP4 + manifest，输出明确 `genuine_ai_video_verified=false`、`publish_approved=false` 和零 Provider 收费。完整真人音画、演员一致性和人工审片仍属后续 PR-15 正式范围。详见 [PR15_OFFLINE_MINUTE_DELIVERY](PR15_OFFLINE_MINUTE_DELIVERY.md)。
- [x] PR-15b（**离线本地对白＋音乐技术混音**）：支持 PCM WAV 对白/背景乐选择、权利自我确认、片源音轨替换或保留、音乐衰减与 AAC 限幅、H.264/字幕轨保留、混音后全片 PR-14 QA 和声音变更时保留已验证镜头缓存；严格标记 `voice_license_independently_verified=false`、`publish_approved=false`、`paid_api_calls=0`。这是本地技术合成，不表示 Gemini TTS/真人声音授权/商业上映/精准口型同步已通过。详见 [PR15_LOCAL_AUDIO_MIX](PR15_LOCAL_AUDIO_MIX.md)。
- [x] PR-15c（**实际 60 秒本地合成双 stem 混音技术 MP4**）：原审批/分镜/FFmpeg/QA 链路加入 540Hz 合成对白时序占位音和 180Hz 合成背景音乐占位音；真实混音后保留 H264/AAC/mov_text、SHA256 及 `technical_qa`，专用 CI 重新编码、验收并上传单独 7 天 Artifact。音源并非真人配音、TTS 或商业授权音乐，`publish_approved=false`、付费调用 0。详见 [PR15_SYNTHETIC_AUDIO_MINUTE](PR15_SYNTHETIC_AUDIO_MINUTE.md)。
- [x] PR-15d（**逐句字幕与审核音轨对齐**）：使用已审核 Actor/台词/起止秒生成独立有序 SRT 字幕；对人为停顿不显示整镜对白，旧手工镜头继续兼容。最终 QA 核对逐句起止时间、允许的静音间隔、字幕内容 SHA256 与剧集总长，伪造或错位文字拒绝验收；强制真实 FFmpeg 测试和 60 秒样片复查。没有真实发音、字级口型、商用版权自动批准。详见 [PR15_APPROVED_CUE_SUBTITLES](PR15_APPROVED_CUE_SUBTITLES.md)。
- [x] PR-15e（**MP4 内嵌字幕文本/时间独立回解核验**）：真实 FFmpeg 从最终 H264/AAC/mov_text 视频中解码 subtitle stream，独立解析每句文本与时间、逐条对比经审核 SRT；避免仅有字幕轨/外部字幕正确但 MP4 内嵌字幕被替换或错位。故障测试重新封装假字幕并重算 MP4 SHA256，QA 必须仍拒绝；强制 6 秒/60 秒 FFmpeg CI 双重验收。继续纯离线、不可称真正 AI/TTS 成片。详见 [PR15_MUXED_SUBTITLE_AUDIT](PR15_MUXED_SUBTITLE_AUDIT.md)。
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