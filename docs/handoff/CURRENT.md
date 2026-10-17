# 当前交接状态（每次结束更新）

## G4/R4.1：Google HTTP400诊断（2026-10-18 NZT）

- main基线9e94f8f；真实Run39035812309（attempt1）已发起3次生成尝试，Sol与Luna各1份剧本结构校验通过；Flash HTTP400停止，未获得剧本。产物12102675304保留两份GPT结果。
- 两份OpenAI原始usage含cache_write_tokens=1064。按缓存写入1.25倍输入价补算合计估算USD0.0540418，非实际账单；旧report估算USD0.0534832未包含缓存写入差额。计费模块缓存细分尚待修正，不把旧数作为准确账单。
- 一次性claim已消耗：不清除、不重跑整批、不重复生成GPT；余下15任务未放行。本次修复未调用任何收费API。
- 已核对既有视频Provider同样使用interactions.create；官方REST端点与当前/v1beta/interactions一致。视频成功不能证明Flash+严格schema成功；目前没有端点写错证据，也没有证据认定key无效。
- 本次仅修复诊断：保留Google白名单status和google.rpc.BadRequest精确白名单字段路径；不保存message/description/未知路径/凭据。新增模拟Google400、保留两份成功稿且不重试的回归；86项相关离线测试通过。
- 限制：旧400响应正文未保存，无法从现有artifact恢复根因；若Google只返回message，安全字段仍可能为空。本修复不等于已修复400，也未验证真实兼容性。
- 下一步：审查诊断PR；另行准备明确授权、预算约束下的Gemini单任务方案，保留现有claim。当前没有新增收费调用或自动续跑入口，正式主备选型未定。
- TokenUpperBound.verified仍是外部可信证据断言，不是模块自行验证或账单封顶。Google max_output_tokens含思考上界依据官方文档，不是实测账单保证；完整18任务须另做执行前检查。

## 前次交接（历史，不代表最新真实调用状态）

# 当前交接状态（每个 Agent 结束工作时必须更新）

> 只保留**最新**状态。历史交接追加到 `docs/handoff/LOG.md` 末尾（每条 ≤ 10 行）。

## 当前阶段

**AMEND-006：F3 六镜真实样片已完成且所有者接受作为第一版视觉方向基线；继续 G4 MVP（未进入 G5）**。F3 [Run #38931439653](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38931439653) 真实6镜 360×640，约52.07秒；Artifact #12058982177。2026-10-17 所有者表示「直接先往下走，问题不大」，[Issue #142](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/142) 已记录「不为轻微连续性问题返工」并按原型验收结束。**这不是商用发行验收**：中文对白真实性/字幕转写对齐仍需另验，Google [#137](https://github.com/Mrlukahuang/ai-short-drama-factory/issues/137) 实际账单仍未取得（只有视频输出 US$1.75896721 估算）。F3 的一次性付费权限已消费，禁止重跑。

### 最新运行诊断（2026-10-18 NZT）

- 首批Run39034195802在OpenAI输入计数预检HTTP400停止；artifact12101851150记录生成尝试0、claim=false。
- Issue146无首批claim；未进入真实剧本生成，账单未独立核实。
- 已发现并修复计数请求误带store/stream/service_tier/max_output_tokens；保留完整Schema与reasoning。
- 补回归测试，本地部分检出79项相关测试通过。供应商400具体code/param旧报告未保留，账号/模型访问尚不能排除。
- 修复合并后需新建manual Run（不是旧任务Re-run）；不自动重试、不扩大US$2原额度。

### 当前 Req

**Stage: G4 / Req: R4.1 / 交付物：所有者已授权的首批3次文本兼容性手动工作流。**

- #148离线适配已合并635754c；#149官方Google输出cap证据更正已合并05aae88。
- 所有者2026-10-18 NZT授权首批Sol/Luna/Flash各1次，计入18份，总US$2，不自动重试；
  随后表示凭据已准备并要求继续。不读取或展示密钥值。
- scripts/run_writer_pilot.py独立网络CLI，默认仍只输出离线计划；
  .github/workflows/writer-first3.yml只允许owner在main手动触发attempt1。
- OpenAI完整payload token计数；Google以整个官方输入容量作保守上界；
  三次预留≤US$2且当日累计≤US$5，Issue146一次性claim在生成前写入，失败不释放、不重试。
- 新流程只执行首批3次，不自动启动剩余15份，不变更正式主备，不生成视频。
- 本地部分检出76项相关测试通过、compileall通过；全仓结果以PR CI为准。
- 本次提交时真实模型0次、API US$0；凭据与真实endpoint/schema兼容仍待首次运行验证。
- 详见 docs/WRITER_FIRST3.md。连接器没有dispatch接口，合并后需所有者点击Actions Run workflow。

### 边界与下一步

1. TokenUpperBound.verified仍是外部证据断言，不是模块自行证明或供应商账单封顶。
2. Google官方已明确max_output_tokens包含thought并硬截断；不能再把缺此文档作阻断。
3. 真实兼容性尚未验证；首批遇拒绝/截断/未知用量/超限即停止，不重跑。
4. 首批全部成功后仍需人工盲评；原始响应与目录价估算不是实际账单。
5. F3不返工；#137实际账单待核；G4未退出，不进入G5。

## 最近一次交接

- 2026-10-18 NZT | GPT | 准备首批3次owner-gated手动文本工作流，
  原18份中的misunderstanding复本1；0真实调用/US$0。下一步手动运行并检查artifact。
