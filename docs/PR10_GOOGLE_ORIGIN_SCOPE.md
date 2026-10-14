# PR-10o｜TTS Google 原始项目/身份来源不可变绑定（纯离线）

## 增量合同

PR-10n 已提供 **仅 Fake** 的 `interactions.get(id=original_id)` 合同，但旧的 `tts_tasks` 缺乏原始请求使用的 Google 项目/身份上下文。仅凭 Interaction ID 不足以授权远端读取；两组凭证串号、权限错配或旧账户失效不能安全自动恢复。

本 PR 为 **本地 SQLite** 添加 `tts_google_origin_scopes`（每 TTS task 一行）：

- `task_id` 唯一且关联既有任务，只有任务仍是 `prepared` 时能通过 `bind_offline_tts_google_origin` 首次登记；
- `project_ref_sha256` / `principal_ref_sha256` 只能来自**不含密钥的外部登记 ID** 的脱敏 64 位小写 SHA256 指纹；不允许 API Key、Token、个人名称、原始账号和脚本正文入库；
- 固定 `source='offline_unverified'`，因此**纯操作员声明**无法假装真正供应商认证；
- 数据库级 UPDATE / DELETE 触发器阻止既有绑定被覆盖；再次传入相同指纹幂等，不同指纹 fail closed；旧的无绑定任务绝不靠读取时临时“补认”；
- 原 PR-10n Fake GET 的单个 SQLite 只读事务必须同批审核任务审计链、held/reconciled 预算和原始 Google scope，并要求 Getter 同时持有完全匹配的原 `project_ref_sha256` 和 `principal_ref_sha256`。GET 前身份不符/旧任务没有绑定就拒绝，**不调用任何 Getter**；GET 后再检查状态一致。

新增测试包含前置/后置 intent 时序、重复登记、不同上下文、缺失旧记录、数据库直接修改/删除拦截、伪造客户端、权限/超时等 PR-10n 既有用例。CI 零网络/零付费 API。

## 明确保留的限制

1. 仅建立**本地不可变的未核实上下文声明**，没有操作员身份认证、没有凭据来源校验，更没有真正的 Google project/principal 自证。
2. 旧任务没有可信出厂上下文时只可**人工核查**，不可补写假 origin 让 GET 自动通过。原已 ACK / unknown ACK 不可重发。
3. 没有修改 `commit_tts_submission_intent` 的全局测试旧流程，没有真实 `google-genai` import、HTTP、`interactions.create`、远端音频回收、Turso 迁移/切换或生产 Worker。
4. 在实施真实供应商读取之前必须再加：原始提交时可信身份捕获、短期最小权限只读凭证、同一项目/身份授权链独立核查、计费记录与音频/声音权益审查；供应商保留期、403/404、权限或网络错误全部 fail closed。

**绝不重跑已消费的 Gemini TTS Canary / TxLab 工作流。** 本 PR 的本地绿灯不能被表述为 Google 真实历史音频可读或付费成本已对账。
