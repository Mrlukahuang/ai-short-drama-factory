# CityDiscount s02｜原版小羊真实奔跑试拍｜手动启动

Stage: G4  ·  Req: R4.4  ·  仅 s02 一镜，非整片发布

## 已做好的按钮

**[在 GitHub Actions 手动启动一次 s02](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/workflows/citydiscount-s02-omni-reference-once.yml)**

进入 GitHub Actions → 该 workflow → **Run workflow** → Branch **main**：

- `confirmation = PREVIEW_ONLY`：只校验严格 Owner 当前创意 rev4、原版小羊源 PNG SHA、账单申报格式和 3:4 交付策略，不外传任何源图，也不产生收费。
- `confirmation = GENERATE_ONE_S02_PAID_WITH_OWNER_IMAGE`：**一条** Google Omni 真实模型请求。读取仓库已经由 Owner 提供的原版 `character_views/mascot_front_derived.png`，重新按源 SHA 验证，以白色/奶油色不透明背景的 RGB PNG（不重绘眼睛，仅裁透明边/保比例尺寸变换）送给 Google。引用当前 rev4 的第02镜英文提示词（小羊确实跑，始终小巧，眼睛大、脸型不变，所有场景毛毡）。模型目前请求为 **360p 9:16**，真实 MP4 下载后**仅在本地**用 FFmpeg 原比例显示人物并对空余左右区域模糊延伸，输出真实的 **1080×1440 (3:4) H.264**。**不是模型原生1080p/3:4，不可假装细节是原生1080p**。

**人工付费前必须真实确认**：当前新西兰本地自然日、Google 上一条真实 s03 调用（和本地当天其他真实调用）的已发生/待入账用量可核实，填准 `nz_spend_today_usd`；如果未知，不能硬填 `0`。`rights_confirmed` / `google_transfer_confirmed` 源自 Owner 本次明确图片所有权与 Google 传输授权，但仍要在手动表单明确勾选；`google_terms_accepted` 指已独立阅读并接受 Google 相关图像数据处理与保留/服务条款；`invoice_verified` 指账单及已用量真实核对。四个缺一不可，工作流直接拒绝收费。必须有仓库 Actions Secret `GEMINI_API_KEY`（不打印）。

**重要费用边界**：脚本预留最多 `USD 2`、新西兰日 `USD 5` 的**运营申报检验**，Google 供应商 **没有与此脚本绑定的硬账单上限**。真实实际扣费必须在 Google Billing 查到后再认定；`actual_fee_usd=null` 保持 UNKNOWN，绝不填 0。不能保证失败调用不计费，也不自动重试。

## 成功交付与验收

第一次免费 PREVIEW 会上传 `receipt.json`，真实模式成功后同一次 run 的 **Artifacts** 提供：

- `s02_raw_omni_9x16.mp4` — 真正从 Google 下载的源视频，供核对原生态画质/角色动作；
- `s02_owner_1080x1440_3x4_NOT_FINAL.mp4` — 后期不拉伸小羊的1080×1440成片规格技术测试；
- `receipt.json` — 原素材源 SHA、请求指纹、单次模型调用数、媒体 SHA、ffprobe 验证、费用 UNKNOWN、不得发布；
- Google 文件在生成响应存在 URI 时，可按已有 provider 路径保留只含真实 `file_id` 的下载恢复文件；**不会自动重跑第二次收费**。

创意人工验收：在视频播放中，小羊是否真的移动，而非图片横移；眼睛有没有变小；外形是不是 Owner 的吉祥羊；小羊占画面高度通常15–22%（上限27%）；奥克兰地标全部羊毛毡；跑步不变脸。如果有一点不达标，镜头回炉、不得标为最终通过，不自动触发第二次 paid。

s05 的挥铲两次后出金币、s06/s07和 s12 完整 Logo 是**下一任务**，不能因为 s02 工作流全绿就声称已经做完。

## 开发/安全边界

使用仓库现有 `prepare_offline_omni_envelope` + `issue_operator_grant`（本次手动 owner 操作范围 + 单进程临时 HMAC 密钥）+ `GoogleOmniVideoProvider.generate_approved_reference_envelope`。不修改 Provider、冻结路径、生产 DB 或发布后端。Generic CI 用 Fake SDK 验证接口防重入，单独 FFmpeg 检查视频。代码 CI/PR 可不花费 Google 模型费用；正式视频生成一定是 Owner 手动选付费模式。

G4 **NOT_READY**、G5 不启动。所有者对 s02 试片审看通过后再谈 s05。
