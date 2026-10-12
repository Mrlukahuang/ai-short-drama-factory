# PR-06 小说影视改编与第三方处理权限人工审核记录

新增不可变的 `novel_rights_reviews`，可按小说保留多次审核版本。每条审核包含审核人标签、持有人、凭据引用、有效期、允许地域、语言、媒介和是否允许发送给第三方 AI。

内部接口：

- `POST /api/v1/novels/{source_id}/rights-reviews`：登记人工审核的决定和范围。
- `GET /api/v1/novels/{source_id}/rights-reviews`：查看历史，不覆盖过去记录。
- `GET /api/v1/novels/{source_id}/rights-eligibility`：按地域、语言、媒介与 `external_ai` 检查最新审核。

权限判定规则：原书必须有 screen_adaptation 授权，最新审核为 approved，时间和地域等均匹配；如要求外部 AI 分析，必须额外开启 allow_external_ai。最新的拒绝审核会覆盖之前的批准（历史仍保留）。

**重要的安全限制：**本地 FastAPI 目前没有身份认证与管理员角色，表单只能作为待核实的内部声明，不代表已核验法律效力。即使 `eligible=true`，`external_model_calls_enabled` 始终为 false，且工厂没有任何外部小说处理模型。未来上线前必须添加身份鉴别、合同/地域核验、加密存储、审计日志、预算批准、供应商数据处理条款检查，才可以真正允许第三方模型调用。

`adaptation_jobs` 的既有登记接口不会被改为自动生成或审批成功；PR-06 只增加权限范围评估与审核记录。
