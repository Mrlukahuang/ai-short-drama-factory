# 开发阶段、需求与交付要求（STAGES）

> 本文件取代 `docs/ROADMAP.md` 作为**唯一有效的阶段计划**。ROADMAP 保留为历史记录。
> 规则：**上一阶段的「退出条件」全部满足并经所有者确认之前，不得开始下一阶段的任何工作。**
> 每个 PR 必须在描述中写明 `Stage: Gx` 和 `Req: Rx.y`。对不上任何需求编号的 PR 不合并。

当前阶段见 `docs/handoff/CURRENT.md`。

```
G0 冻结校准 → G1 视频盲测 → G2 演员资产 → G3 30秒单场景 → G4 60秒整集 → G5 批量可靠性 → G6 小说改编 → G7 云端
                 ▲ 现在要做
```

---

## G0 冻结与校准（本 PR，2026-10-15）

| 需求 | 交付物 | 验收 |
|---|---|---|
| R0.1 | `AMEND.md`、`docs/CHARTER.md`、`docs/STAGES.md`、`docs/GUARDRAILS.md` | 所有者审阅合并 |
| R0.2 | `docs/REFERENCE_PROJECTS.md`、`docs/MODEL_LANDSCAPE.md` | 链接可访问，许可证标注 |
| R0.3 | `AGENTS.md`、`CLAUDE.md` 指向新读取顺序；`docs/handoff/` 交接机制 | Claude Code / GPT 开工时会先读 AMEND.md |
| R0.4 | `scripts/scope_guard.py` + CI 检查冻结路径和 PR 描述字段 | 改冻结路径或缺 `Stage:` 的 PR 自动失败 |
| R0.5 | `config/model_registry.json` 更新到 2026-10-15 | 移除 Sora，新增 Seedance 2.5 / Kling 3.0 Omni |

**退出条件**：本 PR 合并。

---

## G1 真实视频 A/B 盲测（下一步，最重要）

**要回答的问题**：哪个视频模型能稳定产出「同一对男女主、同脸、同声、中文对白自然」的镜头？声音走模型原生音频还是 TTS + 口型同步？

| 需求 | 交付物 | 验收 |
|---|---|---|
| R1.1 | `providers/seedance_video.py`（Seedance 2.5）+ Fake + 契约测试 | 无密钥时 CI 全绿；接口与 `google_omni_video.py` 一致 |
| R1.2 | `providers/kling_video.py`（Kling 3.0 Omni，模型 ID 可配置以便换 4.0）+ Fake + 契约测试 | 同上 |
| R1.3 | 统一 `VideoProvider` 协议（输入：prompt、参考图、可选音频参考、时长、比例；输出：MP4 路径、task_id、实际费用） | 三个 Provider 都实现该协议 |
| R1.4 | 2 位主角定妆照：Nano Banana 2.1，每人 3 张（正脸/侧脸/半身） | 人工批准，存为资产版本 |
| R1.5 | `scripts/ab_benchmark.py` + 手动 workflow `video-ab-benchmark.yml`：3 个固定镜头 × 3 个模型 × 1 次 | **总预算硬上限 30 USD**；需输入确认词才运行 |
| R1.6 | 自动指标：用 `gemini-3.5-transcribe` 转写实际台词，与剧本比对字准确率；ffprobe 技术检查 | 结果写入 `benchmarks/g1/results.json`（不含媒体） |
| R1.7 | 盲测评分页：隐藏模型名，按 5 项打分（脸一致、声音一致、口型、中文发音、动作自然） | 所有者完成打分 |
| R1.8 | `docs/G1_BENCHMARK_REPORT.md` + **ADR-010** 选定主视频模型、备选模型、音频路线 | 所有者签字 |

**3 个固定镜头**（`benchmarks/g1/shots.json`）：
1. 男女主同框、各说一句中文对白（双人一致性 + 对白）
2. 女主特写、带情绪的一句长台词（口型 + 情绪）
3. 男主起身走向女主（动作 + 接续上一镜头尾帧）

**每个模型测两种音频路线**（模型支持时）：A = 原生音频 + 音色参考；B = 无声视频 + Gemini 3.8 TTS + LatentSync 口型（B 路线的口型同步可以只做 1 个镜头的可行性验证）。

**禁止**：在 G1 里做恢复对账、重试框架、数据库表扩展、UI 新页面。结果文件用 JSON 即可。

**退出条件**：ADR-010 合并，写明主模型、音频路线、实测每秒成本、合格率。

---

## G2 演员资产标准化

| 需求 | 交付物 | 验收 |
|---|---|---|
| R2.1 | 演员资产包规格：`character_id`、多角度图、服装版本、音色参考（音频路线 A）或 TTS voice（路线 B） | Schema + 测试 |
| R2.2 | 一键生成定妆照 → 人工选图 → 锁定版本（复用 PR-07a/07b6） | 2 位主角 + 1 位配角完成 |
| R2.3 | 参考图自动注入视频请求（`@character` 引用，参考 huobao-drama / ViMax 做法） | 生成请求里带精确资产版本哈希 |

**退出条件**：3 个角色资产锁定；同一角色在 5 个不同镜头中人工判定为同一人 ≥ 4 个。

---

## G3 30 秒单场景真实成片（第一个真实成品）

| 需求 | 交付物 | 验收 |
|---|---|---|
| R3.1 | 手写 1 场戏剧本（4–6 镜头）→ 走现有审批流 | 复用 PR-03/07b2 |
| R3.2 | 逐镜头调用 G1 选定模型，失败只重试该镜头 | 复用 PR-16a 账本，不新建表 |
| R3.3 | 字幕（转写对齐）+ 配乐（Lyria 3.5 或免版税素材）+ FFmpeg 合成 | 复用 PR-11/15 |
| R3.4 | 自动技术 QA + 人工审片记录 | 产出 MP4 + 费用清单 |

**退出条件**：一条 30 秒 MP4，所有者评价「可以发」；实际成本记录在案。

---

## G4 60 秒整集 + LLM 编剧（MVP）

| 需求 | 交付物 | 验收 |
|---|---|---|
| R4.1 | 接入真实 TextProvider（Claude Sonnet 5.5）：梗概 → Story Bible → 分集剧本 → 分镜 JSON | 输出通过现有 Screenplay 校验 |
| R4.2 | 编剧 Skills：借鉴 drama-skills / shuohao-skills 的分层提示（钩子、反转、结尾悬念） | Prompt 版本化 |
| R4.3 | 视觉连续性自动预检：Gemini 视觉模型对相邻镜头打分，人只复核被标记的 | 替代 PR-07b7 的纯人工对照 |
| R4.4 | 整集一键流水线（CLI 即可）：剧本审批后自动跑完所有镜头 → 合成 → QA | 12 镜头坏 1 个只重跑 1 个 |

**退出条件（= 北极星达标）**：一集 60–90 秒成片；合格镜头率 ≥ 50%；每合格分钟成本和单集人工时长有实测数。

---

## G5 批量与可靠性

只有 G4 证明能出片后才做。

- R5.1 同时生产 3 集，预算三级门禁（复用 PR-17）
- R5.2 评估是否需要 Temporal（参考 waoowaoo）或保持 SQLite + 现有 Worker。**先写评估文档，所有者批准后才实现**
- R5.3 解冻 AMEND-001 的条件在此阶段评估

## G6 小说改编分支

- R6.1 PR-05b 事件抽取（Gemini 3.8 Flash 长上下文）
- R6.2 PR-06b 季规划审核
- R6.3 小说 → 同一 Episode Schema → 走 G4 流水线
- 借鉴：ViMax Novel2Video、Toonflow、ArcReel

## G7 云端与多人

对象存储、鉴权、远程 Worker、Turso（届时重新评估）。**最后做。**
