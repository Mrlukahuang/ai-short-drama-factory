# AI 短剧工厂｜开发 Bible（架构与实施准绳）v1.0

> **状态：技术实施规范 / 多模型交接的唯一长期索引。** 本文不是新版本的 AMEND，也不是阶段退出批准；如有冲突，以 `AMEND.md` → `AGENTS.md` → `docs/handoff/CURRENT.md` → `docs/STAGES.md` → `docs/GUARDRAILS.md` 的实际约束和当前开发状态为准。其他模型须在开发前重读上述文件并确认本 Bible 的适用版本。
>
> **建立日期**：2026-10-19 NZT。审计快照：本仓库 `main@51054c1722ee22be9eab146806e62636d181ed4d`。任何任务启动前从 GitHub 重新取得 main SHA，禁止将此历史快照误写为最新进度。
>
> **相关文档**：
> - [阶段级任务说明与关卡](development_bible/STAGE_DELIVERABLES.md)（按交付划分，不改 G0–G7）
> - [成熟开源复用清单与源码核对](development_bible/OPEN_SOURCE_REUSE.md)（导入代码前必读）
> - [多模型角色分工与无损交接协议](development_bible/MODEL_HANDOFF.md)（换聊天、换模型必读）
> - [正式阶段](STAGES.md) · [运行时交接](handoff/CURRENT.md) · [原复用矩阵](PIPELINE.md) · [来源登记](REFERENCE_PROJECTS.md)
> - [架构 Issue #164](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/164)

## 0. 存在目的与北极星

**我们做的是能重复产出可发布中文 AI 短剧的工厂，不是一个永远在造基础设施的试验场。**

每次改动必须说明对下列四个目标至少一个有直接作用：① 一集 60–90 秒、9:16 毛毡微缩风格双主角视频稳定完成；② 同一角色/同一声线/对白/镜头连续性获得可验证改善；③ 一镜失败只改一镜，保留其它真实成果；④ 费用、人力和发布风险可测可控。

当前 `docs/CHARTER.md` 的 G4 北极星：**合格镜头率 ≥ 50%；每合格分钟成本 ≤ USD30（实账）；单集人工操作 ≤ 2 小时**。这些是最终人工+真实执行指标，不可拿 Fake/估算代替。

**当前阶段仍是 G4；G5 批量、G6 小说改编、G7 云端依赖 G4 所有者验收，不得并行提前做代码。** 文档可以先定义未来阶段的边界和协议，不构成开始实施的授权。

## 1. 最新真实基线——已存在，不重写

| 项目 | 已验证事实 | 还不是 |
|---|---|---|
| 真实视频 | Run [39130058487](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39130058487)，Sol 剧本 → Omni → 12 镜 → 60.177333 秒 H264/AAC 预览，完整解码 | 人物/配音/可发布通过 |
| 单镜离线替换 | `scripts/repair_gpt_episode_offline.py` 可用已有本地片替换指定一镜，验证另外 11 镜 SHA、重拼接 | 新付费单镜重生成及授权 |
| 已有完整 Fake 路径 | `scripts/fake_episode.py` 11 个 JSON 阶段，包含角色/镜头/模拟音频/字幕/配乐/渲染/QA | 11 阶段真实模型端到端 |
| 真实后期 | Run [39133557599](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39133557599) 成功，`scripts/postprocess_gpt_episode_offline.py` 对已有真实 12 镜做剧本推定字幕、mov_text mux、保留原生音轨并核验，0 新模型调用；PR #161/#162 已合并 | ASR 对齐、中文语音正确、声音一致、独立配乐 |
| 质量审查 | `docs/GPT_EPISODE_VISUAL_REVIEW_20261019.md`：s03/s09 男主年龄漂移，s07 分屏，字幕/道具不稳，用户反馈配音差 | 自动视觉/语音质检已达标 |
| 工程进度 | CURRENT 报 G4 约 85% 为估算 | 验收通过百分比 |

**唯一当前开发方向**：遵循最新 `CURRENT.md`，先补「真实失败镜头的合规授权与修复闭环 → 可靠交付记录」，不因本 Bible 改写在途任务；人物/音色深度优化随之进入内容质量阶段。不得重复 Run 的有偿部分，不得复用已消费的 USD5 特批令牌。

## 2. 体系边界与组件选择

```text
[输入] 原创 Brief / 已经获得影视改编许可的文本
     │
     ▼
[创作域] Story Bible → 分集剧本 → Screenplay/DialogueCue
     │  剧本人工审批，保持 schema + 原创版权证据
     ▼
[生产契约] 角色/场景/道具/声音版本、每镜计划、媒体能力、费用预估
     │  执行前预检 + 费用/权限/供应商能力门禁
     ▼
[生成域] Python orchestrator → VideoProvider 适配器 → 每镜 Receipt
     │  原媒体不可原地覆盖；每镜源哈希/模型/任务 ID
     ▼
[剪辑域] 原镜头 → 标准时间线 → 原生声轨/字幕/获授权配乐
     │  FFmpeg 主路径，HyperFrames 只有隔离验证后可选
     ▼
[交付域] 版本化 MP4/SRT/JSON → Technical QA → Content QA → Release QA
     │
     ▼
[所有者审批] 通过后才可能标记 publish_approved；G4退出另行批准
```

**唯一命令/控制权**：Python orchestration 是状态变更、费用、版权、许可及人工门禁的唯一权威。GPT/Codex/Claude/Skills 是可替换的实现者/生成者，不可跳过正式 Python 验证；外部项目的 Agent 自主调度不能直接接管生产状态。

**不采用的整套依赖**：OpenMontage Agent+700 Skills+Backlot、Jellyfish MySQL/Redis+前端、Temporal/Turso、Remotion 平台、HyperFrames Chromium 渲染运行时——只有当前需求的最小局部组件可先隔离 PoC 再决定。现有 FFmpeg/SQLite/假 Provider/已有 Worker 保留。

## 3. 契约设计：沿用已有 Schema，只有缺口才追加可选字段

新模型**先读实际 Pydantic 模型与函数签名**再提改动。本节是*目标逻辑契约*，不是宣称这些字段现在全部存在；不得为了满足下列草案而重建数据库。

### 3.1 故事→分镜

- StoryBible：`series_id`、`story_bible_id`、版本、风格、角色名册、场景、角色不可变外观锚点；来源为已审批 Brief。
- Episode/Screenplay：`screenplay.zh.v1` 既有验证；`shot_id`、`duration_seconds`、`scene_id`、`character_ids`、动作、镜位、上镜人物、`DialogueCue`（speaker、文本、预期时间）。
- 上游变更要改变来源/版本 SHA，受影响后代产物标为失效；**不能静默改写已批准的对白**。
- 字幕草稿来自剧本，不等于真实语音；实际中文转写和口型待独立验证。

### 3.2 分镜→生成（Shot Production Envelope，提议兼容现有结构）

```json
{
  "schema_version": "shot-production.proposed.v1",
  "episode_id": "ep-id",
  "shot_id": "s03",
  "screenplay_sha256": "sha256-of-approved-script",
  "character_ids": ["ajie"],
  "asset_refs": [{"kind":"character", "id":"ajie", "version_sha256":"sha256"}],
  "scene_ref": {"id":"cafe", "version_sha256":"sha256"},
  "speaker_cues": [{"speaker_id":"ajie","expected_text":"原剧本对白","start_ms":0,"end_ms":1800}],
  "provider": {"id":"omni","model_id":"gemini-omni-1.1-flash","reference_image_supported":false,"audio_reference_supported":false},
  "request": {"prompt_sha256":"sha256","duration_floor_seconds":5,"aspect_ratio":"9:16"},
  "authorization": {"paid_execution_authorized":false,"cost_estimate_usd":null,"approved_cost_cap_usd":null},
  "receipt": null,
  "content_qa": "not_reviewed"
}
```

这只是接口协商样例。不能自动造出虚假的 `reference_image_supported=true`、实际费用、speaker_verified 或 published。现有 Omni adapter 目前 **prompt-only**，明确拒绝参考图和音频参考；升级前要先确认供应商 API 契约及本项目适配器支持，禁止声称传了参考资产。

### 3.3 生成→合成（Render Intent，借 HyperFrames 的 JSON-safe 思想）

渲染请求至少记录：源视频片段 ID/SHA/顺序/实测时长、目标宽高/FPS、原 AAC 音轨处理模式（默认 preserve-native）、字幕模式（`draft_from_script` / `verified_transcript`）、字幕文件 SHA、可选音乐版权证明、输出版本与来源哈希、ffmpeg 命令或 renderer 版本、失败状态。严格拒绝带损坏哈希/缺来源片段/不兼容 stream profile 的输入；如果需转码，走显式 normalization 决策，不要偷偷丢音频。

**视频不变式**：除被明确修复的镜头外，输入镜头文件 SHA 保持；后期重新混音/封装不等于原始视频文件 SHA 不变。所有新成片使用新路径与父版本引用，不原地覆盖已验收交付。

### 3.4 QA 绝不混淆三层

| 层 | 机器能断言什么 | 谁决定通过 |
|---|---|---|
| Technical | 片源来源/格式/可解码/时长/镜头顺序/SRT 与 mux 字幕实际一致/文件哈希 | 测试 + FFprobe/FFmpeg |
| Content | 角色脸和服装跨镜一致性、分屏/字幕污染、实际说话者/中文文本/音色/口型和镜头连贯 | 人工审片；可有视觉/转写辅助但须标明置信度 |
| Release & governance | 版权、声纹授权、实际供应商账单、人工发布签字、G4 指标 | 所有者 |

建议状态：`generated` → `technical_preview_passed_pending_human_review` → `content_reviewed` → `release_reviewed`。异常镜头标 `needs_repair` 并锁定对应哈希；不要因为一次通过技术 QA 将 `full_episode_complete/publish_approved` 改 true。

## 4. 端到端既有代码索引：接线优先，重写禁止

| 环节 | 先复用本仓库 | 当前缺口或边界 |
|---|---|---|
| Writer | `pipeline/text.py`、`screenplay.py`、`writer_execution_prep.py` | 正式 GPT 基线/模型评估、内容审批 |
| Storyboard | `pipeline/screenplay_video_plan.py`、`director_timeline.py` | 真实产物与版本化角色绑定 |
| Assets | `assets/references.py`、`pipeline/local_asset_references.py`、`shot_reference_board.py` | 角色/场景/镜头的可核对生产级引用 |
| Provider | `providers/video_provider.py`、`google_omni_video.py` | reference image、稳定声线能力未证实，不能伪实现 |
| Shot receipt | `scripts/run_gpt_video_three.py`、`complete_gpt_episode.py` | 合法单镜付费修复/批次版本正确衔接 |
| Assembly | `scripts/assemble_gpt_video_three.py`、`repair_gpt_episode_offline.py` | 已有真实媒体可无费拼接；保留 |
| Post | `scripts/postprocess_gpt_episode_offline.py`、`pipeline/offline_audio.py`、`offline_render.py` | 已有推定字幕流程；配乐必须保留 Omni 原声、先读混音约束 |
| QA | `pipeline/offline_qa.py`、`g1_benchmark_metrics.py` | 需要把 Content QA/费用/发布证据分开 |

**具体外部项目及可直接移植的许可分类**：见 [OPEN_SOURCE_REUSE.md](development_bible/OPEN_SOURCE_REUSE.md)，以原始文件、commit、license/NOTICE 作为证据。别根据热门 Star 决定整体迁移。

## 5. 分工与阶段管理的两层坐标

**G0–G7 = 正式产品阶段（不可绕过）**；**W0–W8 = 开发工作包**，用于把可交接的成果分给不同模型。任何 W 工作包都要标当前 `Stage: G4` + 唯一 `Req: R4.4` 或 `R4.3`，未来 G5/G6/G7 要等 STAGES 的退出条件；不得把 W 编号当作已授权 Req 编号。

- W0：只读证据/复用盘点 → 精准任务列表；无需改生产代码。
- W1：真实单镜修复的权限与 artifact 级恢复闭环（G4/R4.4，当前主线）。
- W2：真实分镜与资产的版本化映射/上游契约（G4/R4.4；不得伪造 Omni 参考图支持）。
- W3：已有真实后期/字幕与音轨完善（G4/R4.4；不能重复 PR #161/#162 已交付部分）。
- W4：镜头及成片内容 QA、可审查状态（G4/R4.3）。
- W5：G4 证据汇总 + 用户真实评审与退出判断（有审批才退出）。
- W6：G5 多集批量与成本可靠性（**暂停**）。
- W7：G6 已授权小说改编（**暂停**）。
- W8：G7 云端/多人（**暂停**）。

**每包输入、输出、测试矩阵、精确 source 文件、模型/文件所有权、失败回退和 DoD 在 [STAGE_DELIVERABLES.md](development_bible/STAGE_DELIVERABLES.md)。**

## 6. 开工前的六个强制问题

1. 这次是 G4 哪个 `Req`，能证明哪一个真实输出更接近成片？如只有“以后可能有用”，不写。
2. 本仓库是否已经有同样功能？关联 SHA、路径、PR、真实运行证据是什么？同等能力不另起炉灶。
3. 有哪份成熟开源源码可以当现成库或**最小许可合规代码移植**？不抄不可商用/限制许可的原代码。
4. 能否通过 **薄适配层**完成？如果提议新状态系统、新表、新 Worker、整个 UI，必须证明现有路径客观无法满足，并先取得用户批准。
5. 会触发多少真实 API/费用？无人批准的新有偿视频一律不开；Fake/已存在媒体优先。
6. 验收如何区分“CI 单测通过”、“已有真实素材离线通过”、“真实 AI 模型内容通过”、“所有者允许发布”？

## 7. 变更控制与可用性

- 当前治理按 `AMEND-001` 冻结 storage/Turso/tts 恢复/多类 workflow；冻结文件、新数据库表结构、治理文件、超额费用、签字退出必须按所有者审批，不以本 Bible 替代。
- 每个 Req 一个小 PR，推荐代码改动 ≤ 600 行（测试另计）；所有检查绿才合并；同一检查连续修 2 次仍红就停下汇报。
- 每个源码借用记录 **upstream repo@commit、上游相对路径、精确范围、许可证/NOTICE、本地路径、用途、测试、未来更新风险**；在正式复制后同步登记 `docs/REFERENCE_PROJECTS.md §7`，如许可证不明确先暂停复制。
- 任何其他模型只接受 [MODEL_HANDOFF.md](development_bible/MODEL_HANDOFF.md) 规定的证据+SHA 交接，不相信旧聊天“已经完成”的文字。
- 不允许多个模型同时修改同一共享文件；跨模块接口先合意图契约，再由各模块各自修改，集成负责人在最新 main 收尾。

## 8. 禁止事项与失败停止条件

不为假成功重造数据库/重试系统、不自动重做 12 镜、不直接复制 AGPL/NC/Elastic 限制源码、不为漂亮 UI 牺牲真实成片、不改主视频路由去追热度；**模型生成失败时先保留有效产物，检查是契约/输入/提供商/后期哪一层的问题，不能以扩大付费次数代替诊断**。

最终开发评估看具体产物：一个独立可播放的版本化 MP4、对应每镜 JSON 证据、真实 Content QA/人工结论、每合格分钟实际费用与人工时长。四者不齐，最多叫“技术样片”，不能叫“产品验收”。
