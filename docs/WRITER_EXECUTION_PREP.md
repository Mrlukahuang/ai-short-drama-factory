# G4/R4.1 真实编剧执行前适配（OFFLINE ONLY）

当前分支基于 main c202d622（#147），只做无密钥准备。
不修改治理、正式模型注册表、数据库、审核状态、视频链路或现有Fake默认行为。
真实文本/视频调用0次，API费用US$0。用户要求：提交PR，先不合并。

## 已实现

- pipeline/writer_execution_prep.py：纯请求构造、响应解析、Screenplay结果、用量收据和18任务预算预检。
- OpenAI Responses 与 Google Gemini Developer Interactions 分别构造固定端点、
  medium思考、显式标准服务档位、关闭store/stream的文本JSON请求。不包含工具/图片/视频。
- 两家使用相同语义Prompt与闭合Schema：去掉default/title、所有字段必填、可空字段保持nullable、
  additionalProperties=false；保留原有约束。Schema实际服务端兼容仍未实测。
- WriterResult返回Screenplay或明确失败状态，不伪装成旧TextProvider.generate返回的ScriptOutline。
  现有text_api与FakeTextProvider不变；未来生产接入须显式采用Screenplay结果，不能自动审批。
- OpenAI原生refusal单独标记；两家incomplete标记truncated，不接纳看似合法的部分JSON。
  失败、不认识的响应形状、非文本/工具、非法剧本均不交付Screenplay，也不自动续写或重试。
- Google当前Interactions文档的steps/model_output/content被显式解析；非JSON拒绝文案被拒为
  invalid_screenplay，failed/errors归provider_failed，不猜测未验证的安全错误码。
- Pydantic严格校验及闭合字段检查后，核对请求身份、角色/场景、精确目标时长、
  每镜3–10秒、非空钩子/悬念/连续性。自然语言动作可行性与连续性仍需人工。

## 可运行的无网络预览

```bash
PYTHONPATH=src python scripts/prepare_writer_comparison.py --wire-requests --out /tmp/writer-wire.json
PYTHONPATH=src python -m pytest -q tests/test_writer_execution_prep.py tests/test_writer_comparison.py tests/test_drama_writer_prompt.py
```

导出18个待授权payload和精确请求指纹，不读环境变量或密钥。
每个请求仍标记missing_verified_evidence。execute_paid即便传authorized=True也固定拒绝：
仓库本次没有HTTP/SDK发送实现，没有可收费工作流，不存在开启收费的配置开关。

## 用量与费用口径

- OpenAI output_tokens包含reasoning_tokens：可见输出=总输出-思考，不能重复加算。
- Google total_output_tokens与total_thought_tokens分开：计费输出按二者相加；
  工具用量非0则不按纯文本价格估算。
- 缺失/非法用量是unknown，不是0。拒绝和截断同样保留已报告用量。
- 收据带请求/响应SHA256、响应ID、是否模拟；不复制供应商错误消息或思考正文。
  estimated_usd只是标准未缓存目录价估算，不是实扣账单。
- 价格快照2026-10-17，强制2026-10-31过期；超过272k输入拒绝当前价格假设。
  仅支持本轮三个候选。不使用折扣，不包括税费/地区/额外缓存写入等附加费用；
  未来真实执行需确认账号计费条件，不能凭此目录价估算宣称实际账单封顶。

## 18任务硬预检的精确边界

preflight_batch对完整18任务一次性预留最坏费用，Decimal计算，累计已花费+预留≤US$2才通过。
拒绝少任务/重复ID、不同题包、模型混用、不公平的跨模型输入、变化的复本、
修改过的payload、过期价格、负/布尔token、请求指纹不符和缺少可信上界证据。
这个函数的硬限制是**指定证据与标准费率假设下的执行前算术门禁**，不是供应商扣款限额。

TokenUpperBound默认verified=False；输入上界须包含完整Prompt/Schema/消息封装，
输出上界须包含全部计费思考量。证据必须绑定精确请求指纹；verified=True是调用方的
可信断言，不是本模块自行测出的token数。测试中仅使用明确标为SIMULATED的证据。
不把字符数/最终JSON长度/平均token当作可信上界。

重要的未解限制：Google Interactions官方max_output_tokens说明只写
“The maximum number of tokens to include in the response”，并单列thought用量。
本轮资料没有证明此参数能封住全部计费thought。因此本次**不生成真实已验证Google上界**；
在真实执行前需官方可复核的上界或其他供应商硬限额，否则该批必须保持阻断。
OpenAI文档说明max_output_tokens涵盖生成过程中达到的限制，且可能只思考就耗尽额度。

reconcile_usage遇到缺用量或实际超上界时标记halt_required并保留全部预留，不因失败假定免费，
不自动退回预算或重试。它是纯审计数据转换，不是新建持久化/事务/恢复系统。
真实发送、跨运行预算防重、授权及同日预算对账仍未接线，当前execution_authorized永远False。

## 验证与待办

本地connector部分检出中的62项相关测试通过（不是全仓测试声明），compileall通过；
完整仓库验证以PR CI为准。模拟覆盖两家成功、拒绝、截断、失败、缺用量、错误JSON、
跨剧引用、未知说话人、严格类型、篡改payload、18任务预算精确边界与超限、价格过期。
下一步：项目大脑审PR；未获用户授权不调用；正式选型与治理变更仍由所有者决定。

官方核查入口（2026-10-17）：
- https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses
- https://developers.openai.com/api/docs/guides/reasoning
- https://developers.openai.com/api/docs/models/gpt-6.1-sol
- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://ai.google.dev/api/interactions-api.md
- https://ai.google.dev/gemini-api/docs/tokens
- https://ai.google.dev/gemini-api/docs/pricing

只复用现有仓库Prompt、Pydantic Screenplay和比较题包，无外部源码复制。

