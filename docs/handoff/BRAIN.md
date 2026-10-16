# 大脑交接文件（BRAIN.md）— 指挥层如何控制下面的开发分支

> 给**下一个“大脑”会话**（新开的 Claude / GPT 规划对话）和所有者看的。
> 执行层 Agent 不需要读本文件，它们读 `AMEND.md` → `docs/handoff/CURRENT.md`。
> 最后更新：2026-10-17（Claude）。状态快照见第 6 节，**接手时先按第 7 节核对实时状态**，不要相信本文件里的旧数字。

---

## 1. 三层结构

```
┌──────────────────────────────────────────────┐
│ 所有者（Mrlukahuang）                          │  决定方向、批准花钱、看片打分、合并治理 PR
└───────────────┬──────────────────────────────┘
                │ 聊天里说想法 / 发截图 / 发成片
┌───────────────▼──────────────────────────────┐
│ 大脑（规划对话：Claude 或 GPT，一次只开一个）      │  调研、审计 GitHub、写 AMEND、写给执行层的指令、
│                                              │  核对执行层汇报是否属实、帮所有者看片
└───────────────┬──────────────────────────────┘
                │ 只通过仓库文件 + Issue + 粘贴指令 控制
┌───────────────▼──────────────────────────────┐
│ 执行层（GPT / Claude Code，一次只有一个在写代码）   │  按 CURRENT.md 做下一个 Req，一个 Req 一个 PR，
│                                              │  绿灯自合并，遇到门槛开 [需要所有者] Issue
└───────────────┬──────────────────────────────┘
                │
        GitHub：分支 → PR → CI（scope guard + 测试）→ main
```

**核心原则：方向写在文件里，不写在聊天里。** 执行层看不到任何聊天记录；所有者在聊天里说的话，只有被大脑写进 `AMEND.md` / Issue / 指令，才会生效。

---

## 2. 大脑的控制杆（从强到弱）

| 控制杆 | 文件 / 机制 | 谁能改 | 作用 |
|---|---|---|---|
| **AMEND（方向修正）** | `AMEND.md` | 大脑起草 PR，**所有者加 `amend-approved` 标签并合并** | 最高优先级；覆盖 README/STAGES/旧文档。改方向、解冻、改预算都走这里 |
| 阶段与需求编号 | `docs/STAGES.md`（G0–G7）+ AMEND 里新增的 P/F 链路 | 同上（治理文件） | 每个 PR 必须对应一个 Req |
| 防跑偏规则 | `docs/GUARDRAILS.md`、`AGENTS.md`、`CLAUDE.md` | 同上（治理文件） | 7 条硬规则、何时停下、交接协议、合并规则 |
| **CI 强制** | `scripts/scope_guard.py` + `.github/workflows/scope-guard.yml` | 治理文件 | PR 改冻结路径或治理文件且无 `amend-approved` → 红；PR 描述缺 `Stage:`/`Req:` → 红 |
| 当前任务队列 | `docs/handoff/CURRENT.md` | 执行层每次结束更新 | “下一个任务”第 1 项就是执行层要做的事 |
| 历史 | `docs/handoff/LOG.md` | 执行层追加 | 每个 PR 一行：做了什么、花了多少钱 |
| 决策记录 | `docs/DECISIONS.md`（ADR） | 普通 PR | 长期技术决定（如 ADR-010 选定 Omni） |
| **[需要所有者] Issue** | GitHub Issues | 执行层开，所有者回复 | 执行层被门槛挡住时的唯一求助通道 |
| 粘贴指令 | 聊天里的代码块 | 大脑写，所有者转发 | 启动/纠偏/授权的具体一步 |
| 预算门禁 | AMEND-004（≤2 USD/次，≤5 USD/天）+ 脚本里的预检 | AMEND + 代码 | 超额必须开 Issue 等批准 |

**分支规则**：执行层不能直推 `main`；一律 `feat/…`、`docs/…`、`test/…` 分支 → PR。私有免费仓库**分支保护不生效**（GitHub 显示 Not enforced），所以“红灯不合并”靠规则自觉 + 所有者合并前看一眼。

---

## 3. 一次标准循环

1. **所有者**在聊天里提出想法（例：“先打通链路”“我想要毛毡风格”）。
2. **大脑**：
   - 调研（模型现状、价格、开源项目），必要时做小规模真实测试；
   - 把决定写成 `AMEND-00X`（原因 / 决定 / 下一步 Req 顺序 / 预算 / 撤销条件），开 PR；
   - 给所有者一段**粘贴给执行层的指令**（代码块）。
3. **所有者**：给 AMEND PR 加 `amend-approved` → 合并 → 把指令发给执行层。
4. **执行层**：读 AMEND → 更新 CURRENT.md → 按顺序一个 Req 一个 PR → CI 全绿自合并 → 写 LOG →
   遇门槛（超预算、新密钥、治理文件、人工打分）开 `[需要所有者]` Issue，并继续做不受影响的事。
5. **大脑**核对执行层汇报（见第 7 节命令），属实则告诉所有者下一步；不属实或跑偏，给纠偏指令。
6. 真实出片后，所有者把 artifact zip 发给大脑，大脑抽帧 + ffprobe + 看 manifest，给出评估，再进入下一轮 AMEND。

---

## 4. 常用指令模板（给执行层）

**开工（每个新对话第一条）**
```text
仓库：Mrlukahuang/ai-short-drama-factory（main）
按顺序读完：AMEND.md → docs/handoff/CURRENT.md → docs/STAGES.md → docs/GUARDRAILS.md → AGENTS.md。
先只回 3 行：Stage/Req、本次交付物、要改的文件。然后按 CURRENT.md「下一个任务」顺序连续做，
一个 Req 一个 PR，CI 全绿自合并；只在 AMEND-004 列出的情况开 [需要所有者] Issue。
不碰冻结路径、不改治理文件、不开新 UI。结束更新 CURRENT.md 并在 LOG.md 追加一行。
```

**纠偏**
```text
停。你跑偏了。停止当前改动；重读 AMEND.md、CURRENT.md、GUARDRAILS.md 第 5 节。
回答：刚才对应哪个 Stage/Req？违反哪条规则？哪些改动要撤回？撤回后重新给我 Stage/Req/交付物/文件，等我确认。
```

**收工（没有可做的事时）**
```text
当前队列已完成。停止开发：不开新分支/PR，不自己找任务。[需要所有者] Issue 保持原样等我。
我问进度时只读 GitHub 汇报，不改代码。
```

---

## 5. 踩过的坑（新大脑必读）

| 现象 | 原因 | 处理 |
|---|---|---|
| 早期 110 个 PR、存储实验 7k 行、真实视频 0 个 | 没有方向文件，执行层“顺手加固” | AMEND-001 冻结 + scope guard |
| 执行层每个 PR 都停下等审核 | 规则太保守 | AMEND-004 绿灯自合并 |
| 执行层“每小时定时任务”7 小时没干活 | 定时任务被停用（is_enabled=false） | 不依赖定时任务，在对话里连续做 |
| 两个 Agent 同时开发 | 定时任务 + 聊天 Agent 并行 | 同一时间只留一个执行 Agent |
| 执行层说“没有 GitHub 工具/拿不到 Secret” | 该会话工具没接上 | 换会话，或由大脑直接写 PR，所有者手动触发 workflow |
| 大脑下载不了 Actions artifact/日志 | 会话代理禁止访问 blob 存储 | 所有者下载 zip 发到聊天 |
| Omni 只能文字 prompt，不能参考图 | adapter 未实现参考图 | 毛毡风格靠固定文字描述已能保持一致（#132 验证） |
| F3 被 2 USD 上限挡住 | Omni 不能强制时长，最坏 60s ≈ 2.03 USD；上限写死在 `scripts/f3_omni_report.py` | 所有者在 #137 批准后，执行层改该脚本上限 |
| 本地 git 报 “unpushed / no remote branch” | 浅克隆只跟踪 main | 补 fetch refspec + `git branch -u`，属误报 |

---

## 6. 当前状态快照（2026-10-17）

- **方向（AMEND-006 + ADR-010）**：毛毡微缩奥克兰风格（`config/style_presets/felt_diorama.json`）+ `gemini-omni-1.1-flash` 360p，原生音频中文对白。真人路线暂停。
- **已完成**：G0 治理体系；P0–P-final 全 Fake 链路（一条命令梗概 → 60 秒 Fake MP4，`scripts/fake_episode.py`）；#132/#133 真实 3 镜风格测试（全部竖屏、角色一致、中文通过、估算约 0.70 USD）；F1 提示词修正（#135）；F2 Omni 接入 CLI（#136）；F3 六镜 workflow 代码（#138）。
- **卡住**：**Issue #137** — F3 六镜真实运行最坏 2.03 USD > 2 USD 上限。待所有者批准（建议：本次上限 3 USD），执行层改 `scripts/f3_omni_report.py` 后，所有者手动运行 Actions「F3 Felt Omni 6-shot」，输入 `RUN_F3_FELT_OMNI_6`。
- **备选挂起（不阻塞）**：#116 Seedance/Kling 平台与 Key（建议 fal.ai，一个 `FAL_KEY`）；#119 定妆照；#120 九镜 A/B。
- **Active AMEND**：001 冻结存储/TTS 恢复实验；002 原 G1 优先（已被 005/006 覆盖大部分）；003 模型清单；004 自主模式与预算；005 链路优先（真实调用禁令已被 006 在毛毡方向内解除）；006 毛毡 + Omni。
- **已知成本参考**：Omni 360p ≈ 0.034 USD/秒，720p ≈ 0.10 USD/秒；Seedance 2.5（fal）≈ 0.47 USD/秒；Kling 3.0 Standard ≈ 0.22 USD/秒。市场 AI 短剧报价已跌到每分钟几百元人民币。

## 7. 新大脑接手时先做的 5 件事

1. 接入仓库（只读即可；要写 PR 则需 push 权限）。
2. 核对实时状态：
   ```bash
   R=repos/Mrlukahuang/ai-short-drama-factory
   git log --oneline -10 origin/main
   gh api "$R/pulls?state=all&per_page=8" --jq '.[]|"#\(.number) \(.state) m=\(.merged_at!=null) \(.title)"'
   gh api "$R/issues?state=open" --jq '.[]|select(.pull_request==null)|"#\(.number) \(.title)"'
   git show origin/main:docs/handoff/CURRENT.md | head -40
   ```
3. 读 `AMEND.md` 全部 Active 条目 + 本文件第 5 节。
4. 检查执行层有没有跑偏：冻结路径 `git diff --stat <上次核对点> origin/main -- src/drama_factory/storage src/drama_factory/jobs frontend` 应为空；新 PR 都有 Stage/Req；LOG 每个 PR 一行。
5. 问所有者：这段时间调研出的方向/盈利模式有没有变化？有变化 → 写新 AMEND；没变化 → 继续推进 #137 → F3 看片。

## 8. 下一步路线（建议，未写入 AMEND）

1. #137 批准 → F3 真实六镜整集 → 所有者看片打分。
2. F3 通过后：Omni adapter 加参考图支持（提升一致性）；720p 成片对比 360p；接入真实编剧 LLM（STAGES G4 R4.1/R4.2）替换 Fake 剧本。
3. 用实测合格率和每分钟成本回填 `docs/CHARTER.md` 北极星指标，决定量产节奏和盈利模式（国内 vs 出海）。
4. 需要多模型时再开 fal（#116），Kling 4.0 上线后加入对比。
