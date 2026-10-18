# 成熟开源工程复用手册｜源文件、依赖边界与移植门槛

> 本文是 [开发 Bible](../DEVELOPMENT_BIBLE.md) 的可实施源代码索引。校验于 2026-10-19；**先从固定 commit 核对源码和 LICENSE，再决定复用**。本文件是设计提案，不等于第三方代码已纳入本仓库。
>
> 固定版本：`OpenMontage@c8066452325cb57c8fc1ba8c2a71b6e8842e6b65`；`HyperFrames@dc0e80e73af185cc892ea90d5a9f1412a055e9a1`；`ViMax@fd4b72e7731be6e5f88486206d25ea59849b0285`；`Jellyfish@a9678194ddf2d9be3ccbe78d4287d87d5089e123`。实现前可重新核对上游 HEAD，若版本变化，评估差异而不是盲目更新。
>
> 许可核查基线：OpenMontage 根 LICENSE = **AGPL-3.0**；HyperFrames 根 LICENSE = **Apache-2.0**；ViMax **MIT**、Jellyfish **Apache-2.0** 按仓库已有参考审计 `docs/REFERENCE_PROJECTS.md` 的固定提交记录；**直接复制前仍要重新读取相应 LICENSE 与 NOTICE，并逐目录核实是否有第三方特殊条款或模型权重限制**。

## A. 四种复用方式——优先级从高到低

1. **保留现有实现，只借验收规则/设计**：最便宜且最稳。适用于已有 `fake_episode.py` 阶段状态、FFmpeg、现有审片脚本。
2. **直接引入受许可支持的库接口**：只有实际需求和测试可控，且不会连带引入整套前后端/数据库时才做。
3. **小范围代码移植**：确定上游源文件、入口函数、依赖、许可证、署名、NOTICE，复制必需部分及最小测试；实现可隔离，代码出处永久记录。
4. **完整项目替换/引入新平台**：默认禁止。必须先量化现有系统做不到的可复现需求、转换成本、许可证与回退策略，由所有者单独批准。

复用不是按 Star 排序，也不是将四套项目全部装进去。**任务需求决定模块，模块决定适配接口，提供商端口最后选。**

## B. OpenMontage：学完整流水线的骨架，不搬它的 Agent 平台

仓库 https://github.com/calesthio/OpenMontage · AGPL-3.0 · 固定 SHA 见页首。

| 已检查的真实上游文件 | 机制 / API | 我们要实现的**最低借鉴单位** | 不应复制 |
|---|---|---|---|
| [`pipeline_defs/cinematic.yaml`](https://github.com/calesthio/OpenMontage/blob/c8066452325cb57c8fc1ba8c2a71b6e8842e6b65/pipeline_defs/cinematic.yaml) | `stages` 为每个阶段定义 `required_artifacts_in`、`produces`、`checkpoint_required`、`human_approval_default`、`review_focus`、`success_criteria` | 用既有 11 阶段 JSON 标记前置输入、产物哈希、成功条件，明确关键人工审批点 | 整个 YAML 驱动多套视频产品的新编排器 |
| [`lib/pipeline_loader.py`](https://github.com/calesthio/OpenMontage/blob/c8066452325cb57c8fc1ba8c2a71b6e8842e6b65/lib/pipeline_loader.py) | `get_stage_order`、`get_stage_human_approval_default`、`get_stage_review_focus` | 阶段顺序和审查策略变成可查的规范，映射现有 Pydantic 及审批 API | 第二套可配置 DSL/解析器 |
| [`lib/checkpoint.py`](https://github.com/calesthio/OpenMontage/blob/c8066452325cb57c8fc1ba8c2a71b6e8842e6b65/lib/checkpoint.py) | `validate_checkpoint`、`_enforce_stage_prerequisites`、`write_checkpoint`、历史 checkpoint | 将原有 `00..10` JSON 和真实单镜 receipt 关联：前置阶段版本不匹配则停止，下游按哈希失效；保留人工审批 | 另造一套 checkpoint 数据库 |
| [`lib/delivery_promise.py`](https://github.com/calesthio/OpenMontage/blob/c8066452325cb57c8fc1ba8c2a71b6e8842e6b65/lib/delivery_promise.py) | `DeliveryPromise.validate_cuts` 防止剪辑产物违背视频承诺 | 订立“真实运动镜头、原生对白、9:16、人物一致、没有乱分屏”的交付语义与内容 QA 条件 | 照搬该项目面向广告/幻灯片的评分规则 |
| [`lib/variation_checker.py`](https://github.com/calesthio/OpenMontage/blob/c8066452325cb57c8fc1ba8c2a71b6e8842e6b65/lib/variation_checker.py) | `check_scene_variation` 静态镜位、重复分镜、hero shot 多样性检查 | 编剧分镜提示的离线 lint（可选），**不能代替**实际视频质量检查 | 以其主观分数作发布裁决 |
| [`tools/cost_tracker.py`](https://github.com/calesthio/OpenMontage/blob/c8066452325cb57c8fc1ba8c2a71b6e8842e6b65/tools/cost_tracker.py) | estimate / reserve / reconcile / cost snapshot；含审批阈值模型 | 对齐“预估、已授权、可能已消费、供应商实账”四个不同费用字段 | 新的付费账本或绕开已用一次性 claim |
| [`backlot/README.md`](https://github.com/calesthio/OpenMontage/blob/c8066452325cb57c8fc1ba8c2a71b6e8842e6b65/backlot/README.md) | 项目文件、checkpoint、events.jsonl 直接导出只读看板；历史 replay | G5 之后考虑用已有 JSON 可观测性展示；先产数据再谈 UI | G4 时增加看板/Web 服务 |

**移植结论**：现在是 **idea-only**。AGPL 本身可以商用，但复用/修改/通过网络提供服务会有具体合规义务；我们选择在法律与产品发布路径明确前不把它的源码粘进私有商业项目。采用“独立写符合现有 Schema 的规则”，**不作逐行翻译式规避**，也不引入上游代码依赖。

**接受标准**：真正提升失败阶段恢复、避免带错资产的镜头出片、避免技术通过冒充内容通过；不增加新的生产数据库/状态持久层。

## C. HyperFrames：从“可声明的渲染意图”借技术，不换我们的 FFmpeg

仓库 https://github.com/heygen-com/hyperframes · Apache-2.0 · 固定 SHA 见页首。

| 上游确切源码 | 已核功能 | 我们的候选用法 | 引入条件 |
|---|---|---|---|
| [`packages/producer/src/renderRequest.ts`](https://github.com/heygen-com/hyperframes/blob/dc0e80e73af185cc892ea90d5a9f1412a055e9a1/packages/producer/src/renderRequest.ts) | `RenderRequest` 有 version、projectDir、outputPath、JSON-safe options（FPS、format、quality、render config）；验证及序列化函数 | 本仓库 `09_render` 增加清楚的“渲染意图 + 版本”，与当前 FFmpeg 实参对应 | 初始采用字段与验证思想；无需依赖 TypeScript 编译器 |
| [`packages/core/src/mediaTiming.ts`](https://github.com/heygen-com/hyperframes/blob/dc0e80e73af185cc892ea90d5a9f1412a055e9a1/packages/core/src/mediaTiming.ts) | `resolveMediaStartSeconds`、`cutToHostSlots` 定义局部/全局媒体时间轴 | 统一 12 镜真实实测时长 → 字幕 cue、配乐段、镜头时间的换算，不再只依赖理论 5 秒 | 用实测素材建立离线时间戳回归样例 |
| [`packages/core/src/compositionReadiness.ts`](https://github.com/heygen-com/hyperframes/blob/dc0e80e73af185cc892ea90d5a9f1412a055e9a1/packages/core/src/compositionReadiness.ts) | `scanPendingCompositionAssets`、`settleCompositionReadiness` 等处理媒体/图片/字体未就绪 | FFmpeg 运行前检查真实镜头存在、哈希/stream codec/字幕文件/配乐版权、来源可读 | 不为此引入 Chromium；已有 `assemble` 可覆盖多数 |
| [`packages/core/src/audioCarve.ts`](https://github.com/heygen-com/hyperframes/blob/dc0e80e73af185cc892ea90d5a9f1412a055e9a1/packages/core/src/audioCarve.ts) | voice 与 music 轨道识别、时序重叠、duck/频段避让分析 | 若未来添加配乐，只在说话区间自动降低音乐并确认原生对白未损坏 | 首先重用 `offline_audio.py` / FFmpeg，只做本地已授权音乐 PoC |
| [`README.md`](https://github.com/heygen-com/hyperframes/blob/dc0e80e73af185cc892ea90d5a9f1412a055e9a1/README.md) | CLI `init/lint/preview/render`；HTML/CSS/GSAP Seek-safe frame rendering | G4 内容质量够用后，10 秒实验动效字幕或片头；用同一 MP4 走 FFmpeg vs HyperFrames 比较 | 使用无隐私测试片、隔离 Node/Chromium，质量收益 > 运维开销才采纳 |

**不当做**：HyperFrames 不是直接生成同脸同声的角色演技，也不是替代 Omni 的视频模型。仓库视频主要是 H264/AAC 真人生成片段，简单封装/字幕/配乐 FFmpeg 仍更轻。

**PoC 决策表**（实施前记录）：字幕时间准确性、源音轨听感、视频流画质/是否转码、帧级确定性、CPU 时间、包体、Node/浏览器依赖、平台许可与升级成本。没有明确收益，不合并 HyperFrames 运行时。

## D. ViMax：优先复用 Python 编剧/分镜/多机位依赖语义

仓库 https://github.com/HKUDS/ViMax · 本仓库已审 MIT · 固定 SHA 见页首。

| 上游路径 | 可借的成熟部分 | 对接当前文件 | 验收 |
|---|---|---|---|
| [`agents/storyboard_artist.py`](https://github.com/HKUDS/ViMax/blob/fd4b72e7731be6e5f88486206d25ea59849b0285/agents/storyboard_artist.py) | 镜位/动作/每镜叙事目的/角色台词分镜 Prompt 结构，已存在类 `StoryboardArtist` | `pipeline/screenplay.py`、`screenplay_video_plan.py`；先提小范围 Prompt 结构映射，不搬整套 LLM 链 | 原有中文 Schema 校验不退步，角色不被加入未出现镜头 |
| [`pipelines/script2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/fd4b72e7731be6e5f88486206d25ea59849b0285/pipelines/script2video_pipeline.py) | `_group_shots_into_cameras`、`_collect_priority_shot_idxs` 表达镜头依赖和优先生成 | 现有 `director_timeline.py` / `screenplay_video_plan.py`；仅未来需要继承尾帧/镜位时复用 | 不能让依赖排序打乱剧本 shot_id 和 12 镜对应 |
| [`agents/character_portraits_generator.py`](https://github.com/HKUDS/ViMax/blob/fd4b72e7731be6e5f88486206d25ea59849b0285/agents/character_portraits_generator.py) | 固定人物画像/多角度身份锚定的素材工作流 | `assets/references.py`、`shot_reference_board.py` | 同一角色的版本 SHA 正确注入计划，**不可宣称 Omni 已使用参考图** |
| [`pipelines/idea2video_pipeline.py`](https://github.com/HKUDS/ViMax/blob/fd4b72e7731be6e5f88486206d25ea59849b0285/pipelines/idea2video_pipeline.py) | 梗概→编剧→分镜→生成的阶段连接 | 已有 `scripts/fake_episode.py` | **只借遗漏的连接逻辑**，完整 Fake 11 步不重写 |

优先采用可单测的 Prompt 模板、小工具/解析；原 SDK、依赖堆栈、完整 provider 运行器不直接搬。

## E. Jellyfish：优先复用镜头与角色/道具绑定、可生产性检查

仓库 https://github.com/Forget-C/Jellyfish · 本仓库已审 Apache-2.0 · 固定 SHA 见页首。

| 上游路径 | 确认存在的能力 | 我们怎么接 |
|---|---|---|
| [`backend/app/services/studio/shot_character_links.py`](https://github.com/Forget-C/Jellyfish/blob/a9678194ddf2d9be3ccbe78d4287d87d5089e123/backend/app/services/studio/shot_character_links.py) | 镜头与角色的显式连接、顺序、实体校验 | 复用 `ScreenplayShot.character_ids` + 现有资产 ID 和版本，出错时拒绝生成 |
| [`backend/app/services/studio/shot_assets.py`](https://github.com/Forget-C/Jellyfish/blob/a9678194ddf2d9be3ccbe78d4287d87d5089e123/backend/app/services/studio/shot_assets.py) | 项目级场景/服装等关联及镜头链接读取 | 在本仓库 SQLite 既有资产表上添加读取/验证薄适配，不新建一套模型 |
| [`backend/app/services/studio/shot_video_readiness.py`](https://github.com/Forget-C/Jellyfish/blob/a9678194ddf2d9be3ccbe78d4287d87d5089e123/backend/app/services/studio/shot_video_readiness.py) | `get_shot_video_readiness` 聚合参考帧、候选状态、活动视频任务、model/provider 就绪性 | 按我们 Omni 的实际能力降级要求：prompt-only 时不谎报 reference frame 注入；生成前报告未绑定/缺角色/不兼容能力 |
| [`backend/app/services/studio/shot_dialogs.py`](https://github.com/Forget-C/Jellyfish/blob/a9678194ddf2d9be3ccbe78d4287d87d5089e123/backend/app/services/studio/shot_dialogs.py) | 逐镜对白与角色关联 | 对接现有 `DialogueCue`，为后续真声轨转写保留 speaker_id / expected_text |

**取舍**：只借数据关系和就绪条件；拒绝直接移植 Jellyfish 的 MySQL 数据库模型、Redis/任务中心、前端。与我们 SQLite/Pydantic 契约一致后，才讨论实际导入 Python 代码。

## F. 逐项引入验收表——每次都必须填，缺一不可

```text
Owner / Stage: G4 / Req: R4.4 or R4.3
目标缺陷（可复现）：______
本仓库现有代码/行为/SHA：______
缺口证据（真实源视频/离线测试）：______
候选上游 repo@commit 和准确 path:line：______
LICENSE 与 NOTICE、依赖/权重条款：______
方式：沿用现有 / 借设计 / 直接依赖 / 最小移植
移植功能边界、变更行数、替代方案：______
输入输出契约及异常/重试语义：______
原版测试/对照测试/媒体回归：______
费用与模型调用：0 / 需所有者批准（禁止模糊）
贡献归属与 docs/REFERENCE_PROJECTS.md §7 登记：______
回滚：恢复旧 Provider/FFmpeg 路径，不改历史媒体哈希
```

## G. 外部源代码采用状态（审查日）

| 项目 | 源文件核查 | 已导入到本仓库 | 下一步 |
|---|---|---|---|
| OpenMontage | 上述 Python/YAML 路径已核对 | **否** | 只借流程、关卡理念 |
| HyperFrames | 上述 TS 路径已核对 | **否** | 优先规范现有后期时间线；PoC 后决定 |
| ViMax | 关键 Python 路径存在；项目既有复用审计 | **本轮否** | W2 中确定实际需移植的最小函数 |
| Jellyfish | 关键 Python 服务路径存在；项目既有复用审计 | **本轮否** | W2 对接当前 shot/asset schema |

未合并的文档研究不能被后续模型描述成“已复用代码”。每一次实际复制/修改或引入源码，都必须写回 `docs/REFERENCE_PROJECTS.md §7`，同时在 PR 里写明固定 commit。
