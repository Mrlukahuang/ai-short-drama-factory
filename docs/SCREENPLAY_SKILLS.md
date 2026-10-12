# PR-03 剧本 → 分集契约及 Drama Skills 初步审查

## 人工审核剧本的结构

- `Screenplay` 定义每集标题、Story Bible 版本、分集数、起始钩子、结尾悬念和逐镜头计划。
- `ScreenplayShot` 保存起始/结束连续性、景别、摄像机、演员和场景 ID；`DialogueCue` 显式绑定说话人的 actor_asset_id。
- Validation：时长严格相加、镜头 ID 唯一、对白说话人必须是该镜头的演员、场景/演员/Bible 必须属于该剧。
- 人工明确确认后才能通过 `/commit` 生成 **Episode 草稿**；不会自动批准剧本、也不会创建 Production 或付费生成。
- 对 `EpisodeDraft` 的转换保留角色说话人前缀；正式配音之前需将 DialogueCue 作为一等数据保留。

## 接口

- `POST /api/v1/series/{series_id}/screenplays/validate`：无副作用，展示规范化 Episode 草稿。
- `POST /api/v1/series/{series_id}/screenplays/commit`：对象 `{"screenplay":{...},"reviewed_by_operator":true}`，保存为 draft；同一集数重复保存返回 409。

## Drama Skills 审计结果（2026-10-12）

源仓库：[zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills)，审阅版本 `c2426e03c0e7722bebcc6a488b6658dc38c65ac3`。
公开 LICENSE 为 **MIT**；仓库说明含 11 个用于 Agent CLI 的创作 Skill，不是官方 SDK，也不是可直接调用的 FastAPI 模块。

值得吸收的理念：

1. 创作文件分层：剧本、视觉设定、分镜、图片提示词、视频提示词、剪辑单。
2. 角色服装及场景的 continuity lock 与镜头引用覆盖检查。
3. 确认生产清单与付费前的批准门禁。
4. 小说改编的来源引用、章节地图与故事节奏。

**明确不做**：本 PR 没有下载或执行第三方 shell、npx 安装器、Provider、FFmpeg 脚本、云端密钥，也没有复制对方的核心内容。未来若直接复用其 MIT 文件须保留原许可证与版权声明，并单独审计外部脚本、依赖和写盘权限。当前 Schema 与校验器是本仓库的独立实现。

## 后续

PR-04 / PR-05 完成小说情节实体/溯源；未来真实 LLM 负责输出本 Schema，再经相同的独立验证、编辑、审核流程。中文版实时字幕、音色绑定、精确音频驱动在后续音频 PR 处理。
