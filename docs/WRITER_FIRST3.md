# G4/R4.1 首批3次真实文本兼容性测试

所有者2026-10-18 NZT已授权：先Sol/Luna/Flash各1次，计入18份；总预算≤US$2，不自动重试。
本PR提供执行工具，不代表已经运行。正式主备选型不变；不生成视频，不批准剧本。

## 运行入口

GitHub Actions → Writer first3 text compatibility (manual, USD2 total) → Run workflow。
只允许main、仓库所有者、workflow_dispatch、run_attempt=1。
- confirmation：RUN_WRITER_FIRST3_USD2
- reported_spend_today_usd：已核实的今天（Pacific/Auckland）全部API花费；若今天没有则填0。

使用已有仓库Secrets OPENAI_API_KEY、GEMINI_API_KEY；不在页面或日志粘贴值。
当前连接器没有dispatch接口；需要所有者在Actions手动点一次，或另行明确允许浏览器操作。
不通过push/PR事件自动生成收费任务，不把测试密钥带入普通CI。

## 执行顺序与预算

1. 无密钥的离线测试；只有专门的手动步骤才读Secrets。
2. OpenAI对两份**完整拟发送payload**调用 /v1/responses/input_tokens；
   不根据字符数估算Schema/消息封装。计数缺失或>217600则停止。
3. OpenAI预留输入至少10000或计数×1.25，并对输入费率再留25%余量；
   最大计费输出12000（包含思考）。
4. Google暂以官方最大输入容量1048576作保守上界，输出12000含思考。
   因此Google单次预算预留约US$0.831432，远高于预期实际花费；这是上界，不是报价。
5. 全部三次预留相加必须≤US$2，已报今日花费+预留必须≤US$5，价格快照过期拒绝。
   全局Standard、无工具、未缓存目录价假设；不宣称税费/地区附加费用或实际账单已受供应商封顶。
6. Issue #146写一次性claim（分页检查+串行concurrency），先占位再请求；
   已占位的后续运行一律拒绝，即使首次超时/失败。
7. 顺序各尝试一次；拒绝、截断、响应不兼容、未知用量、超上界、非法Screenplay立即停止。
   已发出但超时的请求保留为不明确尝试，不自动重发。
8. 首批最多3次，均使用misunderstanding题、复本1的固定输入，计入原18份。
   剩余15份不会由本工具启动，后续先审核首批及累计费用/预算。

## 输出

private Actions artifact：report.json、原始provider响应、通过结构校验的Screenplay。
report区分generation_attempts、validated_draft、halted、unknown usage、目录价估算与实际账单。
请求前先保存in_flight记录；所有失败也上传已产生的报告，不输出认证header/密钥/错误body。
有效结构只是待人工审阅剧本，不代表中文质量、连续性、对白时长或生产审批通过。
原纯离线writer_execution_prep.execute_paid依然固定拒绝；新网络入口只在独立CLI --paid中。

## 验证

本地部分检出76项相关测试通过（网络全禁用），模拟验证成功三次、占位顺序、既有claim、
缺密钥、非owner/PR/非main/重跑拒绝、超时/截断/缺用量/超限停下。
完整全仓测试由PR CI验证；尚未验证真实凭据、endpoint/schema或真实响应。

官方依据：
- https://developers.openai.com/api/docs/guides/token-counting （完整payload精确计数）
- https://developers.openai.com/api/docs/guides/reasoning （输出cap含生成思考）
- https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash （输入上限1048576）
- https://ai.google.dev/gemini-api/docs/thinking.md （输出cap含思考且硬截断）


## 首次运行诊断与修复（2026-10-18 NZT）

Run https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/39034195802
在OpenAI输入计数预检HTTP400停止。Artifact12101851150/report.json记录：generation_attempts=0、
paid_reservation_claimed=false、http_status=400；Issue146没有首批claim，未进入剧本生成。
旧诊断未保存供应商error.code/param，因此不能声称已经排除账号/模型访问等其他400原因。

已核对官方SDK InputTokenCountParams（blob a0f0963444b428124f2a1462218d43b9628f2245）：
https://github.com/openai/openai-python/blob/main/src/openai/types/responses/input_token_count_params.py
计数请求接受model/input/reasoning/text，不接受原代码附带的store/stream/service_tier/max_output_tokens。
修复只移除计数请求的运行选项，保留完整输入、Schema及reasoning；真正的生成请求不变。
补参数白名单、计数400在claim之前停止、诊断不复制私密报错文本的回归测试。
新报告仅记录白名单error.code/param、失败stage和model，不输出error.message/密钥/任意响应正文。

本地部分检出79项相关测试通过；真实修复效果仍需新一次workflow_dispatch验证。
不要点旧Run的Re-run：attempt2会被拒绝。修复合并后新点Run workflow，仍用原确认词及已核实当日花费。
本次没有重发计数/生成请求，没有清除或更换占位，没有扩大额度或自动重试权限。
