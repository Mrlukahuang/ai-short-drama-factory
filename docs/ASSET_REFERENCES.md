# PR-07a 永久演员与场景媒体参考资产注册

现有 `series_assets` 保留每个剧集独立的 actor/scene/voice/prop 设定与版本。
本阶段新增 `asset_references` 元数据表：每一条图片或声样参考都具有严格 `series_id`、`asset_id`、独立版本、内容 SHA256、来源、权利凭据、同意记录和审批状态。

支持：face_reference、wardrobe_reference、scene_reference、style_frame、voice_sample、prop_reference。
调用 `POST /api/v1/series/{series_id}/assets/{asset_id}/references` 登记待批准的对象存储 Key；`GET` 查询版本；`POST /{reference_id}/approve` 人工批准。错误类型或跨剧 ID 会被阻止。

本阶段**不接受原始图片、语音文件上传，也不读取 storage_key 或提供公共下载**。Key 仅是未来对象存储的不可执行逻辑标识；上传字节和签名 URL 另由后续受控存储 PR 实现。所有在线模型仍保持关闭。

- 用户需声明合成图使用的模型与商用条款来源，或拥有真实人物的相关授权/同意。
- 有真人面容/声音的 `licensed_person` 必须有 consent_reference。
- 图片与声样必须先 `pending_review`，再经明确审查标记为 `approved`。
- 正式生产前必须增加操作者身份认证、不可篡改的审核日志、存储安全扫描和证据校验。

本 PR 可直接供后续 Nano Banana / Gemini Omni Provider 引用精确的已批准资产版本，但还没有真正生成任何角色图片或 MP4。
