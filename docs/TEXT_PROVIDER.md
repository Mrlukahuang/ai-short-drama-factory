# PR-02：结构化 TextProvider 与 Fake 编剧接口

## 功能和边界

本模块用于验证编剧管线的结构化契约，不会真正调用 Claude/Gemini，也不创作实质剧情，更不会把小说送到第三方 API。

- Provider Protocol：`TextProvider.generate(ScriptPlanRequest, ScriptContext) -> ScriptOutline`
- FakeTextProvider：确定性模拟大纲；`is_mock=true`、`ready_for_approval=false`、`status=mock_only`。
- 固定 Prompt 版本：`episode-outline.zh.v1`；未知版本直接 422，不偷偷使用最新版本。
- 剧集级隔离：草稿绑定 `series_id`、不可变 `story_bible_id`、演员/场景资产 ID；跨剧引用 422。
- 指纹：SHA-256 涵盖请求和 Story Bible 快照；与后续媒体生成缓存的职责不同。
- 持久化：`script_drafts` 新表只保存研究草稿；**不会自动创建 Episode / Production 或解锁人工审核门禁**。
- 本版本不接入云模型；任何联网/付费 Provider 都必须单独 PR，明确凭据、预算与版权门禁。

## API

`POST /api/v1/series/{series_id}/script-drafts` 接收：

```json
{
  "story_bible_id": "bible_xxx",
  "episode_number": 1,
  "target_duration_seconds": 60,
  "creative_brief": "雨夜重逢，悬念收尾",
  "actor_asset_ids": ["asset_女主ID"],
  "scene_asset_id": "asset_场景ID",
  "prompt_version": "episode-outline.zh.v1"
}
```

`GET /api/v1/series/{series_id}/script-drafts` 列表；`GET /api/v1/series/{series_id}/script-drafts/{draft_id}` 详情。ID 指代示意，实际通过资产 API 获得。

## 兼容与迁移

旧项目、分集、小说表结构完全不变；Database 初始化幂等增加 `script_drafts`。
不触发任何已有项目数据迁移、支付、模型调用或远端发布。
后续 PR-03 需要增加可信的 `episode-outline → script → ShotDraft` 转换器，并为真实模型的结构化输出增加人工审核态。
