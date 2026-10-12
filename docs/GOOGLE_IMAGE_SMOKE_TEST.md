# Google 图片单张实测：手动触发、可能计费（PR-09）

目标：用 `gemini-nano-banana-2.1` 生成**一张全新虚构成年人演员**的 9:16 定妆照，确认模型账号和 SDK 实际可以访问，并保存一份短期私有 Artifact 供人工审片。

## 提前准备（仓库所有者亲自完成）

1. 在 [Google AI Studio](https://aistudio.google.com/apikey) 创建有权访问图片生成模型的 API key，按 Google 官方要求开通计费。不要把 API key 贴进 ChatGPT、Issue、PR、Commit 或日志。
2. 打开本私有 GitHub 仓库的 [Actions Secrets](https://github.com/Mrlukahuang/ai-short-drama-factory/settings/secrets/actions)，点击 **New repository secret**，名称为 `GEMINI_API_KEY`，值为完整密钥，保存。
3. 打开 [Actions](https://github.com/Mrlukahuang/ai-short-drama-factory/actions)，选择左侧 **Google single-image smoke (manual, may incur cost)**。
4. 点击 **Run workflow**，选 `main`，确认输入框填写 `GENERATE_ONE_PAID_IMAGE`；再次确认会产生真实 Google API 费用后手动执行。
5. 成功后从该 run 的 Artifacts 下载 `fictional-actor-single-image`，打开 JPG，检查清晰度、面容与风格。图片仅保留 3 天。

## 行为与成本

- 工作流只支持 `workflow_dispatch`，不会响应普通 push 或 pull_request 自动运行。
- 输入确认词不匹配时，job 不会运行；缺少 Secret 时在付费请求前失败。
- 仅创建一套**临时、虚构**的演员数据库记录；使用确定的短 Prompt，调用单张模型请求。
- 成功后只存储 `smoke_fictional_actor.jpg` 为 GitHub 私有短期 artifact，不提交到 Git、不写入生产素材库。
- **没有自动重试或批量调用；一次 workflow run 只调用一次模型 API**。如失败，重新手动执行可能再次产生费用。
- 测试代码中的 `maximum_acknowledged_spend_usd=1.00` 是人工确认额度提示，**不是 Google 的强制计费上限**。Google 账单/模型许可/区域可用性以账号实时信息为准。
- 此处是文生图冒烟测试，**不是**人物跨镜头一致性试验，亦未验证双人对话、视频或商用出片。
- 模型供应商有可能变更 SDK 响应形状；首次运行失败也可能是权限、账单、SDK 或响应格式原因，届时按真实日志修复，不猜测成功。

## 纯离线本机检查

```bash
python -m pip install -e '.[google-image,test]'
python -m drama_factory.providers.image_smoke
pytest -q
```

离线模式返回 `image_created=false`，不会读取或使用 Google API 密钥。

## 首次试片失败的排障记录

2026-10-12 运行 #38220651557：密钥已传入、依赖已安装，Google 对旧版 `image/png` 请求直接返回 400，未生成图片。修复 PR 统一切换官方支持的 `image/jpeg` 与 `.jpg` Artifact，并采用 Pillow 解码校验；不能仅凭 HTTP 400 断言 Google 账单绝对为零，实际以 AI Studio 计费记录为准。
