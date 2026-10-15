# P0｜梗概 → 整集 Fake MP4 链路现状、复用矩阵与缺口

> **适用修正**：AMEND-005（2026-10-16，Active），优先于旧的 G1 阶段推进限制；仍遵守 AMEND-001 的冻结路径、AMEND-004 的一 Req 一 PR 与全绿自合并。
> **本文件仅作差距分析，不是已实现能力清单**。目标是未来 **P-final** 用单条 CLI 从本地原创梗概文件生成整集 **Fake** MP4，并在独立工作目录保留每步 JSON；单步可重跑。绝不调用真实 AI/供应商、付费或私有真人素材，也不将 Fake 产物标成商业短剧。
> **源码核对**：本仓库 `main@1a16e54710c8d0c43f49c346cf1130375f798bf8`；ViMax `HKUDS/ViMax@fd4b72e7731be6e5f88486206d25ea59849b0285`（MIT）；Jellyfish `Forget-C/Jellyfish@a9678194ddf2d9be3ccbe78d4287d87d5089e123`（Apache-2.0）。下文指向这些 revision 的具体源码位置。**P0 未复制任何第三方代码**，仅借结构和思路；如以后复制/修改代码，必须保留版权、许可证及 NOTICE（如有），并在 `docs/REFERENCE_PROJECTS.md §7` 登记来源版本/文件及本地文件。

## 1. 复用原则与端到端目标

流程：**梗概 → Story Bible → 剧本 → 分镜 → 角色资产 → 逐镜视频 → 对白 → 字幕 → 配乐 → 合成 → QA**

在 CLI 下使用已经存在的 Pydantic Schema、SQLite 现有表/审核机制（不改 Schema）、现成的 Fake Provider、FFmpeg 音画合成与 QA。新代码只补**接口适配与编排**，不重新实现角色库、FFmpeg、任务账本、前端，亦不在 P0 引入真实文本生成模型。

建议产物目录（**未来契约，P0 不创建**）：

```text
<local-output>/<run-id>/
  00_input.json                  # 原创梗概摘要、来源SHA256；不包含未经授权的小说
  01_story_bible.json            # 结构化、本地 Fake/模板内容
  02_episode_script.json         # 分集剧本
  03_screenplay.json             # screenplay.zh.v1、带逐镜对白和时长
  04_assets.json                 # 演员/场景/声音资产 ID + 精确版本
  05_shots.json                  # 每镜 Fake 视频/文件哈希/来源
  06_dialogue.json               # Fake 非人声 PCM 时槽/轨道声明
  07_subtitles.json              # 对白时间与 SRT 校验索引
  08_music.json                  # 合成/免版税本机配乐引用（默认纯合成）
  09_render.json                 # MP4、技术 manifest、实际哈希
  10_qa.json                     # ffprobe/解码/字幕独立结果
  episode.fake.mp4               # H.264/AAC/mov_text；永久 Fake 标识
```

每个 JSON 至少有 `schema_version`、`run_id`、`step`、`input_sha256`、`status`、`fake_only: true`、依赖产物哈希和安全的输出定位；不得写 secrets、真实模型声称的账单或未经许可的文件路径。单步重跑只使下游**哈希不匹配**的产物失效，绝不调用上游真实 Provider。格式细节由后续对应 P Req 实现、补测确认；上述字段是**建议而非仓库现有 schema**。

## 2. 逐环节复用与外部源码对照（11 步）

状态说明：**复用**＝现有模块能支持该节点的部分工作；**需接线**＝尚未形成从梗概 CLI 自动调用的路径；**待 Fake**＝缺受控无密钥实现。即使某节点标“复用”，亦**不代表从梗概到成片已自动贯通**。

| 步骤 | 本仓库现有模块／现状／是否直接复用 | ViMax（MIT）对应源码与做法 | Jellyfish（Apache-2.0）对应源码与做法 | P 缺口 |
|---|---|---|---|---|
| 1 **梗概输入** | `src/drama_factory/pipeline/text.py` 的 `ScriptPlanRequest.creative_brief` + `FakeTextProvider`：可复用**已有 Fake 策划输入**，但 CLI 尚不能读取本地梗概并自动创建全程运行上下文；`src/drama_factory/pipeline/text_api.py` 是 API 入口。 | [`main_idea2video.py`](https://github.com/HKUDS/ViMax/blob/main/main_idea2video.py)、[`pipelines/idea2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/main/pipelines/idea2video_pipeline.py)：把 idea/要求传给 Pipeline。 | [`backend/app/chains/agents/script_simplifier_agent.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/chains/agents/script_simplifier_agent.py)、[`backend/app/api/v1/routes/script_processing.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/api/v1/routes/script_processing.py)：文本简化和处理入口；Jellyfish 主要从剧本/章节输入，并非直接 idea-to-video。 | **P1、P6** |
| 2 **Story Bible** | `src/drama_factory/models.py`、`src/drama_factory/api.py` 的 Series/Bible 数据接口、`src/drama_factory/pipeline/text.py` 的 typed outlines：Schema 和存储**复用**；但目前没有“梗概→原创 Story Bible”完整 Fake 转换，不能将 `ScriptOutline` 冒充 Story Bible。 | [`agents/screenwriter.py`](https://github.com/HKUDS/ViMax/blob/main/agents/screenwriter.py) 的 `develop_story` / `write_script_based_on_story`；[`pipelines/idea2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/main/pipelines/idea2video_pipeline.py) 连接构思与编剧。 | [`backend/app/chains/agents/script_optimizer_agent.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/chains/agents/script_optimizer_agent.py)、[`backend/app/chains/agents/element_extractor_agent.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/chains/agents/element_extractor_agent.py)：优化剧本与抽取要素，**没有证据表明与本项目 Story Bible 结构相同**。 | **P1** |
| 3 **分集剧本** | `src/drama_factory/pipeline/text.py`：`FakeTextProvider.generate` 返回 `ScriptOutline`，**可以复用，但只到 outline**；`src/drama_factory/pipeline/screenplay_routes.py` 有后续审核/提交接口。欠确定性的 outline→含中文对白与场次的 Episode Script 转换。 | [`agents/screenwriter.py`](https://github.com/HKUDS/ViMax/blob/main/agents/screenwriter.py)、[`pipelines/script2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/main/pipelines/script2video_pipeline.py)：分段编剧、后续镜头设计。 | [`backend/app/chains/agents/script_divider_agent.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/chains/agents/script_divider_agent.py)、[`backend/app/services/studio/script_division.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/script_division.py)：将结构化拆镜结果写入 Chapter/Shot/ShotDetail。 | **P2** |
| 4 **分镜** | `src/drama_factory/pipeline/screenplay.py` 的 `Screenplay/ScreenplayShot/DialogueCue` 和 `check_screenplay_scope`、`src/drama_factory/pipeline/local_story_workflow.py` 的 `make_storyboard_template`、`src/drama_factory/pipeline/director_timeline.py`：**复用 Schema、校验、模板**；目前模板需人工补齐内容，尚不能根据 Episode Script 生成语义正确的全 Fake 12 镜/60–90 秒分镜。 | [`agents/storyboard_artist.py`](https://github.com/HKUDS/ViMax/blob/main/agents/storyboard_artist.py) 的 `design_storyboard` / `decompose_visual_description`；[`interfaces/shot_description.py`](https://github.com/HKUDS/ViMax/blob/main/interfaces/shot_description.py) 保存镜头语义。 | [`backend/app/services/studio/script_division.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/script_division.py)、[`backend/app/models/studio_shots.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/models/studio_shots.py)：按章节建立逐镜结构；无需移植其 MySQL 表。 | **P2** |
| 5 **角色／场景／声音资产** | `src/drama_factory/assets/routes.py`、`src/drama_factory/assets/references.py`、`src/drama_factory/pipeline/local_asset_references.py`、`src/drama_factory/pipeline/shot_reference_board.py`：**复用现有版本与系列归属**；`src/drama_factory/providers/google_image.py` 有 Fake 图像但此 P 链不能付费；缺从新角色草稿自动生成**仅 Fake 的可追溯资产引用**和逐镜精确资产版本映射。 | [`agents/character_extractor.py`](https://github.com/HKUDS/ViMax/blob/main/agents/character_extractor.py)、[`agents/character_portraits_generator.py`](https://github.com/HKUDS/ViMax/blob/main/agents/character_portraits_generator.py) 的正/侧/背向角色参考与接口。 | [`backend/app/services/studio/shot_assets.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_assets.py)、[`backend/app/models/studio_assets.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/models/studio_assets.py)、[`backend/app/services/studio/shot_character_links.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_character_links.py)：角色/场景/道具/服装与镜头绑定。 | **P3** |
| 6 **逐镜视频** | `src/drama_factory/providers/video_provider.py`（共通 `VideoProvider`）、`google_omni_video.py`、`seedance_video.py`、`kling_video.py` 的 Fake；`src/drama_factory/pipeline/contracts.py`（旧异步 ShotSpec/Receipt）；`src/drama_factory/jobs/shots.py`、`jobs/offline_worker.py`、`pipeline/offline_render.py` **可复用 Fake 工人/镜头缓存/FFmpeg**。**注意共通 VideoResult 的 Fake 不返回 MP4；现有本地 render 会生成占位卡，而非真实模型画面**。尚缺把经批准的分镜和版本化参考映射到逐镜 Fake 任务与成果 JSON 的编排桥梁。 | [`pipelines/script2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/main/pipelines/script2video_pipeline.py) 的 `generate_video_for_single_shot`、`generate_frames_for_single_camera`；[`tools/render_backend.py`](https://github.com/HKUDS/ViMax/blob/main/tools/render_backend.py) 按配置注入视频/图像生成器。 | [`backend/app/services/studio/generation/video/build_submission.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/generation/video/build_submission.py)、[`backend/app/services/studio/shot_video_readiness.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_video_readiness.py)、[`backend/app/core/tasks/video_generation_tasks.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/core/tasks/video_generation_tasks.py)：先验证镜头就绪→构造输入→任务中心；不借它的异步栈。 | **P4** |
| 7 **对白音频** | `src/drama_factory/providers/dialogue_audio.py` 的 `FakeDialogueAudioProvider`（**合成频率提示音，并非真实说话**）、`src/drama_factory/pipeline/offline_cast_timeline.py`、`offline_dialogue_timeline.py`：**直接复用纯离线人物/时间槽与 WAV**；缺让 CLI 接线生成 `06_dialogue.json`。AMEND-001 冻结 `jobs/tts_*`，**不得修改**。 | [`interfaces/shot_description.py`](https://github.com/HKUDS/ViMax/blob/main/interfaces/shot_description.py) 保存镜头/叙事字段；ViMax 当前 Script2Video 主链以视觉生成和视频拼接为重点，**未验证有可直接对应本项目中文逐角色 FakeTTS 混音的模块**。 | [`backend/app/services/studio/shot_dialogs.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_dialogs.py)、[`backend/app/models/studio_shots.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/models/studio_shots.py)：镜头对话行与角色关联；不等同于声学 TTS。 | **P5** |
| 8 **字幕** | `src/drama_factory/pipeline/offline_render.py` 的 SRT 生成及 mov_text mux、`offline_qa.py` 中验证 SRT/视频内字幕：**直接复用**；缺在一键 CLI 中将每镜对白时间槽输出为 `07_subtitles.json` 并引用 SRT。 | [`pipelines/script2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/main/pipelines/script2video_pipeline.py) 的视频镜头合成路径；**未确认独立中文 SRT/字幕校验组件**，此环节优先本仓库实现。 | [`backend/app/services/studio/shot_dialogs.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_dialogs.py) 提供对话文本，[`front/src/pages/aiStudio/editor/VideoEditor.tsx`](https://github.com/Forget-C/Jellyfish/blob/main/front/src/pages/aiStudio/editor/VideoEditor.tsx) 为编辑器入口；**不能据此声称已有同等字幕 SRT 生成器**。 | **P5** |
| 9 **配乐** | `src/drama_factory/pipeline/offline_audio.py` 的 `mix_local_stems`、`src/drama_factory/pipeline/offline_render.py` 的离线合成路径：**复用输入 WAV 与混音函数**；缺 CLI 自动选择不含版权风险的合成背景音及 `08_music.json`；不调用 Lyria/外部服务。 | [`pipelines/script2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/main/pipelines/script2video_pipeline.py)、[`utils/video.py`](https://github.com/HKUDS/ViMax/blob/main/utils/video.py) 负责视频组织/拼接，**未核实独立配乐生成 API**。 | [`front/src/pages/aiStudio/editor/VideoEditor.tsx`](https://github.com/Forget-C/Jellyfish/blob/main/front/src/pages/aiStudio/editor/VideoEditor.tsx) 可管理多轨剪辑；不能代替无密钥合成音乐 Provider。 | **P5** |
| 10 **合成** | `src/drama_factory/pipeline/offline_render.py` 的 `render_approved_preview` 生成可播 H.264/AAC/mov_text MP4，`src/drama_factory/pipeline/offline_audio.py` 的离线混音、`src/drama_factory/jobs/offline_worker.py` **可直接复用**；缺单 CLI 统一调度、JSON manifest 持久化、校验式单步重跑。 | [`utils/video.py`](https://github.com/HKUDS/ViMax/blob/main/utils/video.py) 的 `concatenate_video_files`，[`pipelines/script2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/main/pipelines/script2video_pipeline.py) 负责最终产片。 | [`front/src/pages/aiStudio/editor/VideoEditor.tsx`](https://github.com/Forget-C/Jellyfish/blob/main/front/src/pages/aiStudio/editor/VideoEditor.tsx) 是剪辑导出工作台；**未确认可直接调用的后端 FFmpeg 合成管线**。 | **P6** |
| 11 **QA** | `src/drama_factory/pipeline/offline_qa.py` 的 `inspect_offline_delivery`、`src/drama_factory/pipeline/offline_review.py`、`src/drama_factory/pipeline/g1_benchmark_metrics.py` 的技术/Mock 指标：**直接复用**；缺结果自动落 `10_qa.json`、失败防发布与 CLI 非零退出码。**通过技术 QA ≠ 真实人物/版权/发布 QA**。 | [`agent_runtime/vimax_adapters.py`](https://github.com/HKUDS/ViMax/blob/main/agent_runtime/vimax_adapters.py) 有按产物检查依赖、失效下游文件、渲染准备度的逻辑，供 **P6** 借鉴规则思想。 | [`backend/app/services/studio/shot_video_readiness.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_video_readiness.py)、[`backend/app/core/task_manager/manager.py`](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/core/task_manager/manager.py) 做任务与视频准备度；但真实画面内容检测需 G1 盲测恢复后再评估。 | **P6** |

## 3. P1–P-final 最小缺口（每项一个 Req、一个 PR）

下表是 AMEND-005 的**新 P 系列需求**，`P*` 为流水线缺口序号；对应 `R*` 是 **STAGES 的需求 ID 映射**。只做其 **Fake / 本机离线切面**，不会标记 R4.1 的真实 Claude、R3.3 的真实 Lyria、R3.4 的正式发布质量、G1 真人盲测为已验收。

| P Req | 对应 STAGES Req | 本次只需新增的连接 | 复用 / 验收（全 Fake、无密钥） |
|---|---|---|---|
| **P1：梗概→Bible Fake 入口** | **R4.1**（Fake 版）、R4.2（仅既有 prompt 分层） | 从本地原创梗概文件读取 UTF-8→格式/大小限制、SHA256→确定性生成含人物、场景、基础设定的 Story Bible JSON；使用已有 Series/Bible schema，不加表。 | 复用 `pipeline/text.py`、`models.py`；相同输入稳定、无秘密/无 API、无真实文本模型。 |
| **P2：Bible→剧本→分镜适配** | **R4.1**（Fake）、**R3.1**（Fake 人工审批测试） | 用现有 Fake `ScriptOutline` 产出有 2 位虚构角色、中文对白、镜头开/收衔接、60–90 秒的合法 `screenplay.zh.v1` JSON；调用现有校验及审核/提交逻辑，Fake 演示审批必须显式标识为**测试专用**。 | 复用 `FakeTextProvider`、`screenplay.py`、`local_story_workflow.py`；不让未审核真剧本绕过门禁。 |
| **P3：角色资产与引用绑定** | **R2.1、R2.3**（Fake） | 在已有 Series 资产存储中建立确定性 Fake actor/scene/voice、版本哈希；逐镜为演员/场景提供对应具体资产引用，并为未来 Provider 准备精确映射；不复制真实照片或触发定妆照。 | 复用 `assets/routes.py`、`pipeline/shot_reference_board.py`、`pipeline/contracts.py`；跨剧资产拒绝。 |
| **P4：逐镜 Fake 视频调度** | **R3.2**（Fake）、R2.3（连接） | 将合法 Episode/Shot 转到已有 Fake 作业工人；每镜 JSON 提供 shot_id、持续秒数、引用版本、文件/媒体 SHA256、provider=`fake`，无真实供应商调用，保留镜头级重跑语义。 | 复用 `jobs/shots.py`、`jobs/offline_worker.py`、`pipeline/offline_render.py`；确认 Fake VideoResult 不会被误写成真实 MP4。 |
| **P5：对白→字幕→配乐离线接线** | **R3.3**（Fake）、R2.1（声线引用） | 对逐镜中文台词输出**非人声合成 WAV 时间槽**、SRT 片段时间/配乐合成占位、字幕与配乐 JSON；不新增 TTS 恢复链、不调用 Lyria。 | 复用 `providers/dialogue_audio.py`、`offline_cast_timeline.py`、`offline_render.py`、`offline_audio.py`；音频明确声明 synthetic/non-speech。 |
| **P6：总控 CLI + 合成/QA + JSON 单步重跑** | **R4.4**（Fake）、**R3.4**（仅技术 QA）、R3.1–R3.3（接线） | 只新增本地 `scripts/fake_episode.py` 或等价 CLI；串 P1–P5，按阶段写/校验 JSON、依输入哈希决定重用或重做阶段；导出 `episode.fake.mp4`、manifest、`10_qa.json`，故障非零退出。 | 直接复用 `render_approved_preview`、`inspect_offline_delivery`、现有媒体缓存；不得重写 FFmpeg。 |
| **P-final：端到端验收与交接** | **R4.4**（Fake 的 CLI 端到端验收） | 一个**本地合成梗概输入文件**执行单命令，得到合法 60–90 秒 **Fake** MP4 + 每阶段可恢复 JSON；重复运行证实幂等；运行不访问网络/新 Secret。 | 真实 FFmpeg/ffprobe 仅校验合成文件，0 付费调用；CI artifacts **只含完全合成内容**，绝不上传用户素材。 |

### 顺序与 PR 的边界

- 按 **P1 → P2 → P3 → P4 → P5 → P6 → P-final**，每项**单独 PR**；P0 只作本差距分析。P2/P3 可在实现内部细化适配次序，但不得把两项 Req 混进同一 PR。
- 一个 P Req 可能映射多个既有 R 编号，那是**复用/覆盖关系**，不是允许同时改多个 G 阶段真实需求；PR 只能声明一个 `Req: Pn`，另注明 `STAGES mapping: R*`。AMEND-005 已授权这条 P 链，不代表 G2/G3/G4 真人退出条件完成。
- 优先**调用已有模块**；若其假数据需要以新的公开接口接线，只能在所属 P Req 中加最小适配。不得把 P0 预定的产物字段作为已存在的代码假设。
- Fake 生成也应走既有版权、审核和安全边界的**离线演示方式**；测试性的自动确认必须与生产路径隔离、明确标注 `fake_only`，不能升级真实授权。
- **不重复做**云存储、作业恢复实验、Turso 迁移、UI、新小说改编、真人语音、商业镜头质量评分；不改 `AMEND.md`、`STAGES.md`、`GUARDRAILS.md` 等治理文件。

## 4. 外部源码、借鉴与许可证边界

- ViMax **MIT**：[许可证](https://github.com/HKUDS/ViMax/blob/main/LICENSE)、[Idea2Video Pipeline](https://github.com/HKUDS/ViMax/blob/main/pipelines/idea2video_pipeline.py)、[Script2Video Pipeline](https://github.com/HKUDS/ViMax/blob/main/pipelines/script2video_pipeline.py)、[Screenwriter](https://github.com/HKUDS/ViMax/blob/main/agents/screenwriter.py)、[StoryboardArtist](https://github.com/HKUDS/ViMax/blob/main/agents/storyboard_artist.py)、[角色画像](https://github.com/HKUDS/ViMax/blob/main/agents/character_portraits_generator.py)、[视频合并](https://github.com/HKUDS/ViMax/blob/main/utils/video.py)。
- Jellyfish **Apache-2.0**：[许可证](https://github.com/Forget-C/Jellyfish/blob/main/LICENSE)、[分镜拆分](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/script_division.py)、[镜头资产链接](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_assets.py)、[视频生成准备度](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_video_readiness.py)、[视频任务](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/core/tasks/video_generation_tasks.py)、[镜头对白](https://github.com/Forget-C/Jellyfish/blob/main/backend/app/services/studio/shot_dialogs.py)。
- 这里的引用是**确切存在的源码路径和职责比较**，并非保证两库在中文真实演员、配音版权、SRT 和费用方面具备相同解决方案；没有确认能力时明确写“未验证”。**P0 未复制任何源码**，因此 `docs/REFERENCE_PROJECTS.md §7` 暂无新增的代码借鉴登记；后续一旦直接移植才需正式登记与保留许可证。
- `huobao-drama` 属 CC BY-NC-SA，`waoowaoo` 属 Elastic：只可在未来参照**思路**，不可复制商业系统代码（AMEND-005）。

## 5. P-final 成功条件与所有者测试挂起

**Fake 完成标准（可自动验收）**：从合成原创 `idea.txt` 一条 CLI 得到实际可解码、总时长 60–90 秒、9:16、带 `FAKE` 明确标记的 MP4；有十一阶段的可读 JSON 与可验证 SHA256/目录隔离；相同输入复跑不重复提交任务；单步重跑只重建受影响下游；全部 scope + 离线 CI 全绿；模型调用次数 **0**、实际花费 **US$0**。不引入真实模型访问权限。

**真实测试仍 pending**：六张真实 AI 定妆照、三家模型九镜对照、中文真人对白/口型、独立商用版权、人审评分、准确真实账单、G1 ADR-010 等皆未执行。Issue **#116 / #119 / #120 保持打开且不处理**。

**P-final 合并后**，才新开一次 `[需要所有者]` Issue：附上**已真实产生且可访问的合成 MP4 CI artifact 链接**，提出 Omni 360p 全链路一次真实测试，**预计 ≤ US$3**；这是**建议预算而非承诺的供应商硬限额**。在所有者明确批准且实际可控之前不发起该测试；当前 P0 **不创建测试 Issue、不开通 API Key、不生成 Fake 视频**。
