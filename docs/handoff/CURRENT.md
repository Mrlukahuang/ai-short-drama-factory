# 2026-10-21 G4 / R4.4：官方 Gemini Omni 参考图实时入口最小接线（本 PR）

官方文档（2026-10-21 查阅）明确 `gemini-omni-1.1-flash` 的 Interactions API 支持 `input=[{"type":"image","data":"base64","mime_type":"image/png"},...,{"type":"text","text":"..."}]`，并支持竖屏9:16/360p。文档：https://ai.google.dev/gemini-api/docs/omni；资费：https://ai.google.dev/gemini-api/docs/pricing。现有 `google_omni_video.py` prompt-only 是真实的功能缺口，不能再声称当前 Omni 官方不支持图片。

**Stage G4 / Req R4.4**：不写新 Provider；只在现有 GoogleOmniVideoProvider 新增 `generate_approved_reference_envelope`，直接使用已存在 `prepare_offline_omni_envelope` 校验出来的 FND 图片+文字 payload，调用原有**单次** Interactions.create/URI下载/ffprobe 链；旧 raw VideoRequest.reference_images **继续拒绝**，防未经 FND 的任意路径输入。新入口强制手动提供单镜头精确 fingerprint/shot ID 匹配、独立权利/外传/供应商数据条款三个布尔批准、declared NZ day 已支出及 run 预算 ≤USD2/日≤USD5、原有 `DRAMA_ENABLE_PAID_GENERATION=YES` 环境关闭默认值；请求图片 bytes SHA/顺序和 prompt/格式 fingerprint 复核，不把 image/base64 带入 receipt/日志。单请求不重试，`actual_fee_usd` 仍为 null：费用确认值并非供应商硬计费 cap。

CI 使用 **真实 FND-02 operator HMAC 签署及本地 PNG 字节夹具 + Fake SDK 返回实际本地 FFmpeg MP4**，模拟成功与越权/改图/改序/改prompt/超预算失败，**没有真实 Google 网络调用**。不能把本地合成视频报告成新的小羊片段；也没有绕过 Owner #188/#210 的真实素材许可或本地真实账号账单检查。下一实际步骤：整理品牌/小羊/家庭/金币的合法使用权与官方账号保留条款，核验当天实际账单后执行最小一个真实镜头；任何不满足则禁止提交。G4 NOT_READY/G5 暂停。必须以 PR 本轮 CI/合并回执判定交付，不提前宣称成功。

---

# 2026-10-21 G4 / R4.4：正式 Owner 城市寻宝 CityDiscount 首片（创意修订 3）

**本轮正式创意来自 Owner 原文**：`《把奥克兰的好折扣，挖到你身边》`，60 秒/12×5 秒。原《小羊差点买错了》创意修订 2 已**在原有权威文件** `config/pilots/citydiscount_first_promo_v1.json` 中被替换（Git 保留历史）；新稿按 s01 钱包→s02 吉祥物接任务→s03 奥克兰立体地图→s04–s07 四个优惠寻宝站（买菜/美食/购物/出游）→s08 分类核对→s09 折扣地图送到家→s10 家庭出行→s11 CD 金币余钱→s12 完整品牌收尾。全部 Owner 原始画面要求（`owner_visual_direction_zh`）、逐镜中文旁白、音效、音乐提示、机位、连续性均已入原 JSON；可读执行单 `docs/CITYDISCOUNT_FIRST_FILM_STORY.md`。

现有 `promo_motion_graphics.build_offline_citydiscount_promo_plan` 在同一 schema 中承接家庭/吉祥物镜头可见范围、Logo s02 胸前/s08 折扣册/s12 片尾 3 秒、s01/s11/s12 CD 金币正面、片尾四行精准文案，**没有新宣传片引擎**。保留 offlining 安全标记：仅示意优惠卡、无虚构商家/价格、`model_submission_allowed=false`、`script_reviewed_by_owner=false`（仅表示最终制作版本未单独验收）、`publish_approved=false`。**该 PR 是制作稿的代码交付，不是 60 秒真实 MP4**。实际素材仍待小羊版权独立核验、家庭角色版本、CD 金币独立标准图案、真实参考图模型 API/账号与价格、最终发布账号；#188/#210 保持开放。单次上限 USD2/NZ 日上限 USD5，本次模型调用 USD0。**G4 NOT_READY / G5 暂停。** PR/CI merge 是否完成以 GitHub 本轮回执为准。

---

# 2026-10-21 G4 / R4.4：CityDiscount 60 秒真实故事线与 12 镜制作稿（本 PR）

**当前 G4 NOT_READY / G5 禁止。** 首片创意不再仅为 12 张营销说明卡：已改写 `config/pilots/citydiscount_first_promo_v1.json` 的**第二次创意修订**，主人公为 Owner 已反馈满意的奶油白深绿围巾小羊。60s 12×5s 原接口仍在，新增故事弧：0–15s 冲动发现 → 15–20s 卡片翻面/条件反转 → 20–45s 核对日期/门槛/限制/来源 → 45–60s 清醒选择和品牌结尾。每镜补齐摄影视角（来自已入库四角度源角色）、动作提示、拍摄指导、连续性、短旁白和 FFmpeg 后期字幕，真实优惠/日期/商家价格一律不编造。

**实际可读制作单**：`docs/CITYDISCOUNT_FIRST_FILM_STORY.md`；权威内容还是既有 JSON，`promo_motion_graphics.py` 现在带出完整剧情弧、镜头指引到原离线计划，不写新的渲染管线。最小 CI 测试证明故事转折、4 摄影视角/10 PNG 角色、无媒体审批、改稿 invalidates source SHA。真实视频/旁白仍没有新生成。

**下一步**：交 Owner 审批故事；优先小成本试 `s04` 翻卡镜头的真实效果，必须独立核对外部多图 API/价钱/素材权利/治理冲突（#188、#210）。Owner 已给总预算单次 ≤ USD 2、新西兰自然日累计 ≤ USD 5，但这不是实际运行回执，不是个人素材可外传的法律证明。CI/PR 未全绿前不得合并；本轮 0 新 paid calls，0 USD。

---

# 2026-10-21 G4 / R4.4：已审 W2 版本 → 实际 SQLite SeriesAsset → 图片候选记录（PR #213）

本轮在现有 `local_reference_views.build_unapproved_shot_image_review` 增加可选 **read-only SQLite** 校验，先确认选定 Series 的每个 actor 和 scene 的真实数据库 `id/kind/version/specification_json SHA256` 与 W2 已锁定版本完全一致，再读取对应本地 PNG 字节。旧的不带 DB 测试路径保持兼容，但回执明确记为 `series_asset_sqlite_pins_verified=false`，不能再把测试清单冒充真实数据库版本。

使用已有 `build_bound_screenplay_video_plan` 创建真正 SQLite W2 manifest，并读取本地合成 PNG 的双演员 6 镜正/负例；伪版本、变更资产规格、串资产类别、外部数据库、图片先读等均阻断。**生产环境真实 Series 数据库仍需运营方指定并人工核查；这不是证明 Owner 实际生产 SQLite 已经登记小羊。** 无 DB 写入、新迁移、外部请求、权限自动升级或真实视频生成。需以 CI 和合并回执验证结果。#210 四视角/权利审批未完成，G4 NOT_READY / G5 禁止。

---

# 2026-10-21 增量：EpisodeDraft.reference_asset_ids → 版本化 FND 视觉计划 → Fake Provider 凭据

**Stage: G4 / Req: R4.4 / G4 NOT_READY。** 在现有 `screenplay_visual_bridge.py` 引入可选、严格的 `EpisodeDraft` 引用列表校验：每镜引用必须按已审 Screenplay 的在镜演员 + W2 绑定场景 + 锁定道具精确排序；不得删、加、调序，不得改变原镜对白/动作，也不得给不在选择范围的镜头附加引用。原有兼容路径保持不变。

成功校验时把 `episode_draft_sha256` 纳入现有 FND-01 视觉计划哈希，进而进入 FND-02 HMAC grant scope 和无媒体字节的 Fake Omni receipt。预期覆盖两独立 Series 的完整 12 镜、6 镜合成 PNG 安全演练；CI 和最终合并情况以实际 PR 为准。无需新 Worker/DB/Provider，不得把测试密钥当所有者授权；真小羊 #210 权利/视角仍待人工决策，不提交 Omni、不付费。

---

# 2026-10-21 下一项真实增量：PNG 源文件 → W2 逐镜人审候选图（本 PR）

**Stage: G4 / Req: R4.4 / G4 NOT_READY。** 在现有 `local_reference_views.py` 补充 `build_unapproved_shot_image_review`：真正读取 repo checked-out 原始 RGBA PNG 字节并对来源 SHA 做复核，调用已经存在的 RGB 白底规范化逻辑，产生规范化 `png_sha256` 与 W2 角色 `asset_id/version/specification_sha256`、镜头 ID、scene version 的确定性待审批映射。真实小羊四视角经过同一通用逻辑按 12 镜选择；另一无关双演员 6 镜使用合成文件验证不含品牌硬编码。**这不是人工视角审核**。

所有返回值始终保留 `angle_semantics_human_verified=false`、`rights_independently_verified=false`、`operator_approved_for_model=false`、`model_submission_allowed=false`；scene image 仍明确阻断，动作表情图片不冒充 front/side/back。CI 结果及合并情况以 PR 页面为准。不新增 DB、不发外部媒体、不改变真实模型 Provider；Owner 决策仍在 [#210](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/210)。下一步：审查候选视角与权利后才可能接正式授权图库及受控真实视频实验，不为无授权图库伪造 grant。

---

# 2026-10-21 续开发：Reviewed Screenplay → W2 → FND-01/02/03 → Fake Omni 双 Series 安全演练（PR #209）

**Stage: G4 / Req: R4.4 / G4 NOT_READY，G5 禁止。** [PR #209](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/209) 在现有 `visual_spine_offline.fake_episode_visual_replay` 增加可选的**已审 Screenplay 全量镜头绑定校验**：先调用现有 Screenplay→W2→FND-01 bridge，强制镜头顺序一致并比对视觉计划 SHA，才允许读取媒体构造临时本地 envelope。旧离线调用保持兼容；不用另写视觉系统。

**验证范围：** 新测试 `tests/test_g4_reviewed_screenplay_fake_media.py` 以两个**不同 Series ID** 的 12 镜单演员故事与 6 镜双演员故事走同一现有 FND-01/02/03、签名 Fake grant、实际合成 RGB PNG 字节门禁和 `FakeOmniReferenceProvider`；断言跨片 grant、错配角色、漏镜、依赖重接、PNG 字节篡改 fail closed，模拟首尾帧继承和零网络。CI 结果及最终 merge 状态必须以 PR 页面实证为准，不能由测试文件存在就宣称跑绿。

**权限边界：** 此处 only *synthetic testing*, 测试 HMAC 不是 Owner 真实审批。已经上传的十张真实小羊仍没有人工视角语义确认、独立权利核实或模型外传授权；`rights_independently_verified=false`、`operator_approved_for_model=false`、`model_submission_allowed=false`。无真实 Omni API、无收费、无可发布新视频。#201 继续 Open；下一个真正阻断是可信操作员视觉/版权审批与真实图片系列版本绑定，绝不伪造认可。

---

# 2026-10-21 最新：Owner 十张真实小羊多视角/动作 PNG 已入 main，来源 SHA 与 FND-02 离线字节验收全绿

**Stage: G4 / Req: R4.4 / G4 NOT_READY，禁止进入 G5。** 本仓库仍以通用 AI 短剧工厂为目标；CityDiscount 只是首个公开工程测试样本，不是独立的品牌影片渲染器。

**最新 main 依据（全部 PR 的六项 GitHub CI 全绿后合并）：**
- [PR #204](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/204) → `4999581a7ac66f107fb7cd8144a4f2a09d45a781`：RGBA 使用明确白色底合成 RGB，避免透明角色图/Logo 黑底；Owner 的 Mac 复验 5 passed，1 个不阻断的 Starlette 弃用警告。
- [PR #205](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/205) → `fef57454b3f0fd3c9ddabe144a5f3f5bb4e8a444`：通用本地多角度 SHA→角色版本映射，拒绝重复使用同一源图冒充多个视角；不自动批准给模型使用。
- [PR #206](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/206) → `3ce27878e3114e3db0e61a2b8e3626f807b68259`：首批十张素材 Mac 清单登记（此时仅元信息）。
- **[PR #207](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/207) → main `aabb1d7e66a9244113122b86317bae93eb33c98a`**：Owner 的实际十张 PNG 已从 Mac 推送到隔离分支，经 Python 3.11/3.13 CI 逐张验证仓库 checked-out 原始 SHA256、RGBA 解码/尺寸、RGB 规范化及 FND-02 的离线 PNG 字节门禁；6/6 checks SUCCESS。资产目录 `assets/citydiscount/v1/character_views/`，绑定清单 `character_views_inventory.json`，测试 `tests/test_g4_local_image_inventory.py`。四张摄影视角：front/side/back/three_quarter；六张表情/动作：happy/wink/sparkle/jump/thumbsup/coin。

**明确的边界：** 这证明十张图真实存在、内容与 Owner 本机哈希一致且通用图片准入字节合同可用；不证明图像语义确为相应视角、不证明图片独立版权/外传权限、不表示为 Omni 签发了 FND-02 HMAC Grant，不存在真实付费视频提交或已完工 AI 影像。本轮模型调用数 0，新增费用 0 USD。当前 `model_submission_allowed=false`、`operator_approved_for_model=false`、`rights_independently_verified=false`。

**下一项（[Issue #201](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/201)）**：对四个真实视角执行人工语义/视觉确认与素材权限审查，在现有通用 FND-01、FND-02 签名镜头媒体门禁及 FND-03 首末帧上仅做临时密钥、无外部模型调用的 Fake dry-run；禁止拿十张图自动对外发送或启动 G5。

---

# 2026-10-20 最新权威状态：通用双项目 Fake 视频产线已真实 FFmpeg 全绿；下一步图像参考接线

**Stage: G4 / Req: R4.4 / G4 仍 NOT_READY，G5 禁止。** Owner 将本仓库主动切换为 **Public** 以恢复免费的 GitHub-hosted Actions CI，确认本项目用于**开发和验证通用 AI 短剧系统**，CityDiscount 只是第一套测试场景，**不得为了单条宣传片制造专属生产流水线**。公开后历史真实视频 Actions artifact/日志与用户上传的品牌素材可能被公开访问；未知是否旧日志泄密，不能宣称完整安全审计通过。真实账号密钥始终以 GitHub Secrets/本机隔离、不得输出。

**2026-10-20 GitHub 已核实的合并及 CI：**
1. [PR #197](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/197) **6/6 CI SUCCESS**, merge `e3d24b7e78ee69579e44e9006d0feeae8b4b1b3c`：把 Owner 选定的**新版**小羊完整 PNG（Git blob `a5665b80a8484d5124fb874576ff40372f5a7c06`、2,211,254 bytes）和 CD Logo（blob `903f96f235b5375fb540f3ad656ba39eea2b50e2`、93,326 bytes）以原始 Git 对象纳入 `main/assets/citydiscount/v1`，字节大小/Git blob SHA/PNG解码实际跑验；旧版本 SHA256 **不得套用新版**，新版本 SHA256 由可信 checkout 工具在运行时计算；Logo SHA256 `19a6202331db9853d384ddabd30fbdf738f139fd8721638eed54fde193011651` 已证实。
2. [PR #195](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/195) **6/6 SUCCESS**, merge `36176056f949e06530383bb551fe3214bba48fb8`：新增通用 `operator_storyboard_adapter.py`，复用**原有** StoryBible/FakeTextProvider/Screenplay/EpisodeDraft/video-plan，一套代码支持 CityDiscount 单羊12镜60秒和无关车站双演员6镜30秒。旁白/演员对白/画面文字严格分开，不冒充模型已创作或人审通过。
3. [PR #199](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/199) **6/6 SUCCESS**, merge `3349a54a375b020de9d30faabd33dd6b6471b0cd`：新增跨项目实际 TestClient→本地 SQLite / 原API两步模拟批准→已有 Fake Shot Worker→FFmpeg→MP4/字幕/哈希/缓存/隔离技术集成测试。**注意**：普通 Python CI 未安装 FFmpeg，因此该真实媒体用例曾被 skip，不能依赖这份报告冒称执行完成。
4. [PR #200](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/200) **6/6 SUCCESS**, merge **当前 main `60b2daaf75de774f051b72a40e5a5d410d06fc1e`**：只在已有 `offline-video` job 新增强制 FFmpeg/FFprobe 测试。实际执行 [offline-video job](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39366468656/job/118444351453) 于03:52 UTC，**2 passed、0 skipped、1 warning、3.56秒**；双项目真实渲染 **Fake 技术占位 H.264/AAC/mov_text MP4**，逐镜SHA和重复运行缓存均核实。**没有真实 Omni 模型动画/真实中文配音/已批准外传的参考图片/生成内容评分**，本轮新增模型调用0，API费用USD0。
5. [CI Issue #196](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/196) 原 Private 免费 3000/3000 分钟、超额预算 $0 阻断已在公开后恢复，现已关闭。[双项目 E2E Issue #198](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/198) 技术验收后关闭。过去旧短剧 W1–W5 源码/媒体/旧人工 QA 证据未改变，G4仍 NOT_READY。

**下一唯一通用研发入口：[Issue #201](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/201)**：在现有模型内把**真实图片的源 SHA、角色/道具版本、逐镜 ID 和 Scene/Prop 引用**接到 FND-01多视图图像计划、FND-02签名媒体准入、FND-03首末帧，再执行双项目 Provider Fake 多图 dry-run；不单独建 CityDiscount 视频引擎。真实 Provider 调用仍 prompt-only，照片外发、AMEND-006 首片路线正式调整、费用和真人 ASR/内容验收均需 Owner 单独授权（#188、#177）。不提前进入 G5、不删历史记录。

---

# 2026-10-20 · 统一资产和通用剧情入口分离；需要 GitHub Actions 原因才能验收

**Stage G4 / Req R4.4 / Owner 明确：开发测试通用短剧工厂而非单独生产 CityDiscount 影片。** 已经过期的专用预检 [Draft PR #193](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/193) **closed without merge**。本聊天不接受把独立11阶段假收据/静态预演说成真短剧产线通过。

1. **通用资产 Fixture [PR #197](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/197)，Draft 未合并：** 引用 Owner 已上传到 #193 分支的**完全相同 Git 对象**，在新分支 `assets/citydiscount/v1/mascot_character_sheet_v1.png`（Git SHA1 `a5665b80a8484d5124fb874576ff40372f5a7c06`, 2,211,254 bytes）和 `citydiscount_logo_v1.png`（`903f96f235b5375fb540f3ad656ba39eea2b50e2`, 93,326 bytes）。另有源资产 manifest 和读取真实字节/PNG/Blobs 验证测试。旧小羊 SHA256 不适用于新版，**新版 source SHA256 仍待 checkout 真字节验证**；Logo SHA256 `19a6202331db9853d384ddabd30fbdf738f139fd8721638eed54fde193011651` 已在本地原图按 Git blob 重新核对通过。两文件已在 GitHub 新 PR 分支但**都未入 main**。
2. **通用 StoryBible→ScriptPlan→Screenplay→EpisodeDraft→VideoRequestPlan [PR #195](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/195)，Draft 未合并：** 同一 Python 模块接受 1～8 人、1～12 镜人工 ShotCards，严格分别处理角色台词/旁白/后期文字，外部模型/真实视频/收费永远 false；两套独立测试（CityDiscount 单羊12×5秒/车站两位角色6×5秒），**没有开发 CityDiscount-only 视频总控**。
3. **GitHub Actions 真正阻塞 [Issue #196](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/196)：** #193/#195/#197 6/6 job 均约2秒失败/取消，`runner_name=""` / `steps=[]`，GitHub job logs 404 BlobNotFound。GitHub commit check output `annotations_count=2` 每 job，但 connector 不允许读取 annotation API。2026-10-19 GitHub 全球 Actions incident 在同日 16:56 UTC 已宣布 resolved；这些异常在 2026-10-20 02:xx UTC 出现，因此**全球故障不能直接认定为根因**。Issue #196 给 Owner 一条只读 `gh api .../annotations` 命令查实际原因。未经绿灯禁止 merge/disable CI/反复 rerun。账号 Actions 预算或 Runner 配额**仅是待查假说**。
4. **下一步**：有 job annotation 诊断后修 GitHub Actions 运行条件，再针对两个独立PR拿到 6/6 执行证据；然后统一在现有 FakeVideoProvider/FFmpeg/QA 链上做两个题材的受控真端到端。既有 FND-01/02/03 多视图、逐镜参考帧接口复用，不重新造轮子。真实 Omni 视频或图片外发仍需权限/AMEND 决策。G4 NOT_READY，G5 禁止，新增付费模型调用 0、USD0。

---

# 2026-10-20 · 最新：通用短剧工厂优先，CityDiscount 仅 Pilot 01（未合并代码）

**Stage: G4 · Req: R4.4 · Owner 最新指令：** “这个项目是用来测试和开发我们的短剧系统的，而不是为了生产video而做视频”。CityDiscount 仅第一组内容/资产测试，验收必须证明第二组无关题材也走同一 StoryBible→Screenplay→VideoProvider→FFmpeg/QA 合同，**不允许 CityDiscount-only 的第二套生产脚本**。

- **角色版本确定：** Owner 2026-10-20 明确采用 **GitHub 上传的新版小羊 V1**，PR [#193](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/193) Draft 分支 `assets/citydiscount/v1/mascot_character_sheet_v1.png`（Git blob `a5665b80a8484d5124fb874576ff40372f5a7c06`，2,211,254 bytes）。旧小羊的 SHA256 `79e653ff...` 不再适用。GitHub connector 无法读取超1MB二进制，当前新图 SHA256 **待可信 checkout 真字节 readback**，PR #193 已将旧 SHA 标为 null、编入精确 blob 和实际文件名，运行时必须校验 Git blob+计算 SHA256；不需要 Owner 重传。Logo Git blob `903f96f235b5375fb540f3ad656ba39eea2b50e2`，原 SHA256 `19a62023...` 已证实。
- **通用实现：[Issue #194](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/194)，[PR #195](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/195)**：新增独立 `pipeline/operator_storyboard_adapter.py`，将任何1–8人、30–90秒、1–12镜的人工创意卡复用已有 `StoryBible`、`FakeTextProvider`、`Screenplay`、`EpisodeDraft`、`build_screenplay_video_plan`，保留分镜 SHA、角色 speaker 校验、逐镜依赖和旁白/字幕分轨，绝不伪造已审核剧本、模型视频或真实音轨。测试用 CityDiscount 12×5秒+另一部两人车站故事6×5秒。不是 AI Writer 已实际生成故事，也不是 Omni 图片真实接入。
- **CI 真实阻断：** PR #193 与 #195 的全部 scope / Python3.11/3.13 / offline-video / Fake artifact / local-libSQL check-runs 在 runner 启动阶段失败/取消，`fetch_workflow_job_steps=[]`、日志404 BlobNotFound，初次重跑后仍如此。**不能宣称代码通过；不能合并任何红 CI PR；不要无休止重试。** 已建 [需 Owner 检查 GitHub Actions issue #196](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/196)。根因未证实、不可私自关闭 Scope Guard。
- **下一真正开发方向：** 在当前 Schema 上完成通用来源媒体版本入库→已批准 StoryBible→人工/真实 TextProvider 剧本→12镜导演表→FND01–03 视频图片引用（先 Fake、再另行真实授权）→现有 FFmpeg/QA；逐层真实证据，杜绝只输出假的11步 JSON 就称 MP4 成功。原 W1–W5/旧真视频不动。
- **权限不变：** G4 `NOT_READY`、G5/W6 禁止。AMEND-006 旧双主角首片目标与新 CityDiscount 创意不同，只有 Owner 可以写 Active AMEND；新版小羊同意用于 repo 测试不等于允许外发至 Google 或授权收费模型。真人 ASR #177/视频预算 #188 独立待决定。本轮新增 paid model calls=0、API USD0。

---

# 最新权威状态：G4 首片方向切换 CityDiscount 宣传片，60秒12镜/离线合同已交付（2026-10-20 NZT）

**Stage: G4 / Req: R4.4 / G4 NOT_READY。** Owner 在原12镜人工反馈和 FND-00–03 基础框架全CI通过后正式指示：“第一个视频方向改成一个生成我们citydiscount的宣传片”。这只改变**下一条新真实视频的创意目标**，不取消已有真实短剧素材/人审问题、旧FND基础框架，也不授权生成、上传、付款或发布。CityDiscount 是新西兰华语本地优惠资讯/消费比较品牌，不能宣传为已上线App、扫码领券或商家独家合作。

- **创意/离线代码已入main**：[CityDiscount Issue #190](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/190) 与 [PR #191](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/191)：GitHub CI **6/6 SUCCESS**，Python3.11/3.13各 **932 passed、176 skipped**，squash合并 `a7f5a862a55c58649d951a2cb2e47a7a77cc7702`。新增 [60秒12镜分镜JSON](../../config/pilots/citydiscount_first_promo_v1.json)、[CityDiscount品牌片简报](../pilots/CITYDISCOUNT_FIRST_PROMO_BRIEF.md)、`pipeline/promo_motion_graphics.py` **零演员/品牌动效纯离线profile** 和相关合同/广告事实门禁测试。9:16、12×5秒、中文旁白、本地优惠/价格条件/信息来源、漫画/街头涂鸦视觉；正式中文标题/Logo/CTA由后期定版叠加，不由视频模型捏造。
- **框架基础继续有效**：FND-00–03 PR #182/#184/#187/#189已合并；真实 `google_omni_video.py` 仍 prompt-only。CityDiscount promo profile 目前只产生离线分镜计划，**尚未直接经W2双演员FND-01合同或W3后期生成影片**。不得为适应格式伪造演员或跳过来源/权限门禁；需要下一独立薄适配层把promo shot、brand reference和graphic overlay交给已有Provider与FFmpeg后期，有Fake与CI才算可生产。
- **下一决策与测试**：[Issue #188](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/188) 已由旧茶馆真A/B更新为CityDiscount首片真测试。Owner需按仓库规定正式处理AMEND-006历史双主角毛毡定位的首片例外（PR#191是Proposed AMEND，未改Active）、提供有使用权的CityDiscount Logo/品牌视觉/真实CTA，核查Google Omni当前SDK/限额/费用和图片外发许可；最多2–3镜独立真实试生成后才可决定60秒整片。旧USD5权不可复用。#177 Gemini/ASR独立待授权。
- **真实完成边界**：本轮**无CityDiscount MP4**、无模型真实上传/生成、无新费用；真实模型参考图改善、实际账单、G4内容与发布均未证明。G4 NOT_READY，G5/W6禁止。

---

# 最新权威状态：G4/FND-00–03 完整离线视觉生产框架已合并并统一测试，等待未来经授权的真实 A/B（2026-10-19 NZT）

**Stage: G4 / Req: R4.4（R4.3 自动 QA 独立）/ G4 NOT_READY。** Owner 12镜真人未签字反馈后明确要求：“先把整体都搭建好，跟着开源视频代码，然后再统一测试”，停止逐镜 Prompt 修补。GitHub 主线源码级高热度开源对照和完整视觉产线已落地。**这不是 G4 发布/退出或额外模型/素材上传批准。**

- **FND-00**：[PR #182](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/182) 六绿并入 `cc5e5f871e8bd10e64e6660b4bda3978d4237833`；源码/许可证/差距见 [架构审计](../G4_VISUAL_PRODUCTION_ARCHITECTURE.md)。
- **FND-01**：[PR #184](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/184) 六绿并入 `75774051751b6f33a01f63e41873dca83f908658`；角色正侧背、scene/prop 版本图与 shot graph 依赖离线计划。
- **FND-02 + FND-03**：[PR #187](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/187) **GitHub 6/6 full CI SUCCESS 后合并 main `cc66d82517c895c794d889ecd2b572d374631d00`**（Python 3.11/3.13 **各922 passed、176 skipped**；scope、offline-video、fake-artifact、local-libSQL 均绿）。新增：独立操作员签名/有效期/版次/顺序范围 HMAC+实 PNG 字节/SHA/RGB 安全核验；同场景已批准 first/last keyframe 和明确上一镜 last 继承；Google Omni `image+text`/`IMAGE_REF_N`/`FIRST_FRAME`/`LAST_FRAME` **离线请求数组**；整集12镜一条 CLI 可用的 Fake replay 和 receipt SHA。详见 [G4离线产线运行手册](../G4_VISUAL_SPINE_INTEGRATION.md)。`FND-02 #185` 已完成并关闭。
- **当前下一唯一决策**：[FND-04 统一真实 A/B 授权 #188](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/188)：**先核准实际参考图来源/使用权/跨境传输、确认 AMEND-006 历史暂缓定妆照的政策调整、Google Omni 当前 SDK/媒体传输/费用边界及单次预算，然后单独审查默认关闭的最小 live reference adapter，只执行 2–3 镜真实对照。** 未得到明确新授权前 **不得模型调用/外发任何图片/重生12镜**，以前消耗的 USD5 不能复用。Issue #177 Gemini/ASR 实际评估也保持独立未授权。
- **当前可信声明**：FND-00–03 离线基础架构已经实现、测试通过；**生产的`google_omni_video.py`仍 prompt-only，没有真实 reference_applied、真实同脸改善、ASR、供应商实账或发布批准**。本轮新增模型调用0、USD0，W1–W5 已交付源码/原真实影片/冻结区和治理文件不变。W5 `content=fail`、`release=blocked`、G4 `NOT_READY`；G5/W6 禁止。

---

# 最新权威状态：G4 基础视频生产框架重整 FND-01 已合并 → FND-02（2026-10-19 NZT）

**Stage: G4 / Req: R4.4 / G4 出厂仍 NOT_READY。** Owner 在 s01–s12 第一轮**未正式签字**人工审片后，要求**先调查高热度成熟 AI 短剧项目，建立可核验的角色/场景/道具资产和分镜依赖生产框架，再回到个别坏镜头**。这不是批准付费修镜、发布或进入 G5。架构入口 [Issue #181](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/181)；[FND-00 PR #182](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/182) 六项CI全绿合并 main `cc5e5f871e8bd10e64e6660b4bda3978d4237833`，新增 [源码级架构审计](../G4_VISUAL_PRODUCTION_ARCHITECTURE.md)。

**FND-01 正式完成**：[Issue #183](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/183) 与 [PR #184](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/184) 六项 CI SUCCESS、local 11 tests pass 后合并 **main `75774051751b6f33a01f63e41873dca83f908658`**。仅新增 `pipeline/visual_production_plan.py` 与测试，复用 W2 版本资产，选择镜位匹配的角色正/侧/背图和固定场景/道具，构造12镜离线 candidate plan/稳定 SHA/下游失效依赖；非法图片授权/版本/跨项目/镜位/图数/未来依赖 fail closed。**当前无真实可用经独立批准的参考图库；所有输出 `provider_reference_applied=false`、`model_submission_allowed=false`、`production_assets_verified=false`、模型调用0。不是已有 Omni 生产参考图接线完成，也不是内容一致性真实改善。**

**下一唯一框架工作包：[FND-02 Issue #185](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/185)**：只做零费用多模态媒体准入、ProviderCapability 和 Omni 图像角色输入的 dry-run/Fake 请求合同，不碰 W1–W5 已交付源码/旧视频/冻结区/治理。FND-03 后续做首帧候选与审核，FND-04 要新 Owner 预算/许可/隐私授权才能真实2–3镜 A/B。现行 AMEND-006“毛毡暂不需要定妆图”与新观察有策略差异，Agent 不自行改 Active；如需开启真实生产参考图，先由 Owner 正式作治理决策。[R4.3 Gemini/ASR 决策 #177](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/177) 继续开放且**未授权**。W1–W5 交付及 W5 NOT_READY 审计仍保持；G5/W6 禁止，发布不可。

---

# 最新权威状态：W5 已完成零费用真实媒体 CLI 集成审计 — G4 NOT_READY（2026-10-19 NZT）

**Stage: G4 / Req: R4.4 / W5**。唯一验收清单 [G4_ACCEPTANCE_20261019.md](G4_ACCEPTANCE_20261019.md) + [机器 JSON](G4_ACCEPTANCE_20261019.json)，正式 Issue #179。开工 main 2cc91f54a030ba2bc1e7e679c3f409126e912ee8。W5 从 GitHub Run39141517448 两份真实 Artifact 下载并亲自运行 Git-blob 验证的 W4 CLI，原版/W1-FAKE 技术各 PASS、内容 FAIL、发布 BLOCKED；两份报告 SHA 与 W4 已记录离线基线一致；跨版本混用 fail-closed。真人签字仍 0，已证实合格镜头0/历史3需修/其余9未知，Gemini视觉打分和ASR not_run，旧供应商账单及人工工时 unknown。**NOT_READY = W5 工程审计结论，不是 G4 退出。**

**下一唯一行动：Owner 对 Issue #177 的 Gemini/ASR/权利/费用做明确授权或延期决定，并组织真人审片与供应商账单/人工计时补证；缺独立 G4 工单才允许另行安排受控修镜/完整真实流水线核验。** W1–W4 源码不改；未授权新付费API调用0/USD0；不可 G5/W6、不可发布。W5 文档 PR 必须 CI 6/6 绿后才自治合并，最终合并回执存 Issue #179。

---

# 最新权威状态：W4 离线内容 QA 工程交付完成 → W5（2026-10-19 NZT）

**Stage: G4 / Req: R4.3 / W4.1 + W4.2 已完成零费用工程验收。下一个唯一工作包：W5（仍 G4）。** [PR #176](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/176) 6/6 CI 全绿（scope、Python 3.11/3.13 各897 passed/176 skipped、offline-video、Fake、libSQL），已合并 main `40aedd50306919ea2b7451fc734030cbb9eb92e9`。正式 [W4 标准交接](W4_EVIDENCE_20261019.md) 与 [Issue #175 最终评论](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/175) 是输入权威。上一阶段 W1/W2/W3 工程已完成、不重复开发。

- **真实媒体核验**：[Run39141517448](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39141517448) 原版 Artifact 12142320238、W1-FAKE Artifact 12141772943 已下载并独立校验 MP4/SRT/render receipt 哈希、12 镜 60.156 秒 FFprobe 时间轴、两版 60.177333 秒 H264/AAC/mov_text、实际全解码。没有新生成视频/新付费模型调用；历史供应商实际账单仍未知。
- **内容 QA 仍有阻断**：原版 s03/s09 年龄外貌漂移、s07 三格分屏历史 P0；W1-FAKE s07 只是旧 s04 回填，不能算质量修复。两版各3镜需修、其余9镜 `unknown`，真人独立签字0镜；字幕 DRAFT 非 ASR，中文实际对白、配音音色、口型/字幕对齐 `unknown`。独立三门禁：`technical=pass`、`content=fail`（已知历史负面）、`release=blocked`；`publish_approved=false`。
- **正式 R4.3 尚未完成**：Gemini 相邻镜头真实自动打分 `not_run`，中文 ASR `not_run`。新 [所有者决策 #177](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/177) 明确后续预算/许可/隐私前置；不能把 Fake 分数或 CI 作为真实视觉预检通过。G4 没有退出，G5 继续禁止。
- **唯一下一工作包 W5**：只读集成阶段验收，不提前实现 R4.3 收费分支；必须核对真实合格镜头≥50%、真实供应商账单≤USD30/合格分钟、人工时长≤2h、Gemini 视觉自动预检缺口以及所有者 G4/发布签字。未知指标绝不能用零代替。W4 源码后续维护由 M4 负责；W5 不重写 W1/W2/W3/W4。

---

# 当前交接状态（2026-10-19 NZT）

## 最新权威状态：W3 真实后期来源验收成功 → W4 内容 QA（2026-10-19 NZT）

**Stage: G4 / Req: R4.4 / W3.1 已完成；下一唯一工作包 W4（G4/R4.3）。** [PR #173](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/173) 6 项 CI 全绿合并至 `main@4c16e12d8d4aebd4395ba43b2512de61825c4d80`。[真实素材 Run39141517448](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39141517448) 成功；原真实版 Artifact **12142320238**、W1-FAKE s07 修镜后严验版 Artifact **12141772943**，分别保留 12 镜实测毫秒时间轴、源报告/视频 SHA、16 cue 剧本推算 DRAFT 字幕及 MP4 SHA、来源/父版本 `09_render` receipt、`10_qa` 独立校验。最终媒体均 60.177333s，H264/AAC/mov_text，Full Decode pass；原/新 MP4 SHA 分别 `d4208ccb7b4353e184eb7d003125a010e20f8dedf7a3a9bc0eee85a0e4f041f7` / `de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f`。旧 s04 只是模拟 s07，不是质量修复。详见 [W3 标准证据包](W3_EVIDENCE_20261019.md)。

- **复用而不重写**：已有 `postprocess_gpt_episode_offline`、`assemble_gpt_video_three`、`offline_qa`、W1 修镜、FFmpeg；W1/W2 源码冻结无变更。W3.2 无本地获授权 WAV/许可证据，按 Issue #171 的条件性范围不启用，也不改通用 `offline_audio.mix_local_stems`；默认原生中文 AAC 透传。
- **仍未通过**：W2 生产资产 Manifest SHA=null / assets verified=false；W3 字幕 **draft_not_asr**、原始 Omni **prompt_anchor_only**；同脸/同声、对白内容、字幕实际对齐、人类内容审查、真正修镜和发布均 `false/pending`。新模型调用 0、增量 API 费用 USD0；旧真实供应商账单仍未知。**G4 未退出，G5 禁止。**
- **下一个唯一任务 W4**：Owner M4（G4/R4.3）只用 W3 Artifact 中原版+W1-FAKE 两份 `09_render.json`、`10_qa.json`、`draft-captions.srt`、MP4 和 W2 离线 prompt-binding 契约，按每镜 ID/真实哈希/时间轴做人物外貌、声线/中文对白、口型、字幕和 s03/s09/s07 已知故障的审片与人工签字；没有实际 ASR/镜头一致性与内容许可证据则状态 `unknown`，不得宣称发布可用。**W4 不改 W1/W2/W3 已交付源码，不进行付费生成。**

下面 W2/W1 历史章节只作历史证据，其“下一个任务 W3/W2”已被本最新指针覆盖。


## 当前权威状态：W2 离线验收通过 → W3 增量后期交接（2026-10-19 NZT）

**Stage: G4 / Req: R4.4 / 下一个工作包 W3。** 2026-10-19 已核验 W2 [PR #170](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/170) 合并至 `main@278763505b165e6a637a8acecc4b162121b3170a`；7 项 GitHub check-run success，Python 3.11 / 3.13 各 883 passed、171 skipped。Issue [#169](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/169) 已关闭，且 [最终 `drama-stage-handoff.v1`](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/169#issuecomment-6251556462) 已登记。W2 纯离线绑定，通过 `pipeline/shot_asset_binding.py` 锁定角色/scene/服装规格/speaker/资产版本、源 SHA 与 Prompt 变更；**没有真实生产版 W2 manifest SHA、没有真参考图/音频注入、没有新视频生成或人工内容验收。**

- **下一个唯一开发 Issue：[W3 #171](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/171)**：增量真实后期——先补 W1 已有修镜版本/原12镜的实测时间轴、来源与输出 receipt 证明；需要时仅使用本地合法授权 WAV 验证可选配乐，且必须保留原生中文对白。已有真实 DRAFT 字幕/FFmpeg 后期 Run39133557599、W1-FAKE Run39137352545 不重做。W2 没有真实锁定 Manifest 时**绝不能写生产 assets verified**。
- W1 / W2 源码冻结，分别由对应模型完成并交接；W3 只改后期 Owner 范围，零付费/不碰 Omni Provider、冻结 TTS、生产资产历史和治理文件；PR/CI/Run/Artifact/准确源 SHA 后方能标 W3 通过。
- **G4 尚未退出，G5 禁止**；`publish_approved=false`、对白/字幕实际对齐及人物声线未通过，早期一次 USD5 权限已经消费且不得重用。
- 本节是最新任务指针；下面 W2 施工、W1 与真实12镜章节保留为历史证据，不能把其中的“待 W2 验收后”作为现在仍在等待的任务。

## G4/R4.4 W2 资产与对白版本绑定（2026-10-19 NZT；PR #170）

- W1 已正式通过且被冻结，不重复 W1 / FFmpeg / 后期，也不修改历史12镜或一次性费用权限。本 W2 从 main 409d042ae00e6d66fd097b86e0d34555eb20b83e 开发。
- 单一 W2 执行 PR：[#170](https://github.com/Mrlukahuang/ai-short-drama-factory/pull/170)。新增只读 `pipeline/shot_asset_binding.py`；继续复用 Screenplay 验证器、`check_screenplay_scope`、`build_screenplay_video_plan`、ActorBible/SceneBible/VoiceBible；不复制上游 ViMax/Jellyfish 源码。测试与端口边界见 [W2_SHOT_ASSET_BINDING.md](../W2_SHOT_ASSET_BINDING.md)。
- 核心交付：固定 story/script/source/style + 资产 ID/version/specification SHA、逐镜外貌/服装/scene、cue speaker/expected dialogue，双 Prompt SHA 与 canonical manifest SHA。供消费的是 `prompt_anchor_only`，**不支持 reference image/audio**，原审批、媒体、账单、技术与内容审核均不被改写。
- 按 [Issue #169](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/169) 验收：PR 的 Python/scope/offline CI 必须全部绿才算完成并可依 AMEND-004 自治合并；任何检查未完成不得宣称通过。正式已合并 main SHA 和最终 `drama-stage-handoff.v1` 以 #169 的最后交接回执为准。
- **下一任务（待 W2 成功合并后）**：依最新 Bible 继续 G4 工作包 W3；W4 需要使用该 manifest 做内容 QA，不能提前进入 G5。任何真正 Omni/参考音视频能力验证另需授权。

## 持久开发 Bible（2026-10-19，G4/R4.4 技术实施指南）

- [开发 Bible 总入口](../DEVELOPMENT_BIBLE.md)：架构、正式 G0–G7 与可交付 W0–W8 的边界、现有真实代码/Artifact 复用原则。
- [成熟开源复用](../development_bible/OPEN_SOURCE_REUSE.md)：OpenMontage/HyperFrames/ViMax/Jellyfish 固定 commit、源码路径、许可与最小移植检查表。
- [阶段交付与验收](../development_bible/STAGE_DELIVERABLES.md)、[多模型无损交接](../development_bible/MODEL_HANDOFF.md)：不同模型换聊天前必须使用统一证据包与明确文件 Owner。
- **本段仅指向技术实施规范，不重排本文件现有“单一下一任务”，不授权 G5/付费模型/冻结区或治理变更。**

## 当前权威状态：W1 零费用端到端验收通过（2026-10-19 NZT）

**Stage: G4 / Req: R4.4 / W1**。开发 Bible `main@ac28e5d` 后实现 W1，#166 与 #167 已合并；核实后的代码主干为 `1792fb387ac907d3da808348128eddce5924f793`。**W1 的 0-call/Fake 部分已用真实旧12镜素材通过，独立付费单镜生成仍禁用且尚未验收。G4 未退出，G5 禁止。**

- [Run39137352545](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39137352545) 全部步骤 success；W1-FAKE Artifact ID `12140422056`，字幕 DRAFT Artifact ID `12140556405`。使用已存在真实 `s04` **仅模拟**替换失败 `s07`，其余11镜 SHA 不变，旧整集 MP4 SHA `f76daf3065796ef847500041648f5dadb1cffa98898c466f11ac3471be9e8887` 不变；新回填+后期 MP4 SHA `de6d623523d8537461571b66508ee997a28e10fed23cd927900c3f8370a6df2f`。
- 自治 Scope/Tests 全绿；媒体技术 QA 通过，内容/声线/对白/字幕实际对齐及发布均未通过；**新供应商视频调用0、新 API 费用USD0**。先前一次 USD5 claim 不可再用、真实账单未知。
- W1 标准机器可读 handoff 与下一包输入输出见 [W1_EVIDENCE_20261019.md](W1_EVIDENCE_20261019.md)。
- **下一唯一开发包：W2**（仍 G4/R4.4），按 Bible 开发人物/场景/说话者逐镜资产版本与 Prompt 锚定的离线契约；其输入为 W1 的原视频/剧本 SHA、per-shot repair plan、source receipts 与11镜 SHA，不触碰 W1/后期/合成所有权范围；输出必须确定性、冲突 ID/版本 fail-closed，模型参考图/音频不能谎称已经支持。
- W1 真正单镜有偿请求继续作为**阻塞的后续独立审批任务**：须可证实供应商成本保护、当日支出、新的一次性授权/任务接收回执；本次 W1 Fake 成功不等于收费分支获准。

## 早期施工记录（历史，非当前下一任务）

## 新 Development Bible / W1 当前施工（2026-10-19）

- main 起点 `ac28e5dff9c9ff7035881a4ef2e07f231cc35abf`，PR #165 已合并；Stage **G4** / Req **R4.4** / W1，按 `docs/development_bible/STAGE_DELIVERABLES.md` 的单镜定向修复零付费合同优先。
- 本轮新 `scripts/w1_single_shot_repair.py` 是薄适配：原剧本固定校验 + 单个 failed shot 计划 + 独立收费未批准状态 + 已有本地 Fake 镜头接收 + 复用 `repair_gpt_episode_offline.py` 单镜回填 + `postprocess_gpt_episode_offline.py` 草稿字幕、原生音轨与技术 QA。
- `scripts/repair_gpt_episode_offline.py` 仅加历史 `prior_shot_receipt`，保留被替换片原 Prompt/任务/账单；不修改其它11镜、原媒体或已用 USD5 claim。
- 现有 `gpt-episode-postprocess-offline.yml` 增加一个**明确标记 W1-FAKE** 的只读真实12镜离线回填演练：使用真实旧 s04 模拟 s07 的替代**绝非真实质量修复**。不能冒称新供应商请求完成。
- 验收以本轮 PR 实际 CI、真实 Artifact 成功记录为准；当前不宣称已通过直至工具证实。本轮 **0 新模型调用/费用USD0**。
- 详细 I/O、回滚和 W2 输入输出/禁止重复开发见 [W1_SINGLE_SHOT_REPAIR.md](../W1_SINGLE_SHOT_REPAIR.md)。
- **单一下一任务（待 W1 验收后）**：W2 角色/场景/对话的生产资产 ID/version/固定锚点离线契约，G4/R4.4；禁止动 W1 修镜/现有后期、冻结区和付费生成。W1 后续真实单镜付费生产仍需要独立可核实授权与供应商成本上限评估，未获则保持关闭。

## Stage / Req / 当前交付

Stage: G4 / Req: R4.4。真实 12 镜链路已成功生成+拼接，但用户审片认为人物与配音不合格。**不得把技术通过视为内容通过或 G4 退出。** 仍在 G4，不启动 G5。

## 当前可核实的真实证据

- main 最后由 GitHub PR #157 合并确认 `8bf859bf81f9ef7edbe056b0d0283c82fdc51503`；实际生产 Run [39130058487](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39130058487) 的 `video3` job 为 `success`。
- 12 镜：s01–s03 复用 Run39047208593，s04–s12 新生成 9 镜；原始文本来源 Sol Run39035812309；成片总长 60.177333 秒、360×640 H264/AAC，哈希 `f76daf3065796ef847500041648f5dadb1cffa98898c466f11ac3471be9e8887`，解码通过。
- 最终标记 `technical_preview_passed_pending_human_review`；`all_script_shots_assembled=true`、`g4_duration_range_passed=true`，但 `full_episode_complete=false`、`publish_approved=false`、`dialogue_content_verified=false`、`subtitle_alignment_verified=false`。
- 本次9镜估算 USD4.27173825、一次 USD5 风险确认**已消费**，供应商实际账单仍未知；绝不作为重新执行/重试许可。#158 原批准请求尚需留档收尾；#137 的 F3 原费仍待核。
- 已根据用户实际上传的原版 MP4 逐镜抽取 0.5/2.5/4.5 秒画面。**人物一致性失败**：s03/s09 灰发年长男与 s04/s05/s11/s12 年轻男变化；s07 三格分屏；画面文字/道具不稳。音轨技术存在，但未完成可信语音转写及音色逐镜试听，用户明确报告配音不合格。
- 详细根因与分级见 [GPT_EPISODE_VISUAL_REVIEW_20261019.md](../GPT_EPISODE_VISUAL_REVIEW_20261019.md)。真实路径是 Sol screenplay→prompt-only Omni 独立生成→FFmpeg concat；没有把完整 P/Fake 11步资产/声音/字幕/内容 QA 路径真实打通。
- 原有 Google 文本 Flash400 未修，不阻塞当前 GPT 基线；Sol/Luna/Flash 18 任务盲测尚未执行完整。临时编剧 Sol，不宣称正式主备已定。

## 最新真实后期重放结果（2026-10-19 NZT）

- PR #160 合并 `5212885207c7359f378f298a116edcfa7c77f9b2`：已完成12镜**单镜已有替换视频**离线回填、11镜原文件哈希保持和FFmpeg重拼接/解码。不是付费模型单镜重生成。
- PR #161 合并 `a7f32422add126ab734d5ed3b7043aa4396db3d6`：真实12镜+原 Sol 剧本进入离线 06–10 后期；草稿 SRT/原 H264/AAC 透传/mov_text 封装与 QA；主干自动跑真实 artifact 工作流。
- PR #162 合并 `e594cb8ffa1143e9b369dba47fa4f994ddfc7145`：仅修 Actions `GITHUB_PATH` 延迟生效造成的初次离线任务FFmpeg找不到（首次 Run39133331156 failed before postprocess；没有调用视频模型）。
- **最新真实成功 Run：[39133557599](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39133557599)**，job `postproduce-real` success。读取原文本 Run39035812309 和已成功12镜 Run39130058487，Artifact `12138992023` 名 `gpt-real-12shot-caption-DRAFT-39133557599`（约6.02MB压缩）；真实原始镜头没有重新生成；本次 API 模型调用0、模型费用USD0。
- 此新 MP4 的字幕是**按剧本与真实片段时长估算**并已验证嵌入，不是 ASR 转写/口型或字词对齐验收；原生 AAC 音轨保留，`08_music` 记录 native 透传，**没有单独新音乐**；人物、音色、内容、费用核对及发布审批仍未通过。
- 给所有者的进度估算：最短真实生产到技术后期的链路已通过，G4 MVP **约85%（剩约15%，工程估算非验收百分比）**；G4 尚未正式退出，G5 未启动。

**单一下一任务（仍优先全链路可用性）**：整理真实单镜付费修复的最小授权/失败镜头衔接与可重复交付验收；以现有12镜产物为基线，先做离线流程，费用授权和任何新视频生成必须另外明确批准。内容精修/模型切换延后，但正式 G4 退出仍需符合质量、实际账单及人工审批标准。

## 当前执行方向（所有者 2026-10-19 再次明确）

**优先把生产流水线跑顺，而不是现在精修人物、音色或剧情。** 本轮 Stage: G4 / Req: R4.4 追加一项不收费的真实视频后期能力：使用已有外部 MP4 对完整12镜中的指定一镜进行离线替换，只重拼接、校验，不重生成11个其它镜头。新增脚本 `scripts/repair_gpt_episode_offline.py`、离线真实 FFmpeg 合成测试及 `docs/GPT_EPISODE_COMPLETION.md` 使用说明。生成与真实质量审核仍未因此通过。

**单一下一步**：在此 PR 绿灯合并后，继续打通**真实生成视频到后期**的最短路径（剧本对应的字幕草稿、可选配乐与版本化输出），保留原生中文音轨和严格区分“推定字幕”和“经过转写验证”的标记；先复用已有真实视频离线测通，严禁新增收费调用或冒称内容验收通过。

评估给所有者的进度：最短 Sol/GPT→12镜Omni→FFmpeg→技术QA已经真实成功；G4全流程约75%（主观工程估算，不是自动化量化验收），剩25%主要是完整真实后期接线、单镜实际生成/修复的收费授权衔接、内容/费用最终验收。G4未正式退出。

## 本轮继续接线：真实整集离线后期（G4/R4.4）

在已经成功的 12 镜真实 MP4 + 已验证 Sol 剧本上，不重新生成视频：
- `scripts/postprocess_gpt_episode_offline.py` 新增已完成源素材哈希核对、现有原生音轨 stream copy、按原剧本与实际镜头时长换算的**估算字幕**、SRT→MP4 mov_text 封装与实际 mux 字幕逐字对照、完整媒体解码、`06_dialogue`–`10_qa` 五项落地 JSON。
- **明确没有 ASR、原声音色检验或新增配乐**；单独 `08_music` 只记载 native-audio 透传，字幕虽能入 MP4 也仍需逐字/对齐审查；不宣称 G4 退出、发布或 11 步所有质量门禁满足。
- 使用仓库原视频/文字 artifact 的离线新目录验收；测试用 FFmpeg 合成12镜，零新的模型调用/费用、零密钥。
- 继续采用用户的“先跑通全链路，后调演员及配音”优先级。

**单一下一步：** 本 PR 所有 CI 绿后自合并；下一步核对已通过的真实12镜素材，跑一次这个不收费的后期路径，并再评估 G4 阶段剩余缺口（逐镜付费重生成合法授权/转写内容验收/真实发片质量）。真实供应商账单仍未知。

## 上次审查记录（非本轮开发重点）

**先修“人物/声音生产契约与验收缺口”，不是盲目重生整集。** 复用现有角色及场景资产 Schema，先把每镜头统一角色详细定妆描述、资产 ID 与逐镜 speaker/dialogue 审核字段接入真实请求计划并有离线测试；明确当前 Omni provider 不支持 reference image/audio。随后加真实镜头内容 QA 入口及人工验收记录，考虑 R4.3 视觉跨镜检查。应按每个 G4 Req 单独小 PR 执行，更新交接文件。

只有确认能防止同脸同声漂移、并经过新的所有者费用许可，才测试最小 2–3 镜片段；不重跑12镜，不改冻结 TTS、基础设施、模型选型或发布门禁。

## 约束

AMEND-001 冻结路径不得动；AGENTS/GUARDRAILS/STAGES/AMEND 不经所有者许可不得修改。用户要求加速、减少重复确认但不能跳过收费限制。实际费用仍未知；真实已执行的一次 USD5 标记不可清理；没有新授权不得重新生成视频。
