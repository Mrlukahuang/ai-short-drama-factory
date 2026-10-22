# 交接历史（追加，不改旧条目）

格式：`日期 | Agent | Stage/Req | 做了什么 | PR`

- 2026-10-15 | Claude | G0/R0.1–R0.5 | 建立 AMEND / CHARTER / STAGES / GUARDRAILS / 参考项目 / 模型现状 / 交接机制 / scope guard；冻结 PR31 存储实验 | docs/g0-charter-guardrails
- 2026-10-15 | GPT-6 | G1/R1.3 | 统一 VideoProvider 请求/结果协议；Omni + Fake 适配与离线测试，无付费调用；其余两家 Provider 待 R1.1/R1.2；所有者合并后移交 | PR #114
- 2026-10-15 | GPT-6 | G1/R1.1 | 火山方舟 Seedance 2.5 Provider+Fake+无密钥契约测试；零真实调用/零费用；需新 Key/平台决定 Issue #116 | PR #117
- 2026-10-15 | GPT-6 | G1/R1.2 | Kling 3.0 Omni 可配置 Provider+Fake+离线合同与 FFmpeg，0 次真实请求/US$0；新 Key 见 Issue #116 | PR #118
- 2026-10-15 | GPT-6 | G1/R1.5 | 固定3镜×3模型×1 PLAN-ONLY；手动确认+≤$30计划上限，实际付费0次/US$0，真实运行需预算Issue #120 | PR #121
- 2026-10-16 | GPT-6 | G1/R1.6 | 按所有者暂停所有真实测试；Mock 中文CER+合成媒体ffprobe QA、九任务pending results.json；0真实模型/US$0，完整真实验收延期 | PR #122
- 2026-10-16 | GPT-6 | P/P0 (AMEND-005) | 仅文档：全11步仓库复用矩阵、ViMax MIT/Jellyfish Apache-2.0 源码定位、P1–P6/P-final 与 STAGES Req 映射；G1真测及Issues #116/#119/#120挂起，0调用/$0 | P0 PR
- 2026-10-16 | GPT-6 | P/P1 [STAGES R4.1 Fake] | 本地 UTF-8 梗概→可验证原有 StoryBible schema 的确定性 Fake JSON，SHA256 输入溯源、无覆盖 CLI、拒绝危险文件；0 模型/US$0 | P1 PR
- 2026-10-16 | GPT-6 | P/P2 [STAGES R4.1/R3.1 Fake] | FakeTextProvider→结构合法六镜中文对白Screenplay，临时资产ID不属于数据库且不自动审核/提交；0模型/US$0，P3处理正式绑定 | P2 PR
- 2026-10-16 | GPT-6 | P/P3 [STAGES R2.1/R2.3 Fake] | P2临时角色/场景绑定本机SQLite现有Series/Bible/5项v1 Fake演员音色场景资产；单事务幂等、跨剧/冲突拒绝；零真实模型/US$0 | P3 PR
- 2026-10-16 | GPT-6 | P/P4 [STAGES R3.2 Fake] | 复用已审批Production的现成Fake worker/FFmpeg镜头，逐镜input/media/资产v1 SHA256 manifest，零收费调用、镜头缓存可重用 | P4 PR
- 2026-10-16 | GPT-6 | P/P5 (R3.3 Fake) | 接已批准假镜头的非人声时间槽WAV、已验SRT索引及纯合成配乐/混音MP4，0模型/US$0 | PR #129
- 2026-10-16 | GPT-6 | P/P6 (R4.4 Fake) | 一条CLI串P1–P5、11步JSON哈希缓存/指定重跑与合成MP4/QA，真实Provider0/US$0 | PR #130
- 2026-10-16 | GPT-6 | P/P-final (R4.4 Fake E2E) | 全帧Fake水印、原始合成梗概60秒CLI、11阶段验码、CI上传MP4工件；真实AI0/US$0，工件状态待CI确认 | PR #131
- 2026-10-16 | GPT-6 | F/F1 (R3.1 Omni) | 按 AMEND-006 固定毛毡玩偶出场角色描述、双复杂动作拆≤6秒，离线 Fake 合同测试；0 模型/US$0 | PR #135
- 2026-10-16 | GPT-6 | F/F2 (R4.4 Omni) | CLI provider=omni/style=felt_diorama，沿用十一阶段JSON与本机合成故事；原生音频、六镜Stub、哈希断点续跑与最坏10s费用守卫；真实模型调用0次 | PR #136
- 2026-10-16 | GPT-6 | F/F3 (R4.4 Omni) | 六镜360p手动工作流/真实费用与ffprobe报告、实际授权前硬挡USD2超支(见[需要所有者]#137)；真实API调用0、真实六镜未执行 | PR #138
- 2026-10-17 | GPT-6 | F3/R4.4 CI fix | Run #38922439695 ffmpeg缺失127，预算/Secret/付费镜头步骤全部跳过，收费0次；复用现有SHA256锁定FFmpeg工具，等待离线CI | PR #140
- 2026-10-17 | GPT-6 | F3/R4.4 budget fix | 仅#137单次USD2.50临时额度 + 日额USD5申报、一次性Issue占位阻止重复收费；估算非Google硬限额，尚未发送收费请求 | PR #141
- 2026-10-17 | GPT-6 | F3/R4.4 REAL | Omni 1.1 Flash真实6次调用，Actions #38931439653绿灯，六镜360×640/AAC、52.073秒整集Artifact #12058982177；视频输出费估USD1.75896721，**Google实际账单待核**；所有者审片Issue #142，预算Issue #137，禁重复付费 | doc PR #143
- 2026-10-17 | GPT-6 | G4/R4.2 | 所有者接受F3初版，不为#142轻微问题付费返工；沿用现有typed编剧请求添加中文分层钩子/冲突/反转/悬念 Prompt 版本、离线预览和 SHA 测试；0真实请求/US$0；G4退出及#137账单仍待核 | PR #145

- 2026-10-17 | GPT | G4/R4.1 | 3题×Sol/Luna/Flash×2离线题包、公共Prompt/Schema哈希与本地结构校验；22项相关测试通过，真实模型0/US$0，正式选型/凭据/文本预算待#146 | writer-comparison PR


- 2026-10-17 | GPT | G4/R4.1 | 两家纯wire适配/Screenplay/拒绝截断/思考用量收据/18任务USD2预检；62项相关离线测试通过，真实0次/US$0，Google全思考上界待核；按要求PR不合并 | execution-prep PR


- 2026-10-18 | GPT | G4/R4.1 | 所有者授权合并#148至635754c；补查官方Thinking指南确认Google max_output_tokens含思考并硬截断，更正旧阻断；输入上界/真实兼容性/凭据/收费授权仍待，0调用/US$0 | evidence correction PR

- 2026-10-18 | GPT | G4/R4.1 | 所有者授权首批3次文本测试US$2/不重试，新增隔离CLI+main手动workflow、完整输入计数/保守Google预留、Issue146一次性claim；76项相关测试通过，真实0次/US$0，待手动dispatch | writer-first3 PR

- 2026-10-18 | GPT | G4/R4.1 | Run39034195802计数预检HTTP400，report生成0/claim=false；修计数请求运行参数误传，补白名单/安全诊断/预检失败回归，79项相关测试通过；未重跑、未扩大额度 | count400 fix PR

- 2026-10-18 | GPT | G4/R4.1 | Run39035812309两份GPT校验通过、Flash400停；补Google白名单status/fieldViolations诊断，86离线测试通过，不重跑/不清claim；缓存写入补算总估算USD0.0540418非账单，真实400根因仍未知 | Google diagnostics PR

- 2026-10-18 | GPT | G4/R4.1 | 所有者选择基于GPT推进；Sol临时开发基线，导入既有OpenAI响应→资产scope校验→待审Screenplay/EpisodeDraft→既有人工commit；96离线测试，真实两份GPT仅离线回放，新调用0；正式选型未定 | GPT review integration PR

- 2026-10-18 | GPT | G4/R4.1 | GPT剧本→逐镜Omni请求纯离线准备，替代误用F3硬编码旧故事；109离线测试；真实Sol12镜/首3镜计划已准备，输出快照估算4.0551/1.013775(10秒/镜)，非总预算；新调用0、视频0 | video plan PR

- 2026-10-18 | GPT | G4/R4.1 | 准备固定Sol原稿s01-s03手动视频入口，129离线测试+compileall，SDK禁止重试，新claim不复用旧授权；估算USD1.42391275非上界，须owner单独接受风险和声明当日支出；本次真实调用0/视频0 | GPT video3 runner PR

- 2026-10-19 | GPT | G4/R4.4 | 复用成功3镜真实视频离线合成+QA15.060333s；134相关测试（新增5真实FFmpeg）；重复Run39126187434确认0生成；新调用0/费用0，原账单未知，60秒整集未完成 | GPT offline delivery PR

- 2026-10-19 | GPT | G4/R4.4 | 整集remaining9手动入口+固定原3镜hash复用+12镜合成QA；140本地离线测试/真实原3镜dry-run0调用；新9镜估算USD4.27173825需owner单次USD5风险例外，尚未收费执行，阶段未退出 | remaining9 completion PR
- 2026-10-19 | GPT-6 | G4/R4.4 | Run39130058487 复用3+新增9=12镜，60.177333秒H264/AAC、SHA256 f76daf30…，技术通过/内容审查不通过；s03/s09年龄漂移、s07分屏，音色/对白仍未核；真实prompt-only资产/声音QA缺口记录，实际9镜账单待核。本轮离线0新调用/US$0，不重试、不进入G5 | preview-review PR
- 2026-10-19 | GPT-6 | G4/R4.4 | 按所有者链路优先指示，新增已存在替换片的12镜单镜离线替换/其它11镜哈希保留/重拼接解码路径与合成媒体测试；不触发新模型、不复用一次性USD5确认、不改冻结区；独立付费单镜重生成与真实字幕仍待实现，PR CI验收前不得宣称完成 | G4 offline repair PR
- 2026-10-19 | GPT-6 | G4/R4.4 | 新增已完成真实12镜的离线字幕草稿后期桥梁：原源文件哈希/剧本校验→原生AAC/H264透传→估算SRT封装mov_text→字幕实际mux比对/FFmpeg解码→06-10阶段JSON；无ASR或新配乐、真人音色/字幕对齐/发布均未通过；新增真实FFmpeg合成素材测试，模型调用0次/API费用0 | offline postprocess PR
- 2026-10-19 | GPT-6 | G4/R4.4 | #160单镜离线回填和#161真实视频后期草稿字幕已合并；#162修Actions跨步PATH。自动真实原素材Run39133557599 success，Artifact12138992023/6.02MB；原音轨保留/草稿mov_text字幕+验收元数据落地；本轮重放真实API调用0/USD0，原视频账单仍未知。画面/对白/字幕对齐/发布未批准，G4约85%工程估算/未退出 | handoff PR
- 2026-10-19 | GPT-6 | G4/R4.4 documentation | 所有者要求以成熟开源为蓝本、不同模型按阶段交付；创建开发 Bible、固定 upstream 复用手册、W0-W8 交付/验收手册、多模型文件所有权与 handoff schema；只写文档/不改治理与生产模型，付费 API 0 次/USD0；现有真实12镜/离线字幕基线不重复。主线下一任务仍以 CURRENT 为准 | Development Bible PR
- 2026-10-19 | GPT-6 | G4/R4.4/W1 | ac28e5d基线按新Development Bible新增单镜失败审查→固定Prompt/旧片SHA计划→付费pending→已有片Fake收片→单镜离线回填→已有06–10后期/QA。保留旧原镜头receipt/费用，11镜不动；现有真实12镜只做s04代替s07的W1-FAKE零费用接口试验，尚待PR CI/Actions回执；0新视频API/0 USD，不重新使用旧USD5 | W1 PR
- 2026-10-19 | GPT-6 | G4/R4.4/W1 | #166 main681ad0f + #167 main1792fb3合并；CI/scope全绿。真实旧12镜Artifact在Run39137352545零费用模拟修s07（使用旧s04）成功，W1-FAKE Artifact12140422056，旧MP4 SHA f76daf30不变/新后期MP4 SHA de6d6235，另11镜原哈希保持；0供应商新调用/USD0。Technical pass；Content/ASR/Release均pending；标准证据包W1_EVIDENCE_20261019.md；下一包W2资产版本绑定，真实收费另行批准 | W1 handoff PR
- 2026-10-19 | GPT-6/M1 | G4/R4.4 W2 | PR #170: 只读确定性演员/场景/服装/说话者版本及 Prompt SHA manifest；复用原验证器/计划，17 类 fail-closed 与零网络测试，0 新模型调用/费用，W1/FFmpeg/发布保持不变；验收以 PR 最终 CI 和 Issue #169 handoff 回执为准 | PR #170
- 2026-10-19 | GPT-6 coordinator | G4/R4.4 | W2 PR#170 已合并 main 278763505b165e6a637a8acecc4b162121b3170a，7 checks success、Python 883 pass/171 skipped（3.11、3.13），Issue#169 关闭且标准证据包齐全；只接受零收费绑定，不推定真实生产资产 SHA、同脸同声/内容发布。W3 Issue#171 只做真实后期剩余增量：原12镜/W1修镜时间轴来源、可选授权音乐保留原生中文音轨；零新模型调用，不提前进入 G5 | W3 handoff docs PR
- 2026-10-19 | GPT-6/M3 | G4/R4.4/W3 | #173 6项CI全绿合并main4c16e12；原Writer/Omni真实12镜只读后期与W1旧s04→s07 FAKE修镜时间轴/父源SHA，Run39141517448 success、原Artifact12142320238/后Artifact12141772943；两版60.177333s 12镜、16 DRAFT cues、H264/AAC/mov_text、独立FFmpeg解码与媒体/SRT/render receipt SHA校验通过；W3.2缺授权WAV未启用，W2生产Manifest=null，0模型新调用/USD0，内容/ASR/发布全部pending；交W4审片，G4未退出 | W3 handoff docs PR
- 2026-10-19 | GPT-6/M4 | G4/R4.3/W4 | #175→PR #176：新增版本锁定12镜内容 QA、HMAC 人审导入、10项视觉/音频判据、历史 s03/s09/s07 负面回归、W1-FAKE父链严验、技术/内容/发布三门禁与 W5 交接。实际下载 W3 原版和Fake Artifact、全片H264/AAC/mov_text解码与媒体/SRT/09-10 SHA核对通过；独立离线初始报告各3镜历史需修/9镜未知，人审签字0。R4.3 Gemini预检和中文ASR not_run，新模型API0次/USD0；PR最终CI/合并回执见Issue #175，G4不退出 | W4 PR #176
- 2026-10-19 | GPT-6/M4 | G4/R4.3/W4 final | PR #176 全部6项CI success后自治squash合并 main40aedd50306919ea2b7451fc734030cbb9eb92e9，Python3.11/3.13各897 passed/176 skipped；实际W3两版Artifact本地哈希与完整解码通过，零新API、零重生成。W4.1/W4.2工程通过、12镜历史缺陷和unknown保持、内容/发布不通过、R4.3真实Gemini评分not_run；另开需所有者决策#177，下一包W5继续G4，G5未授权 | PR#176 / Issue#175
- 2026-10-19 | GPT-6/M5 | G4/R4.4/W5 | 基线main2cc91f54复核，#179从GitHub实际下载原Artifact12142320238/W1-FAKE12141772943，原样Git-blob核验W4 CLI+content_review并对两片真实媒体执行：report SHA e8a6218d4f26 / e1b2a69e4dc5；技术pass/内容fail/发布blocked，3需修/9未知/0人审、错误版本exit2；ffprobe 60.177333s、ffmpeg全解码成功；Gemini/ASR not_run、旧账单及人工时长unknown；新收费模型调用0/API USD0。W5结论NOT_READY，G4未退出，#177待Owner，G5禁止 | Issue #179 / G4_ACCEPTANCE_20261019.md
- 2026-10-19 | GPT-6/architecture | G4/R4.4/FND-00–01 | Owner 审完12镜未签字反馈后要求架构优先。源码调研 Toonflow/Huobao/waoowaoo/ViMax/Jellyfish/ArcReel/OpenMontage/HyperFrames；#181/FND-00 PR#182 六CI绿合并 cc5e5f8；FND-01 PR#184 六CI绿合并 main75774051751b6f33a01f63e41873dca83f908658，纯离线多视图/场景/道具/ShotGraph plan，local11 tests pass，无真实Provider参考图接线、无收费调用/真实素材上传。下一 #185 FND-02 offline Provider media admission；旧 W5 G4 NOT_READY，#177 Owner评估保持 open，G5禁止 | Issues #181/#183/#185 PRs #182/#184
- 2026-10-19 | GPT-6/architecture | G4/R4.4 FND-02/03 merged | Owner授权先完成全基础框架、后统一测试。#187 新增 signed asset/media admission、PNG字节SHA/RGB核验、首末帧同场景继承与审批门禁、Omni image+text dry-run、12-shot CLI Fake replay，Python3.11/3.13各922 passed/176 skipped、scope/offline/Fake/libSQL合计6/6全绿，合并main cc66d82517c895c794d889ecd2b572d374631d00，零模型请求/USD0，不外发素材、不改W1–W5。#185关闭。下一 #188 需所有者权利/隐私/费用/AMEND-006授权后的2–3镜真A/B，旧#177 Gemini/ASR保持未授权，G4 NOT_READY、G5禁止 | PR#187 #185 #188
- 2026-10-20 | GPT-6/CityDiscount Pilot 01 | G4/R4.4 first creative target | Owner将第一新生成视频改为 CityDiscount 9:16 60秒品牌宣传片。#190/PR#191六CI绿合并 a7f5a862a55c58649d951a2cb2e47a7a77cc7702；Python3.11/3.13各932 passed/176 skipped。12×5秒分镜JSON/品牌brief/隔离零演员promo_motion_graphics计划器/防虚构价格与App功能门禁测试已交付，无MP4/外部图片/收费模型调用。真实live-provider+FFmpeg接线另行受控，#188已更新为CityDiscount真A/B授权，AMEND-006/正式阶段更改需Owner亲自治理。#177独立未授权，G4 NOT_READY，G5禁止 | Issue#190 PR#191 Issue#188
- 2026-10-20 | GPT-6/R4.4 generic film factory | Owner确认GitHub上传版 mascot_character_sheet_v1.png 为新版唯一基准 Git blob a5665b80a8484d5124fb874576ff40372f5a7c06，新SHA256待可信二进制读取；Logo匹配。#193 Draft 仅Pilot示例元信息，#194/PR#195通用 StoryBible-FakeTextProvider-Screenplay-EpisodeDraft-VideoPlan 薄接线和两组无关剧情测试；真实模型0，API费USD0，发布/G4退出禁止。GitHub Actions #193/#195 全部六检查 runner启动失败、无步骤/无日志，不能合并；阻塞已建 #196，停止无目的重跑 | PR#193 PR#195 Issue#194 Issue#196
- 2026-10-20 | GPT-6/G4 R4.4 refactor | Owner选 GitHub 新版小羊 v1 原blob a5665b80...；转为独立通用资产PR#197（复用两份Owner上传Git对象、PNG+Git blob字节验证）及无关剧本可复用StoryBible→Screenplay→video-plan PR#195；CityDiscount-only preflight PR#193未合并关闭，避免双轨。CI#196三个PR运行前全部失败/取消，runner_name空/steps空、日志404，annotations_count=2不可经connector读取，待Owner只读gh api annotations；无真实模型/新增费用，G4 NOT_READY | #193 #195 #196 #197
- 2026-10-20 | GPT-6/G4 R4.4 公开仓库后开发恢复 | Owner将ai-short-drama-factory设Public，Private 3000/3000免费Actions分钟及$0过额阻塞解除；#196关闭。PR#197原Git blob小羊新V1/Logo SHA字节核验（6绿）并入e3d24b7e；PR#195双不同题材通用 StoryBible→Screenplay计划（6绿）并入36176056；PR#199离线SQLite/API/Fake Worker/FFmpeg双项目集成测试（6绿，但普通Python测试因缺FFmpeg跳过真实渲染用例）并入3349a54a；PR#200把该用例强制纳入已有offline-video步骤，真实FFmpeg job 2 passed/0 skipped、六CI全绿，main 60b2daaf75de774f051b72a40e5a5d410d06fc1e。两个题材已产出Fake H264/AAC/字幕技术MP4并查hash/cache，**不是**真实Omni影像或TTS；API收费0，G4 NOT_READY。下一唯一通用图像/角色版本与模型Fake准入 #201，公开仓库敏感历史与影片需持续隐私注意 | #195/#197/#199/#200 #198 #201
- 2026-10-21 | GPT-6/G4 R4.4 owner真实小羊十图归档 | Owner在Mac本地整理并SHA256验证4摄影视角+6表情动作共10张RGBA PNG后push分支235783c；#204修RGB白底透明合成，#205严格多角度来源SHA映射，#206锁定10张本地清单；#207上传真实PNG字节并增强仓库CI全量 SHA256/尺寸/PNG解码/RGB规范化/FND-02离线门禁，Python3.11/3.13、Scope、libSQL local、Fake artifact、offline-video六绿后合并aabb1d7e。没有人工角度正确性证明/版权外传批准/模型提交权限/真实Omni调用，新增费用0，G4 NOT_READY。下一步#201严格人工视角及权利审查，再做Fake媒体授权演练 | #201 #204 #205 #206 #207
- 2026-10-21 | GPT-6/G4 R4.4 reviewed screenplay -> FND offline gate | #209 将已审 Screenplay 镜头顺序/演员/场景及依赖哈希与现有 W2/FND-01/02/03 Fake 整集演练接线；新增不同 Series 的合成 RGB 图片、临时测试 HMAC grant、首尾帧继承和错片/串授/篡改负例；全程没有对外媒体提交/付费模型/小羊视角或权利审批。CI/合并状态见 #209，G4 NOT_READY；下一步仍是 #201 Owner 视觉/权利审批门。 | PR #209 / Issue #201
- 2026-10-21 | GPT-6/G4 R4.4 actual PNG review | 在既有 local_reference_views 新增真正读取 Owner 10 张 PNG 的四视角→ W2 角色版本/镜头引用待审核凭据，依旧拒绝权限自动升级、伪造视角；第二无关 Series 复用相同逻辑。对真实外传/权利/场景图保持 fail closed，Owner #210 待决。PR CI / merge 以 GitHub 为准，USD0，G4 NOT_READY。 | PR #211（如编号实际不同以 PR 链接为准）/ #201 / #210
- 2026-10-21 | GPT-6/G4 R4.4 EpisodeDraft 真实引用接线 | 补齐 EpisodeDraft.reference_asset_ids 对应 W2 角色/场景/道具逐镜确定性引用，绑定 EpisodeDraft SHA 到 FND 视觉计划/HMAC 与 Fake 凭据；两不同 Series 离线正/负例。所有者真实图片仍无外传批准；验收 CI/合并见 PR #212，G4 NOT_READY，USD0。 | #201 #210 PR #212
- 2026-10-21 | GPT-6 | G4/R4.4 | PR #213：扩展既有图片人审候选链，选填真实 SQLite DB 时在访问图片前核对 W2 actor/scene pin 的 id/kind/version/specification_sha256；以实际 W2 builder + SQLite + 合成 PNG 做离线测试，旧无 DB 收据标注未验证。CI/合并状态看 PR，0外部模型/0费用，#210仍需Owner。 | #213 #201 #210
- 2026-10-21 | GPT-6 | G4/R4.4 城市品牌首片故事 | 改写 CityDiscount 原 12镜/60s 创意 proposal 为《小羊差点买错了》完整冲动→卡片翻面反转→审条件→不冲动决定→品牌收尾；逐镜摄影视角/动作/连续性/短旁白/字幕，复用既有 promo planner，制作单 docs/CITYDISCOUNT_FIRST_FILM_STORY.md；真实音视频/审批/图片外传仍未完成，0付费/USD0，G4 NOT_READY。CI/合并按 PR #214 GitHub 证据。 | PR #214 / #188 / #201 / #210
- 2026-10-21 | GPT-6 | G4/R4.4 CityDiscount Owner 正式寻宝宣传片 | 接收 Owner 12镜60秒剧本《把奥克兰的好折扣，挖到你身边》；在旧 JSON 原路径创意修订 3 完整替换过时剧情，补逐镜真实旁白/画面/音效/奥克兰地标/家庭场景；模型前资产约束 s01/s11/s12 CD 金币，s02/s08/s12 Logo，片尾完整3秒，真实优惠只示意；更新既有 planner 和人读执行单，独立版权/家庭图/金币标准源未解除；无新付费、G4 NOT_READY，PR #215 CI/merge 以 GitHub 实证为准。 | #188 #210 #201 PR #215
- 2026-10-21 | GPT-6 | G4/R4.4 Omni 真实参考图接口 | 官方 Gemini Omni 文档确认支持 image/png + text；修复既有真实 Google adapter 的 FND PNG/文字单镜头最小接线，保留 legacy 未审核原始 Path 的明确拒绝；必须人工批准权利/隐私外传+账号条款/预算并实时核对哈希，无自动启动/无外部请求。与真小羊/家庭/金币素材权利无关的合成图片测试一律离线。0模型调用，0USD。PR #216 CI/合并以GitHub实际状态为准；#188/#210仍阻断真实上线。 | PR #216 / #188 / #210
- 2026-10-21 | GPT-6 | G4/R4.4 首次 CityDiscount 真实视频入口 | 利用 Owner s03 原剧本制作**只含毛毡奥克兰地标/无吉祥物无品牌资产**的独立真实 Omni 360p 环境空镜试拍，新增手动 Actions workflow + 零费预检脚本，严格 1次调用、无自动重试、人工当日账单输入+USD2预留/NZ日USD5、输出实际MP4 FFprobe+回执；PR #217 CI结果及合并状态以 GitHub 为准。未手动付费运行前**不得宣称已有真实小羊/城市AI素材**。 | #188 #210 #201 PR #217
- 2026-10-21 | GPT-6 | G4/R4.4 CityDiscount 12镜60s原素材无费分镜升级 | Owner 已通过真实 s03 毛毡城市风格，Google 费用仍未对账故不做付费新调用；复用已生成 Omni s03 MP4 SHA+仓库10角色PNG/正式Logo源，Pillow/FFmpeg 本地合成60秒12镜动态预演，有真实吉祥物局部原图、品牌结尾和准确旁白*文字*，其余未完成场景均明确非 AI 连续运动；产出 Actions artifact，不提交视频二进制。不声称真实全片生成、中文TTS或金币源已授权，G4 NOT_READY。PR #218。 | #188 #210 PR #218
- 2026-10-21 | GPT-6 | G4/R4.4 CityDiscount 真人配音前置节奏 | 利用 Owner 原始12句VO、已存在60秒Logo+吉祥物小羊原图预演与s03真实AI城市视频，增本地 espeak Mandarin *机器人草稿旁白*，从每镜+0.2s 入点、自动速度拟合不截断并降临时音乐，生成可听60秒音轨预演和FFmpeg原视频无损copy的MP4；不冒充自然中文音色，0新Google/云TTS调用，Google实际账单未知，G4 NOT_READY。PR #219 状态须看最新CI和合并证据。 | #188 #210 PR #219
- 2026-10-21 | GPT-6 | G4/R4.4 CityDiscount Owner新版故事与首版尺寸 | 统一 1080×1440 portrait 3:4，真实原版小吉祥羊15–22%画面高度、所有场景/家庭/道具毛毡；三个真实抓取类型(MON_SUPERMARKET、GrabOne Auckland restaurants、Cheapies NZ)各挖2铲后出1枚CD金币，城中满载疲惫奔跑、送家庭笑着跑走；新 v2 JSON+现有 planner校验+正式逐镜说明，rev3仍存档；音乐优先禁 espeak，新账单未知不付费；PR/CI见本轮结果，G4 NOT_READY。 | #188 PR TBD
- 2026-10-21 | GPT-6 | G4/R4.4 CityDiscount 指定镜头小羊与Logo真素材复用 | Owner 仅要 s02/s05/s06/s07 重点视觉+ s12 Logo，不再加站；只用仓库原版 PNG front/three_quarter 等比例贴图不改眼睛，所有图1080×1440，s12真实 SHA 官方Logo；新增离线审片板+GitHub Actions下载产物，费用0/无外传。仍为静态制作板，实际动态羊未做、旧账单 UNKNOWN，G4 NOT_READY。PR #222 本轮真实 CI/合并状态以GitHub回执为准。 | #188 #210 PR #222
- 2026-10-21 | GPT-6 | G4/R4.4 s02 REAL Omni手动试拍入口 | Owner确权+Google小羊外传，但账单/保留条款仍需单独手动确认；复用FND-02临时单镜签名与已有真实SDK，PNG source SHA→只发一次Omni9:16源视频→FFmpeg不拉伸主体变成1080×1440 3:4，真 MP4/artifact/receipt；付费只在Run workflow明确同意且成本核验后触发，CI不付费、不冒充已生成。详 docs/CITYDISCOUNT_S02_REAL_TRIAL.md。G4 NOT_READY，s05仍未开发。 | #188 PR TBD
- 2026-10-22 | GPT-6 | G4/R4.4真实Shot05 360p单镜试拍入口 | owner s02动作可接受，小成本原生360p优先；复用成功 s02 PNG SHA+FND签名SDK+3:4转制，定点s05两下铲土后一金币，保持大眼小羊。PREVIEW_ONLY零费UNKNOWN支持；paid要核对Google账单、条款，限额USD2/次USD5/NZ日；真实s05视频NOT_RUN直到Owner workflow_dispatch。仍不发布/G5暂停。 | #188 docs/CITYDISCOUNT_S05_REAL_TRIAL.md
- 2026-10-22 | GPT-6 | G4/R4.4 实测 s05 红灯复核 | Owner Actions #39596195021 真模型1次成功且生成真实MP4；错误仅workflow查找/上传了不存在的 s05_owner_...而真实脚本写 s05_1080x...；从GH Artifact 12343403535还原源MP4并离线重做3:4，0新付费；提交最小三处文件名修复和CI防回归。模型门店乱码牌、未官方CD金币字仍待内容验收；Google当前实际扣费UNKNOWN，G4未退出。 | #188 PR TBD
- 2026-10-22 | GPT-6 | G4/R4.4转回主系统已有真实镜头通用接入 | CityDiscount只是Pilot，不继续单镜返工/发新费用。重用EpisodeDraft、media_ingest、W3 render/W4 QA，新增零费验 SHA/receipt/时长/重复/缺镜头桥梁，任意两个题材复用，无私密路径发布，不认证Google账单或发布许可。 | docs/G4_EXISTING_REAL_SHOT_HANDOFF.md ; PR TBD
- 2026-10-22 | GPT-6 | G4/R4.4通用已有真实镜头→W3/W4物理端到端回归 | 从已合并#226离线验证入口出发，新CI用已存在的真实FastAPI/SQLite人工审批门、FFmpeg+W4技术审查，同一源视频缓存、不重复模型调用；两镜全真/部分缺失与失败前拒绝路径，强制offline-video不skip。CityDiscount仅Pilot、不修单镜、不花新费用。 | PR TBD
- 2026-10-22 | GPT-6 | G4/R4.4 已批准真实镜头整集技术预览一命令 | 实际旧W3/W4接口+既有SQLite审批+MP4/SHA/receipt，严格all-real默认、partial只限带占位草稿；0模型调用、0新费用、不动W1–W5、CI强制FFmpeg；本地SQLite状态会写入，非只读，正式使用需运营者批准及备份。 | docs/G4_EXISTING_EPISODE_OFFLINE_ONE_COMMAND.md PR TBD
- 2026-10-22 | GPT-6 | G4/R4.4主流水线“真正只读”的整集覆盖预检 | 在现有PR#228 CLI增加--preflight-only，SQLite mode=ro+query_only，无初始化迁移、无FFmpeg/Provider/SQLite写；列出0/部分/齐全真实镜头数+SHA/receipt核验、缺失ID及下一操作，非法源严拒。原真实成片模式仍明确会写技术状态；CityDiscount单镜和Google付费调用暂停。CI强制离线FFmpeg回归。 | docs/G4_EXISTING_EPISODE_OFFLINE_ONE_COMMAND.md PR TBD
- 2026-10-22 | GPT-6 | G4/W5 真实W3历史原版及W1-FAKE→已有W4 CLI回放门禁 | 取回Run39141517448的原版/FAKE，SHA/FFprobe真实验证；新增零付费GitHub Actions验收workflow和静态scope，运行现有W4 CLI，预期content=fail/release=blocked，不能凭现有单测假称真人审片。待实际 workflow 结果，G4 NOT_READY、G5停。 | docs/handoff/W5_REAL_W4_ARTIFACT_REPLAY_20261022.md PR TBD
- 2026-10-22 | GPT-6 | G4/W5 真实 GitHub W4 回放证据与唯一 W5 接受清单一致性门禁 | #230合并，两个真实60.177秒W4直接审片技术pass/内容fail。最新小增量在同一workflow对既有G4_ACCEPTANCE_20261019.json验SHA、NOT_READY、0人审、供应商账单UNKNOWN、R4.3未运行；不另造审计系统，不触碰生产SQLite、0新增模型调用。 | docs/handoff/W5_REAL_W4_ARTIFACT_REPLAY_20261022.md PR pending
- 2026-10-22 | GPT-6 | G4/R4.4 | rev4 已存在 s02/s05 真实小羊 + 旧 s03 城市场景 → 12×5s 1080×1440 技术预览/显式缺镜头/来源 SHA回执；无新模型调用，不算全真成片，历史账单UNKNOWN，专项GitHub实FFmpeg CI待验 | PR #233
- 2026-10-22 | GPT-6 | G4/R4.4 | Owner rev5: 12镜真实空间缩放入街区、追踪小羊穿街再缩地球，3.4秒官方Logo＋“都市折扣🌟，您的省钱助手小羊薅薅。”；新增5秒纯本地2D毛毡地球Logo示意视频和回执，真实连续镜头not_verified、付费0，G4 NOT_READY | PR #234
- 2026-10-22 | GPT-6 | G4/R4.4 | Owner今日要求实际出60秒rev5：锁定已有rev4真实2镜与rev5真实官方片尾视频SHA，本地2D奥克兰城市zoom进街区、跟羊移动/zoom out→地球，加入临时自制音效音乐，输出60s H264/AAC且保留NOT_FINAL；无Google调用/额外费用，真实3D相机及商业发布仍未验证 | rev5-motion PR
- 2026-10-22 | GPT-6 | G4/R4.4 | Owner反馈#235仍是平面；新增世界XYZ 3D体积小城市、真实投影相机转角/高度缩放、街道走向和原版小羊PNG按深度遮挡，制作新60秒零新付费预演；真AI动态仍仅s02/s05，非最终商业3D渲染 | PR #236
- 2026-10-22 | GPT-6 | G4/R4.4 | 新3D城市小羊动效：地面道路网格L型连续路径、原版PNG轻跳/前后脚/地面阴影/转弯、两铲后示意币，镜头6参数连续。原真实s02/s05不动，实FFmpeg重新编60s；纯本地无新增付费；非正式rigged三维小羊 | PR #237
- 2026-10-22 | GPT-6 | G4/R4.4 | 在已有真实XYZ毛毡城市上新增世界空间低多边形羊身/4条步态腿与Owner原图脸部贴片，s11末帧经零付费本地动效缩入s12旧地球再到官方Logo；真实s02/s05保留、完整AI真12镜仍NOT_READY；专项60秒GitHub实片及全CI待验 | 新PR
- 2026-10-22 | GPT-6 | G4/R4.4 | 首次实际下载最新60秒真MP4抽帧审片，发现s01/s11家庭不清、羊被楼遮/真AI与画布风格落差；添加3个占位毛毡家庭模型＋近景剖面楼顶与真实MP4 SHA锁定12镜Contact Sheet，人审仍待定。无付费新增。 | 新视觉QA PR
- 2026-10-22 | GPT-6 | G4/R4.4 | 停止以积木插图冒充真实电影级质感；独立下载SHA复验s02/s05原始Omni和旧s03环境片，保存用户私密证据ZIP与最新60秒样片；新增9个真实毛毡视频缺失镜头的逐镜prompt/跨镜接续/发布及费用硬边界，账单与新Google图片外传许可仍待Owner #188/#210，0新付费调用，G4 NOT_READY | rev5-genuine-footage pack PR
- 2026-10-22 | GPT-6 | G4/R4.4 | 采用真实旧Omni s02(5s)+s05(5s)+旧官方Logo(5s)做15s原版羊画质基准；本地真MP4 SHA与输入SHA核验，原9:16居中无拉伸到3:4，同源两侧虚化，声道AAC静音；不造新羊/不伪称完成60秒；专项GitHub工作流上传质量基准供九镜未来真实生成比对，外传/付费均NOT_AUTHORIZED | 15s looklock PR
- 2026-10-22 | GPT-6 | G4/R4.4 | 实际逐帧审查s02/s05真Omni，发现s05虚构英文店名Checlues；生成局部空白羊毛毡招牌5秒视频并验证120帧、小羊区域无显著变化，保留原SHA和音轨；专项CI及原片证据待合并，0新付费/素材外传 | s05 sign redaction
