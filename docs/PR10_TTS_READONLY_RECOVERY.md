# PR-10j｜已持久化 TTS 失败状态的只读恢复分类（不重发）

## Purpose

PR-10g/h/i 已把审核、单次持久化 paid intent、三级预算预留、唯一 Provider Interaction、24k PCM WAV 格式登记和未知 ACK 隔离接通。进程在供应商调用前后崩溃后，不能将“没有 WAV”统统理解成“请求失败可以重试”。这里新增一个**纯 SQLite 本地读取观察者**，为运维提供明确的安全恢复分类。

`inspect_tts_recovery(db,task_id)` 在**同一个 SQLite BEGIN 读取快照**核实 task、reservation 与不可修改事件序列。严格验证：
- 状态和审计事件次数/顺序：`prepared_offline`、`budget_held`、`paid_intent_committed`、`interaction_id_recorded`、`unknown_ack_quarantined`、`format_verified_not_speech_reviewed`、`operator_entered_vendor_charge`。缺失、重复、跳状态都 fail closed。
- 未提交不能假称已经产生 Interaction；提交成功后必须保留历史预算。已确认 Interaction 不可伪装为没提交；只有 `verified` 可有经过验证的 64 位 SHA256 和合理音频长度。
- 人工录入供应商发票必须具有对账事件、审核人和凭证；**人工录入不等于独立核验 Google 账单**。既有 `quarantined` 即使人工对账完成仍不可再次提交。

返回结果**不含任务 ID、供应商 Interaction ID、剧本文字、演员声音、密钥、账单凭证、WAV 本体**，仅有 `task_status`、保留费用状态、是否拥有回执和受限的下一步人工动作说明。对外永远 `automated_retry_allowed=false`、`recover_by_resubmitting=false`、`production_cutover_allowed=false`。

具体分类：

| Task | 安全只读判断 |
|---|---|
| `prepared`，无预算 | 尚无提交权限，须先完成单独预算/审批流程 |
| `prepared`，held | 可单独审批原始任务，但本观察者绝不提交 |
| `submission_intent` | 结果不明；只允许查询**原**供应商请求历史 |
| `quarantined` | 可能已计费；人工核对原账单或供应商 Support，禁止重发 |
| `acknowledged` | 已有唯一 Provider ID，只能恢复**原请求**的音频 |
| `verified` | 本地 WAV 格式证据有记录；仍须账单和商业使用权审核 |

纯离线回归实际模拟这五类状态、人工对账、Fake ACK 丢失及无效 WAV；额外注入伪造 Provider ID、损坏哈希、假发票、删除持久预算与异常/重复审计，要求全部 fail closed，且确认读取前后的数据库行完全一致。无新 API Key、网络、Turso、Drive 或收费模型请求。生产数据库恢复流程、跨 Runner 可见性、Google 历史查询/人工对账仍待专项验收。
