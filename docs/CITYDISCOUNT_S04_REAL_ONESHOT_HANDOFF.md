# G4 / R4.4 — s04 真 Omni 单镜生成入口（默认零付费，不自动提交）

**2026-10-23 NZDT。** 紧接 #248 / main `702f6a921dcbf17e6d81d845cb1f72d789c1863b`。用户追问“到底做到哪里了、能不能生成”。事实：原真实模型小羊 s02/s05 已完成；s03 是真旧奥克兰毛毡环境片，没有真实羊；s04 还没有独立真角色动态。现有 60s A/B/金币片均属技术审核，缺九镜小羊表演；此前仓库没有 s04 可手动启动的 real image-reference Action。

本 PR **只新增一个实际可运行的最小单镜入口，利用成功付费生成过 s05 的既有 provider**，不再建立新适配器、不修改曾成功生成的 s02/s05，也不自动触发真实模型请求。

- 脚本 `scripts/citydiscount_s04_omni_reference_once.py`：调用已有 `GoogleOmniVideoProvider.generate_approved_reference_envelope`（即 s02/s05 成功路线），来源为当前 `_canonical_png()` 校验过的 Owner **正面**小羊 PNG。只提交 **一张原版正面图 + 文字提示**；没有传送 s03 原视频或额外四视角素材，不伪称通过跨镜真实环境视频延续。真实生成目标是 **5.0秒、模型原生360×640 9:16、后期无拉伸适配1080×1440 3:4**，生成原始 MP4/修正版MP4/receipt，标明视频实际源360p不是原生1080p。
- s04 创意约束：12镜剧情索引 `s04`，`storybeat=supermarket_arrival`，城市小羊由远处街道自然跑进全毛毡微缩超市蔬果摊，最后在小土堆旁举铲**准备** s05挖掘；这镜不挖、不出金币。原小羊五官/绿色配件/小铲保持一致，小羊高度首选15–22%，最大27%；连续镜头、真实毛毡纤维/景深和相对建筑视差、无真实商家/商品价格/自创商标和字样。
- GitHub Actions `.github/workflows/citydiscount-s04-omni-reference-once.yml`：只有 `workflow_dispatch`，需用户人工启动。默认 `PREVIEW_ONLY`/未知账单支持零付费检查；付费必须手动选择 `GENERATE_ONE_S04_PAID_WITH_OWNER_IMAGE`，准确填独立核实的当日已用USD、确认独立素材版权及本次向Google转交、Google保留/使用条款、账单核验及GitHub已有 `GEMINI_API_KEY`。代码与Action默认支付关闭，批准模式最多一次真实SDK调用、禁止自动重试、隔离旧产物，单次Owner运营预留 USD2 / 新西兰日上限 USD5；**预留字段不是Google服务端美元硬封顶**，到账发票仍待事后核对。工作流不会自动提供扣费保证。
- `tests/test_citydiscount_s04_omni_reference_once.py`：预检不调用模型；低预算/UNKNOWN的付费拒绝；4个独立人审布尔值分别拒绝；Fake SDK模拟一次调用且拒绝覆盖；确认素材SHA及prompt时空身份锁；对输出原文件、后期尺寸、禁止发布等字段做契约断言。**CI绝对不触发付费请求。**
- 治理事实：[#188](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/188)、[#210](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/210) 当前仍OPEN。用户曾批准“单次USD2／新西兰日USD5”受控实验以及原素材用于旧特定 run，但**不能从历史回执推定新s04素材外传及新Google条款已单独核准**，也没有当前NZ日Google实缴消费数据。本PR的 `model_submission_allowed`/ `real_media_generated` 都不能提前宣称通过。该GitHub连接器目前可维护工作流、核验Jobs，但没有 `workflow_dispatch` 动作，不能假装已替Owner点击执行。需Owner在GitHub Workflow手动触发付费流程，并对每项确认负责。

**技工目标不是已完成广告：**真实 s04 一次成功也只会从2/11增加到3/11个小羊动态镜头；与已完成 s03 真实城市及 s05 实拍前后地理连续性必须另外逐帧验收；九镜剩余会减为八镜。暂无新增外部模型调用或Google花费，完整内容仍 G4 NOT_READY / G5冻结 / 非发布用。

**可用入口（在PR全CI绿并合并进main后）**：
https://github.com/Mrlukahuang/ai-short-drama-factory/actions/workflows/citydiscount-s04-omni-reference-once.yml

这里的 Workflow 链接只是操作入口，**不是已生成的视频**。如果无法核实当日账单、图片权利或Google条款，运行 `PREVIEW_ONLY`，不要勾选或虚填四个确认项。
