# CityDiscount s05 原版小羊挖金币｜真实 Google Omni 360p 试拍

Stage: G4 / Req: R4.4。Owner 2026-10-22 要求 360p 加速真实测试，s02 实片动作/风格可作为试片继续，轻微衔接生硬接受。

**[打开 Shot 05 手动试拍工作流](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/workflows/citydiscount-s05-omni-reference-once.yml)**

打开后选择 branch `main`，点击 **Run workflow**：
- 首次可以选 `PREVIEW_ONLY`、`nz_spend_today_usd=UNKNOWN`，其他选项保持未勾选；此方式只做本地零费用素材 SHA/Owner 分镜+预算输入预检，不触发模型、不外传原图。
- 付费仅当 Owner 独立核查当日 **新西兰自然日 Google 实际用量和待入账费用** 后：`confirmation=GENERATE_ONE_S05_PAID_WITH_OWNER_IMAGE`；`nz_spend_today_usd` 填当天**已核实**的 USD 数字，不能用猜的 0；四项勾选：`rights_confirmed`、`google_transfer_confirmed`（Owner 已明确授予原版 CityDiscount PNG 及Google试拍使用）、`google_terms_accepted`（运营者实际独立审阅并接受Google相关服务/图片保留条款）、`invoice_verified`（费用真实查证）。缺任一项拒绝付费；用既有 GH Action Secret `GEMINI_API_KEY`，不可把密钥贴聊天或日志。
- 本地额度核对 **USD 2/次、USD 5/新西兰自然日**，不是 Google 侧硬性账单止损。仅发 **一条** 请求、失败不重试。Omni真实视频可能另有图像/文本输入费用，实际扣费须单独核对，不能把预估当账单。
- **s05 5 秒单镜头**：小羊在毛毡蔬果摊边 0–1.5s 第一次挥铲，1.5–3.0s 第二次不同挥铲，3s 才有**且仅有一枚**毛毡金币，4s 捡金币。Google请求参考仓库经 SHA 验证的原版 `mascot_front_derived.png`（临时不透明 RGB，不绘制其他眼睛）。统一针毡奥克兰、主角占画高15–22%，不大于27%，不虚构任何已验证实时商家优惠。
- **CD文字准确性**：供应商不允许自由编造 Logo/品牌字样，所以**生成阶段只要求无字金色金币**；已验正宗 CD 图案未来需 **独立确定性后期贴入并做位置跟踪** 才能算正式“CD金币”镜头。绝不把 AI 随机拼出来的假字当 CityDiscount 授权金币。
- 原始 `s05_raw_omni_9x16.mp4`：真实Omni **360p（360×640）9:16**；经已有 FFmpeg 等比显示主体/模糊延伸背景转成 `s05_1080x1440_3x4_NOT_FINAL.mp4` 的技术目标 1080×1440，**并非原生高清画质**；运行产物 Artifacts 附源视频、转制视频、SHA与 ffprobe 回执。没有实际视频就不得称成功。
- 这是一条 **G4 真实视频试拍**，不代表已经达到 s05 动作与人物一致性创意验收，不是60秒完整影片；G5保持暂停；付费模式要 Owner 在 Google账单核实并点击后才跑。
