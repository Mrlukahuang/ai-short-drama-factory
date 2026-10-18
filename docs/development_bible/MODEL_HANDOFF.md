# 多模型协作与零上下文偏差交接协议 v1.0

> 本协议是 [开发 Bible](../DEVELOPMENT_BIBLE.md) 的执行文件。适用于不同 GPT、Claude、Codex、模型及不同聊天窗口。**GitHub main / PR / Actions / Artifact / README 是证据，聊天中的记忆或口头百分比不是证据**。此文不创造自动代理执行能力；模型只有在实际连接了仓库、可操作并返回工具回执时才能宣称写入/合并。

## 1. 指挥关系与权威顺序

- **所有者**：确定产品目标、模型/费用与许可选择、G4 退出/发布签字、冻结区或治理文件解锁。不能把一次批准解释成永久收费许可。
- **协调模型（Integrator / Architect）**：只做任务拆解、更新交接、接口/许可证评估、审查 PR 与证据、冲突协调、阶段验收汇总。**不同时修改另一个模型正在负责的源码文件**。
- **执行模型（单包 Owner）**：一次只认领一个 W 包、一个正式 Stage/Req、一个 Git 分支；无权限时只输出补丁/文档和真实核验结果，不假称已部署。
- **复核模型（Reviewer）**：只读检查本包的变化、第三方许可、测试、数据保护和下游契约是否改变；可以提出修改，但不直接在执行模型分支上大范围改写。

权威排序：`AMEND.md`（Active 修正）→ `AGENTS.md` / `docs/GUARDRAILS.md` 的基本治理 → `docs/handoff/CURRENT.md`（单一当前工作）→ `docs/STAGES.md`（正式阶段、退出条件）→ `docs/DEVELOPMENT_BIBLE.md`（实施技术规范）→ `docs/development_bible/*`（细项手册）→ `docs/REFERENCE_PROJECTS.md`（开源移植登记）→ issue / PR 说明。冲突时不自行改治理来配合本 Bible，而是提议所有者裁决。

## 2. 固定角色与写权限分区（阶段移交后生效）

| 模型角色/可用别名 | 负责 W 包 | **唯一主要可写文件集合** | 禁止触碰 |
|---|---|---|---|
| M0 协调/架构 | W0、W5、阶段切换 | `docs/DEVELOPMENT_BIBLE.md`、`docs/development_bible/*`、本包 issue/PR 描述；交接登记由集成人在合并时更新 | 在 M1–M4 工作期间代写 Provider/音频/角色业务逻辑 |
| M1 剧本与资产 | W2 | `src/drama_factory/pipeline/screenplay_video_plan.py`、既有 `assets/references.py`、`pipeline/shot_reference_board.py`、对应测试/必要本包文档 | `scripts/run_gpt_video_three.py`、`scripts/assemble_gpt_video_three.py`、后期主脚本 |
| M2 视频生成与修复 | W1 | `scripts/run_gpt_video_three.py`、`scripts/complete_gpt_episode.py`、`scripts/repair_gpt_episode_offline.py`、`providers/google_omni_video.py`、对应测试 | `pipeline/screenplay_video_plan.py`、`postprocess_gpt_episode_offline.py`；不得绕过已用付费 claim |
| M3 后期与合成 | W3 | `scripts/postprocess_gpt_episode_offline.py`、`scripts/assemble_gpt_video_three.py`、当前后期脚本范围的测试（其他共有模块仅经接口批准） | 改编剧/角色计划、Provider 发送参数、改冻结 TTS |
| M4 QA / 审片 | W4 | `src/drama_factory/pipeline/offline_qa.py` 的新增独立验证（须保留原语义）、`docs/GPT_EPISODE_VISUAL_REVIEW_20261019.md` 的后续新报告或本包新文档、对应测试 | 将内容 QA 成功误设为 G4 退出/发布成功，自动付费修镜 |
| M5 集成/发布验收 | W5 | `docs/handoff/CURRENT.md`、`docs/handoff/LOG.md`、合并记录与运行说明，**在最新 main 上改** | 与活跃模型冲突地修改生产业务代码；代所有者签发布许可 |
| M6 未来 G5–G7 专岗 | W6–W8 | **未分配；正式 G5/G6/G7 释放后重新声明** | 任何提前开发 |

这张表是**默认职责分配**，不是文件的永久独占许可。一个实际任务若必须跨多个领域的共享文件，先由协调模型冻结接口变更和 GitHub Issue，指定**唯一一个执行 Owner** 在同一分支做该小范围修改；其他模型只审查或在明确独立分支中做不重叠改动。团队可改变使用哪家模型，不能改变已冻结文件和业务契约的所有权。

**特别注意**：`docs/handoff/CURRENT.md`/LOG 属于全团队共享基线。非集成模型在 W 包 PR 收尾时依 AGENTS 要求更新交接，但须**串行**：不要两个分支同时改 CURRENT。实践上由当期 PR Owner 在收尾前先刷最新 main、锁定该次交接写入，再立即 PR/合并；其他模型暂停修改共享交接文件。

## 3. 一个模型从接任务到交付的 9 步固定协议

1. **Fresh fetch**：GitHub 获取 `main SHA`、`AMEND.md`、`AGENTS.md`、`CURRENT.md`、`STAGES.md`、`GUARDRAILS.md`，再读本 Bible、当期 W 包和外部复用记录；不得只看旧聊天摘要。
2. **识别唯一任务**：写 `Stage: G4 / Req: R4.4 / W#: W1 / deliverable: ...`；若当前 CURRENT 的唯一下一步与派发不一致，先只读核实差异/通知协调者，不能并行劫持其它任务。
3. **列出证据**：上一个通过的 main commit、Actions run、artifact、源媒体/剧本 SHA、已验证和未验证事项、费用/授权状态。
4. **先查可复用代码**：列出本仓库已经存在的入口和近似实现；再定位上游源码固定 SHA 与 LICENSE；给出 adapt/import/idea-only 决策。
5. **画最小 I/O 契约**：明确生产状态变更、失败/重试/回滚、精确文件 owner、最多一个正式 Req、一小批受控文件；需要其它模型改接口，先让协调者建契约决策记录。
6. **创建隔离分支**：从当前 main，而不是别人未合并的分支；不得直接 push main。不要新建无关抽象/数据库/Workflow。
7. **离线验证优先**：跑对应单测、全套必要 test/scope、FFmpeg/ffprobe 或复用真实已有 artifact 的离线端到端；日志不得包含密钥、私有媒体、版权原文。若调用收费 API，需可核实的独立授权。
8. **提交 PR / 审查 / CI**：PR body 包含 Stage/Req/W、来源 SHA、准确改动文件、测试与日志链接、许可登记、费用、限制、失败路径、下游影响。全绿后依 AMEND-004 规则可自合并，但治理/冻结/收费/阶段退出不得绕过所有者。
9. **冻结交接**：记录最终 main SHA、PR 合并状态、实际工作流 Artifact、验收、未完成和下一任务唯一入口；**不要把正在等待的未来调用描述成已经在后台运行**。给下一位模型的是可复制的材料与 GitHub 链接，不是“我记得”。

## 4. 交付包格式（下游模型必须能机械检查）

每个阶段工作包交付时，在 PR 描述或非秘密 Markdown artifact 中提供：

```yaml
handoff_schema: drama-stage-handoff.v1
project: Mrlukahuang/ai-short-drama-factory
date_nzt: YYYY-MM-DD
stage: G4
req: R4.4
work_package: W1
owner_role: M2-video
main_sha_at_start: "<40-char commit>"
pr_url: "https://github.com/.../pull/..."
pr_state: "open|merged|closed"
merged_main_sha: null  # 合并后才填
changed_paths: []
upstream_reuse:
  - repo_commit: "owner/repo@sha"
    source_path: "path/to/file"
    usage: "design-only|library|adapted-code"
    license_review: "not-needed|reviewed|blocked"
inputs:
  screenplay_sha256: null
  source_episode_report_sha256: null
  source_video_sha256: null
  artifact_url: null
outputs:
  contract_version: null
  manifest_path: null
  video_sha256: null
  artifact_url: null
verification:
  unit_test: "not_run|pass|fail"
  full_ci: "not_run|pass|fail"
  media_qa: "not_run|pass|fail"
  real_provider_generation: "not_run|pass|fail"
  content_human_review: "not_run|pass|fail"
  license_notice_check: "not_applicable|pass|blocked"
money:
  new_paid_model_calls: 0
  estimated_usd: null
  operator_authorization_url: null
  invoiced_actual_usd: null
safety:
  publish_approved: false
  same_face_verified: false
  same_voice_verified: false
  subtitle_alignment_verified: false
next:
  single_next_work_package: "W2"
  prerequisite_main_sha: null
  blocked_reason: null
  files_to_avoid: []
```

**字段纪律**：未知填 `null` / `not_run`，不能写假值；`invoiced_actual_usd` 只能取可信供应商账单；成功产生的媒体如果未上传 GitHub Artifact 就不能编造链接；历史原片哈希和新输出哈希要分开。

## 5. PR 描述统一模板（复制改值）

```markdown
Stage: G4
Req: R4.4
Work package: W1
Deliverable: <一句话、可自动/人工验收的交付物>
AMEND check: No frozen/governance paths; no new paid calls, or link to explicit owner approval

### Inputs / baseline
- Main SHA at start:
- Old validated artifact/run/sha:
- Contract version:

### Reuse before writing
- Repo existing module:
- Upstream project@commit/path/verified license:
- Reuse decision: existing / design only / minimal legal code adaptation
- New code needed because:

### Changes / ownership
- Owned files and expected side effects:
- Non-goals / other team paths untouched:

### Tests / evidence
- Unit test result:
- CI check URL:
- Existing REAL media offline run:
- New paid API calls/actual invoice:
- Technical QA / Content QA / Release decision (separate):

### Handoff
- Main SHA after merge:
- Current task remaining:
- Next single owner and work package:
- Known blockers and rollback instructions:
```

CI 检查 PR body 的 `Stage: Gx` 和 `Req: Rx.y`；不要只写 W 编号。对 frozen/governance 变更需要所有者按 `amend-approved` 审批，不能由模型给自己放行。

## 6. 典型跨模型接力示例

**M2 → M3**：M2 不说“单镜成功了”，而交 `shot_id=s07`、旧媒体 SHA、新媒体 SHA、其余 11 SHA 校验清单、来源 task ID（确有真实任务时）、批准 URL、原/新 parent delivery。M3 在刷新 main 和产物之后用新实测时长重算 07_subtitles/09_render，保留原生 AAC，不再触发 Omni。

**M3 → M4**：M3 交原声保留方式、SRT 的 `draft_from_script` 标记、真实 MP4 artifact、技术 QA result。M4 不能把推定字幕当字词转写；审片记录遇未知先标 unknown，发现 s03/s09/s07 缺陷要附可复现时间点。

**M4 → M5**：M4 交 human approval / unknown / failed 分镜表及真实样片 SHA。M5 计算镜头合格率、实际合格分钟成本、人力时间，缺账单或所有者签字则保持 G4 `pending`，不能据 CI 全绿自动进入 G5。

## 7. 保护并行开发不冲突

- **代码写权限**：同一文件同一时间只允许一个执行模型有写主权。协调模型可以通过 GitHub Issue 做只读审查/规划。
- **契约冻结优先**：上游 schema 更改先产契约审查 PR，合并后下游从新 main 开分支；下游不得依赖未合并的另一个模型分支。
- **README/CURRENT/LOG 共享文件**：按收尾次序串行更新并标示 main SHA，发现 PR 冲突应 rebase/reconcile，而不是强推覆盖。
- **CI 只看当前实际结果**：PR 不是“已合并”，成功编译不是“真实 API 已调用”，GitHub issue 计划不是“已完成”。
- **权限障碍**：如果工具无法创建 Codex Cloud 任务、读私有 repo、合并或真正执行视频，必须准确报告能力边界；不要把 GitHub 评论假装为已派发或运行中的子代理。
- **并行可以做什么**：M1 只读研究 Jellyfish/ViMax、M3 只读研究 HyperFrames、M4 审查历史真实媒体；三者不改 W1 当前在用的脚本时可以并行。

## 8. 新聊天/新模型启动模板（单包交付）

```text
项目 Mrlukahuang/ai-short-drama-factory。你当前是 <M2 视频生成模型>，
本任务仅 <W1 单镜修复闭环>，Stage: G4 / Req: R4.4。
必须先从最新 main 读取 AMEND.md、AGENTS.md、docs/handoff/CURRENT.md、
docs/STAGES.md、docs/GUARDRAILS.md、docs/DEVELOPMENT_BIBLE.md、
docs/development_bible/STAGE_DELIVERABLES.md（只读本 W 包）、
docs/development_bible/OPEN_SOURCE_REUSE.md、
docs/development_bible/MODEL_HANDOFF.md，并核实 Issue #164。
不要依据旧聊天默认认为本阶段仍在做同一事情。
先说明此刻的 main SHA、已验证的真实 Run/Artifact、目前缺口，
查现有代码与第三方许可，然后只做本包最小修改及测试，单 Req/单 PR。
不碰别的模型负责的文件，不碰冻结区，不做未经独立批准的收费视频。
交付 PR URL、CI、实际合并 SHA（若已合并）、输入输出哈希和完整
drama-stage-handoff.v1，交给下一个模型；没有真实工具回执不要声称成功。
```

任何模型如果拿不到必要附件，先按 GitHub Run/Artifact 的确切标识查找；不可依靠手写路径猜测拥有视频媒体。此模板同样适用于 Claude、GPT、Codex 等，并不要求它们共享聊天上下文。
