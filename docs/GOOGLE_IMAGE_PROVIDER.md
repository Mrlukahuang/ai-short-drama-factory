# PR-08a Google Nano Banana 2.1 图像 Provider（受控、默认关闭）

模型 ID `gemini-nano-banana-2.1`，来自 Google 官方的 [图片生成](https://ai.google.dev/gemini-api/docs/image-generation) 和 [模型说明](https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1)。
接口：`client.interactions.create(model=..., input=..., response_format={"type":"image","mime_type":"image/jpeg","aspect_ratio":"9:16","image_size":"1K"})`。

`FakeGoogleImageProvider`：不生成像素、不联网、不扣费，返回 is_mock=true。
`GoogleImageProvider`：真实实现，但**不会由当前 FastAPI 路由自动调用**；需满足：

1. `DRAMA_ENABLE_PAID_GENERATION=YES` 明确启用；
2. 单次请求 `operator_approved=true`；
3. 本机环境 `GEMINI_API_KEY`，且安装可选 `google-image` 依赖；
4. 演员资产必须归属当前 Series；
5. 当前仅支持从文字生成新演员参考图（无上传参考图片字节，不能冒充跨集已绑定参考的图生图）。

输出 JPEG 字节只返回给调用者；没有自动持久保存到资产库或远端存储，必须后续增加审核后持久化与对象存储。

**成本重要说明**：`maximum_acknowledged_spend_usd` 是人为确认参考金额，**不是** Google API 的实际硬性账单封顶。当前没有外部账单回执或模型级预算服务，本阶段不可做无人值守批量生成。为此**生产 API 并未暴露真实生成端点**；只有开发者明确手动调用才可能计费。

当前 CI 只用注入假 SDK 返回验证请求参数、门禁和响应解析，没有产生真实图片，也没有测试真人一致性。Google 真实 API 首次验证需要用户在自己的 Google AI Studio 账号创建密钥/开通计费；不应在聊天或 GitHub 提交密钥。


## PR-09 手动单张试片入口

Github Actions 只在人工 workflow_dispatch + 特定确认词 + 仓库私有 `GEMINI_API_KEY` 共同满足时运行。参见 [GOOGLE_IMAGE_SMOKE_TEST.md](GOOGLE_IMAGE_SMOKE_TEST.md)。上传单张生成图为 3 天 Artifact；不会在 PR/CI 自动生成，也不会把生成的文件永久纳入仓库。

## 2026-10-12 真实 API 失败记录及修复

手动运行 [#38220651557](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38220651557) 通过依赖安装和 GEMINI_API_KEY 存在性检查，但 Google Interactions API 返回 HTTP 400：`response_format.mime_type=image/png` 不支持；只支持 `image/jpeg`。已经同步改为 JPEG，并同步修改 Pillow 解码校验、产物扩展名 `.jpg`、单元测试与 Artifact 路径。参阅官方 [Interactions API 图片输出 MIME 枚举](https://ai.google.dev/api/interactions-api-v1)。

修复 CI 不会自动调用付费模型；用户必须明确手动开启下一次试片。
