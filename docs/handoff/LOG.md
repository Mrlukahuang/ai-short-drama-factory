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
