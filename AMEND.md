# AMEND.md — 方向修正记录（任何 Agent 开工前第一个必读文件）

> **规则：本文件优先级最高。** 与 README / ROADMAP / 旧 PR 文档冲突时，以本文件最新一条 `Active` 修正为准。
> 只有仓库所有者（Mrlukahuang）可以新增或撤销修正；Agent 只能**提议**（在 PR 描述里写 `Proposed AMEND`），不能自行写入 Active 条目。

阅读顺序：`AMEND.md` → `docs/CHARTER.md` → `docs/STAGES.md` → `docs/GUARDRAILS.md` → `docs/handoff/CURRENT.md` → 再看具体代码。

---

## AMEND-001（2026-10-15，Active）冻结基础设施实验

**原因**：约 110 个 PR 里，storage 模块（Turso/libSQL txlab v2–v5、fencing、迁移演练）7,357 行，是最大模块；Provider 只有 1,200 行。真实 AI 视频镜头数为 **0**。项目在没验证“模型能否稳定产出中文双主角同脸同声镜头”之前，就在做云数据库事务实验，方向偏了。

**决定**：
1. **冻结**以下路径，禁止新增功能、新增实验版本、新增 workflow：
   - `src/drama_factory/storage/txlab_*`、`pr31_*`、`libsql_*`、`turso_*`、`cutover_*`、`migration_readiness.py`、`snapshot_rehearsal.py`
   - `src/drama_factory/jobs/tts_*`（TTS 恢复/对账链；只允许修 bug）
   - `.github/workflows/*txlab*`、`*turso*`、`*drive*`、`*cloud-canary*`
   - `docs/PR31_*`、`docs/TURSO_*`
2. 生产数据库**继续用 SQLite**，直到 G5（见 `docs/STAGES.md`）。
3. 现有代码**不删除**、测试继续跑；冻结区只允许：修复导致 CI 失败的 bug、删除（需所有者批准）。

## AMEND-002（2026-10-15，Active）先做真实视频盲测，再定架构

**决定**：下一阶段只做 **G1 真实视频 A/B 盲测**（见 `docs/STAGES.md`）。在 G1 出结论（ADR-010）之前：
- 不新增任何 UI 页面（Streamlit 冻结在 PR-07b8；不再做本地占位动画、参考图动效等“替代真实视频”的功能）。
- 不新增小说改编功能（PR-05b/06b 推迟到 G6）。
- 不新增 TTS 链路功能（是否需要单独 TTS 取决于 G1 结果）。

## AMEND-003（2026-10-15，Active）模型清单以 2026-10 核查为准

Sora 2 API 已于 2026-09-24 关停，不得列为候选。视频候选为 Gemini Omni 1.1 Flash、Seedance 2.5、Kling 3.0 Omni（Kling 4.0 上线后加入）。详见 `docs/MODEL_LANDSCAPE.md`。

## AMEND-004（2026-10-15，Active）自主连续开发模式

**原因**：所有者不希望每个 PR 都停下来等审核。

**决定**：Agent 按 `docs/STAGES.md` 当前阶段的需求顺序**连续开发**，不必等待所有者：
1. 每个 Req 仍然单独开分支、单独 PR（规则不变）。
2. PR 的**全部检查为绿**（含 `scope`、`test`）且模板已填写 → Agent **可以自己合并**，然后更新 `docs/handoff/CURRENT.md` 并直接开始下一个 Req。
3. 付费调用：**单次运行最高费用 ≤ 2 USD 可以自行执行**；当天累计 ≤ 5 USD。执行后在 `docs/handoff/LOG.md` 记录模型、次数、实际费用、Actions run 链接。

**必须停下来叫所有者的情况（只有这些）**：
- 单次付费运行可能超过 2 USD，或当天累计将超过 5 USD
- 需要授权：新的 API Key / Secret、账号权限、接受服务条款、OAuth
- 需要修改冻结路径（AMEND-001）或治理文件（`AMEND.md`、`docs/GUARDRAILS.md`、`docs/STAGES.md`、`AGENTS.md`、`CLAUDE.md`、`scripts/scope_guard.py`、`.github/workflows/scope-guard.yml`）
- 阶段退出决策：需要所有者人工评分、签字的事项（如 G1 的 R1.7 盲测打分、R1.8 / ADR-010）
- 同一个检查连续修 2 次仍是红的
- 删除文件、修改已有数据库表结构

**怎么叫**：在仓库新建一个 Issue，标题以 `[需要所有者]` 开头，写清楚要决定什么、选项、预计费用；然后**跳过这个阻塞项，继续做不依赖它的下一个 Req**；没有可做的就停下。

**撤销条件**：所有者在此处标记 Revoked，或连续发现 2 次跑偏。

---

## 修正模板（所有者新增时复制）

```
## AMEND-00X（YYYY-MM-DD，Active）标题
**原因**：
**决定**：
**影响的文件/阶段**：
**撤销条件**：
```

已撤销的条目改为 `Revoked YYYY-MM-DD`，保留原文，不删除。
