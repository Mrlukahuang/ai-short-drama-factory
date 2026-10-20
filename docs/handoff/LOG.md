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
