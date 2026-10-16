# Architecture Decision Record (ADR)

这些是当前明确决策。具体模型可以重新测试/替换，接口契约不随单家厂商变化。

## ADR-001 真人短剧优先（2026-10-12）

**状态：Accepted**。最困难的连续真人双角色交互决定系统数据结构。2D 漫剧 / 3D 动画共用叙事、音轨、队列和审查模块，仅视觉 Provider 与资产约束不同。

## ADR-002 Python 状态机为唯一总控

**状态：Accepted**。Agent/Skills 负责内容生成策略，但不允许自由绕开预算、审核与版权门禁。FastAPI 控制接口；先用 SQLite；未来迁至 Turso。FFmpeg/Remotion 负责确定性成片。

## ADR-003 原创和小说改编为两个独立创作入口

**状态：Accepted**。小说上传、版权、章节溯源、事件图、改编计划是一套独立子域；批准后转成同一 Story Bible / Episode / Shot Schema。禁止机械按章均分集数。

## ADR-004 Google 优先评估，Provider 可替换

**状态：Accepted for evaluation, not an exclusive production commitment**。首先测试 `gemini-omni-1.1-flash`、`gemini-nano-banana-2.1`、Gemini TTS；Seedance/Kling 作为视频竞争者。模型 ID、价格、弃用时间均需周期核查，不可把 ChatGPT/Claude 订阅当作免费后端 API。

## ADR-005 审核门禁与幂等

**状态：Accepted**。所有原始输入和输出版本化；先审核剧本和角色，再触发昂贵的视频生成。镜头级幂等及任务恢复是上线硬性条件，不得在整集失败后盲目重建所有镜头。

## ADR-006 私有独立仓库

**状态：Accepted**。建议名称 `Mrlukahuang/ai-short-drama-factory`，设为 `Private`。不混入既有内容分析或 Godot 仓库。暂未决定未来公开发行许可；代码可在私有仓库独立研发。

## ADR-007 本地小说文件与权益

**状态：Accepted**。先解析本地文本、存储章节和 SHA-256；上传 ≠ 具备改编权。生产部署中必须人工核实地域、期限、媒介、AI 处理/外包授权、电子书格式和发布权。未经许可/审核，不发送给外部模型。

## ADR-008 栏目 / 剧集 / 资产隔离（2026-10-12）

**状态：Accepted**。`Column → Series → Episode → Production` 为正式生产层级。现有 projects 表在迁移期表示 Series，旧 API 保持兼容。角色、场景、声音和道具归属 Series；默认不可跨剧引用，即使同名亦不共享。Story Bible 和资产版本只追加不覆盖。视频真实多队列并发留在 M3，用户权限隔离留在 M5。详见 [MULTI_COLUMN](MULTI_COLUMN.md)。
## ADR-009 冻结基础设施实验，先验证真实视频（2026-10-15）

**状态：Accepted**。见 `AMEND.md` AMEND-001/002。生产继续使用 SQLite 至 G5；Turso/libSQL txlab、TTS 恢复链冻结（只修 bug）。新增原则「先验证、后加固」：环节未用真实模型跑通前，不写恢复/对账/迁移代码。阶段计划改由 `docs/STAGES.md` 管理，`docs/ROADMAP.md` 转为历史记录。冻结由 `scripts/scope_guard.py` 在 CI 强制。

## ADR-010 主视频模型与音频路线（2026-10-16）

**状态：Accepted**（AMEND-006）。主视频模型 `gemini-omni-1.1-flash`，360p 草稿 / 720p 成片；音频路线 A：模型原生音频 + 中文对白。视觉风格：毛毡微缩（`config/style_presets/felt_diorama.json`）。依据：Issue #132 / PR #133 真实 3 镜头测试，竖屏、风格、角色一致性、中文对白均通过，估算约 0.70 USD。Seedance / Kling 保留为备选 Provider。
