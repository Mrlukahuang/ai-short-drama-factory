# 工作包分期交付手册｜W0–W8（模型独立交接）

> 上级：[开发 Bible](../DEVELOPMENT_BIBLE.md) · 多模型协议：[MODEL_HANDOFF.md](MODEL_HANDOFF.md) · 外部源码：[OPEN_SOURCE_REUSE.md](OPEN_SOURCE_REUSE.md)。**W 是开发工作包，不是仓库正式阶段/Req**；PR 必须仍用 `Stage: G4` 与 `Req: R4.4` / `R4.3`（或正式 STAGES 指定的未来 Gx/Rx.y）。不得用本手册绕过 G4 退出条件提前进入 G5–G7。

## 0. 工作包管理原则

每一个工作包代表一个可以由独立模型执行、完成测试、开 PR、经过另一模型审查、合并到 main 并交接的**垂直成果**。把 W1–W5 当作当前 G4 内部工作顺序：不是五个随意同时开发的分支。**核心原则：上游契约被生产证据冻结后，下游模型才接手；不允许多人同时对同一文件写入。**

标准完成条件（Definition of Done，DoD）：(1) 指向唯一 Stage/Req；(2) 说明具体输入产物与来源 SHA；(3) 使用既有代码或写明最小上游复用决策；(4) 单测/契约测试/离线真实媒体测试结果分级；(5) 费用/许可证/安全门禁；(6) 一份可核对的 PR 与 main SHA；(7) 复述下一位模型的唯一任务及其禁止修改范围。**任何步骤未满足，不可标“阶段完成”。**

### 状态一览（建立本手册时）

| 包 | 正式归属 | 目的 | 基线状态 | 可以开始吗 |
|---|---|---|---|---|
| **W0 资产盘点/证据冻结** | G4/R4.4 | 不重复造轮子 | 本 Bible 与 Issue #164 建立审查基线；持续刷新 | 可只读更新 |
| **W1 单镜修复的生产闭环** | G4/R4.4 | 只重做失败镜头，保证费用/许可/回填 | 离线单镜替换已有；真实重新生成尚未验证 | **当前优先** |
| **W2 角色/场景/台词绑定** | G4/R4.4 | 减少同脸同声与镜头信息漂移 | Fake 资产结构存在；真实 Omni prompt-only | W1 契约冻结后 |
| **W3 实片后期的真实接线** | G4/R4.4 | 文字、声音、音乐和 MP4 可追溯 | Run39133557599 字幕 DRAFT 成功，独立配乐未做 | 已有部分**不重写**；剩余小需求按 CURRENT |
| **W4 内容 QA 与逐镜审片** | G4/R4.3 | 质量失败能定位并单镜回退 | 有人工画面报告，自动内容 QA 未证实 | 有真实素材/承接契约后 |
| **W5 G4 综合验收** | G4/R4.4 | 证明是能发布的产品而非技术样片 | 尚未退出 | W1–W4 + 所有者审批后 |
| **W6 三集批量与成本可靠性** | G5/R5.x | 产能/稳定性，而非单集功能 | 未启动 | **禁止，等 G4 退出** |
| **W7 已授权小说改编** | G6/R6.x | 原创和小说汇入同一生产总线 | 未启动 | **禁止，等 G6 解锁** |
| **W8 云端多人运营** | G7/R7.x | 安全远程交付 | 未启动 | **禁止，等 G7 解锁** |

## W0：既有资产清点与复用评审（角色：协调/架构模型）

**用户目的**：让后续所有模型不用重新调查全仓库或再次实现已有内容。**范围**：只读盘点 + 不改治理的文档 PR。已由本 Bible 提供初始结果，之后只在真实主干明显变化时刷新。

- **输入**：最新 main、`AMEND.md`、`CURRENT.md`、`AGENTS.md`、`STAGES.md`、既有 `docs/PIPELINE.md`、`docs/REFERENCE_PROJECTS.md`、最近成功 Actions 与 artifact。
- **工作**：按 00_input–10_qa 对每步给出 `Implemented Fake / Existing Real / Validated Real / Blocked`；代码证据用实际 path+commit，严禁假定模拟成果是成片。查 OpenMontage/HyperFrames/ViMax/Jellyfish 固定源码；按 LICENSE 分类可复制与只能借鉴。
- **输出**：本 Bible + 本目录文档；源代码差距单；一张映射表（本仓库入口/外部候选/明确差距/最小实现路径/测试）。
- **验收**：新模型可根据本文在不问前任的情况下找到 Run39133557599、12 镜 Run39130058487、具体脚本、当前 R4.4 下一步；不创建第二套产物/数据库。
- **失败/停止**：仓库 main 已变则刷新；证据不足写 unknown，不补造“已测”。
- **交接**：W1 模型只拿冻结源 SHA、代码/产物清单、预算与权限约束。W0 不做代码实现。

## W1：失败镜头的受控再生产和回填（执行模型：Generation/Provider）

**正式归属：Stage: G4 / Req: R4.4。优先级：P0。**

**为什么**：已经有 12 镜和单镜“已有 MP4 替换”，但“失败 s07 只需合法生成 s07，再接回所有后期产物”还没有确认完成。必须解决这个闭环，才能把未来质量修复变成低成本的单镜操作。

- **输入契约**：被选的 `shot_id`（s01–s12）、冻结的 approved screenplay SHA、原 `report.json` 和媒体列表 SHA、资产快照版本、失败原因/人审记录、运营者对这一次 API 调用的独立费用批准与可执行的安全上限。
- **复用优先**：`scripts/run_gpt_video_three.py`（真实 Omni Provider 请求及一次性计费保护）、`scripts/complete_gpt_episode.py`（验原始媒体）、`scripts/repair_gpt_episode_offline.py`（已有本地新片回填）、`scripts/assemble_gpt_video_three.py`（校验/concat）；借 OpenMontage 的前置审批、checkpoint 思想。**不可创建新的任务账本或复制原付费标记。**
- **先做零费用实现**：从现有“待修 shot → 计划/来源/预算 → 单镜提供商任务的权限检查 → 新 receipt → 单镜回填 → 新交付父版本”的状态图写接口契约、Fake 和离线错误路径。使用仓库已有真实旧片模拟提供者新返回；不发真实 API。
- **输出契约**：repair plan、批准来源、旧新媒体 SHA、明确的 `provider_task_id`（如果真实调用才有）、估算/授权/实际账单分列、`new_generation_attempts`、原 11 镜哈希表、重拼接 MP4 与新的 parent delivery SHA、失败时保存旧版本。
- **DoD**：任意 1 镜替换成功时 11 镜内容 SHA 不变、shot 顺序不变、新输出独立目录、FFprobe/全解码成功；失效/错 ID/重复授权/旧令牌/不兼容 codec/错误来源/越权全 fail-closed；输入缺少收费批准时 **0 次真实模型调用**；旧已完成原片不可覆写。
- **真实收费测试**：独立新授权（不能继承已消费的 USD5），先从 1 镜验证；目前不在本包自动启动。测试成功与否以真实任务回执/成本来源记录，**非估算当账单**。
- **停止条件**：真实单镜 Provider 请求没有可确认上限，供应商不支持的入参，费用超过 AMEND 限制，重复计费不确定，或者 CI 两次修复仍红 → 创建所有者 Issue/停止收费部分。
- **交接给 W2/W3**：固定 shot receipt 字段与父版本关系；若计划里无角色资产绑定，明确标 false，不“补填已验证”。
- **专属文件优先**：`scripts/run_gpt_video_three.py` / `scripts/repair_gpt_episode_offline.py` / `providers/google_omni_video.py` 的最小范围；跨共享 `screenplay_video_plan.py` 的变更需先与 W2 接口审查。

## W2：角色/场景/道具/声线版本锚点（执行模型：Character & Storyboard）

**正式归属：Stage: G4 / Req: R4.4。依赖：W1 约定了修复中保留的来源字段。**

**为什么**：失败真实视频里绿围裙男 s03/s09 变老，s07 意外三格分屏。只靠每镜独立 prompt 不能保证视觉一致，应先保证输入身份约束稳定，再验证模型能力。

- **输入契约**：通过审批的 Story Bible / `Screenplay`、`felt_diorama.json` 风格、现有角色/场景/服装资产 ID 和 SHA、每镜 `character_ids`、`DialogueCue.speaker`。
- **源码复用**：Jellyfish `shot_character_links.py` / `shot_assets.py` / `shot_video_readiness.py` 的绑定关系，ViMax `storyboard_artist.py`、`character_portraits_generator.py` 的视觉提示；本仓库 `assets/references.py`、`pipeline/shot_reference_board.py`、`screenplay_video_plan.py`，禁止搬 MySQL/Redis。
- **拆解**：W2.1 确保一个 character_id 对应唯一一致的短外貌锚点与锁定版本；W2.2 每镜只包含实际出场的人物；W2.3 speaker_id+expected_dialogue 与 shot 对齐；W2.4 明确 API capability probe——Omni 当前 reference image/audio 不支持的地方如实记录并禁止默默丢入参。
- **输出**：一份可核对的 per-shot actor/scene/speaker manifest，原 prompt_hash、新 prompt_hash、来源版本、`production_assets_verified` 的真实含义（未实际验证不得置 true），不变的审批/状态接口。
- **DoD**：角色错 ID、跨 series 资产、空锚点、台词 speaker 不在支持列表、同一角色两个冲突版本、丢失版本 SHA 时离线 fail-closed；同一剧本重复构建产出相同 prompt/manifest SHA；不改变已完成视频或授权标志；带有角色名的文字并非真正引用图像能力。
- **真实质量测试**：先用已有 12 镜真实失败证据做回归与静态检查；未来拿到新供应商能力和授权时，仅 2–3 镜评估脸、服装、音色和对白，不能因 W2 代码测试全绿就判人物一致通过。
- **停止条件**：需要新增收费生图、变更 G1 音频路线 B、改冻结 `jobs/tts_*`、修改治理/表结构 → 只提交决策证据，不擅自开发。
- **交接给 W4**：可引用的 `character_id`、`speaker_id`、`expected_dialogue`、参考资产版本 SHA 以及哪些仅是 prompt 锚点。

## W3：真实后期 / 字幕 / 配乐（执行模型：Postproduction）

**正式归属：Stage: G4 / Req: R4.4。现状：真实字幕草稿**已经**成功，不允许从零重做。**

- **输入**：W1 产出的有效媒体/receipt/父版本或既有 Run39130058487、现有 Sol approved screenplay 及 `scripts/postprocess_gpt_episode_offline.py` 结果、实际 ffprobe 时长。
- **复用**：`scripts/postprocess_gpt_episode_offline.py`（06–10 JSON、剧本字幕草稿/实际封装对照）、`assemble_gpt_video_three.py`、`pipeline/offline_qa.py`，已有 `offline_audio.mix_local_stems`；借 HyperFrames `mediaTiming.ts` 和 `renderRequest.ts` 的时间轴与渲染意图。
- **已完成**：真实 MP4 + DRAFT SRT / mov_text 字幕、原 H264/AAC stream copy、完整解码，成功 Run39133557599。不要把该成果作为“未做”再提一个 PR。
- **剩余缺口**：W3.1 合法单镜修复后，仅依实际新 clip 时长重建受影响时间轴、字幕和新成片；W3.2 若确有当前需求，**可选的本地获授权配乐**与原生对白保留/ducker；W3.3 把草稿字幕和 ASR 验证字幕永久区分；W3.4 输出版本及 provenance 完整。
- **特别危险点**：`offline_audio.mix_local_stems` 在 `dialogue` 存在时会**替换原音轨**，且依赖已有 `mov_text`；直接套真实 Omni 片会破坏原生对白。必须先建立 0-call 真实媒体回归，针对本用例做最小适配，不改冻住的 TTS recovery。
- **输出**：`09_render.json`（父版本、source shot hashes、字幕模式、audio mode、FFmpeg 参数、MP4/SRT SHA），`10_qa.json`，独立新 MP4；未实证 ASR 时 `subtitle_alignment_verified=false`、`dialogue_content_verified=false`、`publish_approved=false`。
- **DoD**：不含新配乐时音轨与原始音轨内容/codec 保留方式明确并检验；含音乐时新 MP4 不丢原生对白、不截句、不超峰；SRT 与 mux 字幕逐字对照、片段边界合规、ffprobe/全解码成功。已有 12 镜不改/新版本可回滚。
- **HyperFrames PoC**：仅后续的动效模板需求满足时，在**隔离分支/已有无敏感 10 秒片**进行对比；没有 FPS、稳定性、字幕或视觉提升的实证不得纳入正式运行时。

## W4：内容连续性 / ASR 与人工审片闭环（执行模型：QA/Evaluator）

**正式归属：Stage: G4 / Req: R4.3。当前没足够证据宣称完成。**

- **输入**：冻结的每镜 shot manifest（身份、scene、speaker、预期台词）、现有 12 镜源视频/分帧/音轨、SRT DRAFT、来源/费用记录。
- **复用**：`pipeline/offline_qa.py` 技术 QA、`pipeline/g1_benchmark_metrics.py` 指标、`docs/GPT_EPISODE_VISUAL_REVIEW_20261019.md` 的人工样例；OpenMontage 的 delivery promise 只作检测维度参考。
- **子包**：W4.1 人审记录格式：`shot_id` / 角色一致 / 声线 / 真实对白 / 口型 / 道具 / 乱分屏 / 文本污染 / 审查者及来源版本；W4.2 可加离线 frame grid 辅助比对；W4.3 ASR 服务的可行性与费用许可评估；W4.4 输出 shot 级 `usable`、`needs_repair`、`unknown`，并保留证据与人工裁决。
- **输出**：technical/content/release 三份不同报告，失败镜头 ID 与具体原因、回填给 W1 的唯一失败片段；未经可靠 ASR 不写“对白已核实”。模型置信分不等于人工签字。
- **DoD**：以已知 s03/s09 年龄漂移、s07 分屏为回归案例，未验证声线/台词必须 `unknown`（不能 pass）；人工明确拒绝则 `publish_approved=false`；任何不同版本媒体比对先验 hash。
- **费用/审批**：使用云端视觉模型或转写服务需遵守单次/每日 AMEND 费用限制、版权与新密钥许可；在授权前可先完成离线评审接口和测试，禁止自动生成修复镜头。

## W5：G4 MVP 集成验收与用户退出门（执行模型：Integrator/Acceptance）

**正式归属：Stage: G4 / Req: R4.4（涉及独立 R4.3 成果只引用，不混进一个 PR）。**

- **输入**：最新 main 上 W1/W2/W3/W4 全部真实合并提交、每阶段 PR CI、原有和修复后的 MP4 与 reports、供应商实账、用户反馈。
- **集成任务**：在统一 README/运行说明中提供从批准剧本到成片的 **单入口 CLI** 或已存在可组合命令；失败镜头只影响其下游 JSON，不能使其它已成功镜头重新收费；按旧版本/新版本分别记录时长/sha/编码/音轨/字幕。
- **出厂合同**：真实 60–90 秒 9:16 视频；两名主角可区分且每镜一致性经人工审片，台词和声音审查不隐去未知；成本以账单记录实际合格分钟；每集人工操作时间来自实际计时。
- **G4 北极星**：合格镜头率 ≥50%、每合格分钟实费 ≤USD30、单集人工操作 ≤2h，按 `docs/CHARTER.md` 实测；真实版本人工确认“可以发”，版权/声线权益齐备。
- **交付**：最后成功 run+artifact+source SHA+所有有效模型调用/计费回执+人审报告+清晰的 `full_episode_complete` 和 `publish_approved`。缺任何一项就记 `pending`，不得擅自进入 G5。
- **最后决策**：所有者单独批准 G4 退出；Integrator 无权修改 AMEND/STAGES 绕过审批。
- **与模型接力**：集成人员在**最新 main** 构建总交接清单，指定后续 G5 的任务起点和禁止重复工作，不让前一模型继续在已合并代码上做新改动。

## W6（未来 G5）：三集批量、稳定性、真实成本

**启动条件**：W5 获得所有者 G4 正式通过和 `STAGES.md` 允许。**现在仅保留设计，不实现**。

- **目标**：相同生产契约连续/并行产 3 集、保持一镜失败只局部恢复，按原有预算三级门禁/SQLite Worker 缓存，不发生盲目重复 API 计费。
- **输入**：G4 验收 MP4、shot/episode manifests、G4 实际费用、已有 `jobs/shots.py` / SQLite/receipt。
- **优先成熟源码**：已有 worker 优先；OpenMontage checkpoint 是设计启示，不复制 AGPL；Temporal（如有必要）先出有真实失败证据的迁移评估，不直接上。
- **交付/DoD**：3 集真实成功率、平均单集成本、恢复时间、调用次数/重复调用率、自动质量回归；不超既有批准预算；逐集可重现来源。
- **限制**：AMEND-001 的 storage/Turso/tts 冻结仍有效，须另行所有者决策是否解冻。

## W7（未来 G6）：小说/版权改编

**启动条件**：正式 G6 开始、证明原著适配权；不能发送未授权小说原文给任何模型。

- **目标**：TXT/EPUB/DOCX/PDF → 本地源文件哈希/章节锚点 → 事件/人物关系 → 季规划 → `Screenplay`，**合流同一 G4 视频总线**，不另造渲染器。
- **输入**：有许可证的原著、原文版本/合同范围与审校结论、G4 固定 Story Bible/Screenplay 协议。
- **借鉴**：ViMax `novel2movie_pipeline.py` 仅核对可移植部分，许可复核；现有 `docs/NOVEL_ADAPTATION.md` / 原章节读取模块。
- **交付**：原始段落/事件/剧本之间可追溯映射、改编审查签字、相同视频/声音/QA/费用流程重复利用。
- **DoD**：未授权输入 fail-closed，小说更新只使依赖集失效；改编不重建视频系统。

## W8（未来 G7）：云端/多人运营

**启动条件**：正式 G7 开始、确有多用户/共享资产需求且经安全评审。

- **目标**：基于 G4/G5 固定任务与产物协议，将文件存储、身份鉴权、队列执行、审计、版权和费用门禁部署到云端。
- **先做差距评估**：本机已稳定的 SQLite + Worker 是否确实不够？只引入必需的存储/调度；不得复制 Jellyfish 整个平台或 OpenMontage Backlot。
- **DoD**：权限隔离、Secret 管理、素材加密、完整审计、发布授权与账单安全、失败隔离与回退。
- **禁止**：G4 尚未验收时写云端业务代码。

## 全局跨包依赖与优先次序

```text
W0 只读清点 ──► W1 单镜修复闭环 ──► W2 版本化资产/台词契约
                         │                        │
                         └──────────► W3 真实后期输出
                                                  │
                                     W4 内容QA ◄──┘
                                           │
                                           ▼
                                      W5 G4验收
                                           │  所有者 G4 退出批准
                                           ▼
                                      W6 / G5
                                           │  G6 正式启动
                                           ▼
                                      W7 / G6
                                           │  G7 正式启动
                                           ▼
                                      W8 / G7
```

**可以有限并行**：W2 的只读源码分析和 W3 对历史素材的只读核验可以并行；写生产代码必须先冻结共享契约和文件所有权。W4 可独立写审片报告，不可在 W1/W2 修改同一个产物 schema 时抢先改主干。

**最小 PR 设计**：W1 权限/离线接口、W2 真实计划资产映射、W3 缺失的后期适配、W4 内容审查各拆**单一正式 Req** 的小 PR；每个 PR 按 AGENTS/GUARDRAILS 走 scope+tests；不存在“为了跨阶段方便”把多 Req 混在同一个大 PR 的例外。
