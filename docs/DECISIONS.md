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
