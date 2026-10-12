# PR-16a：镜头级事务任务账本（离线，无收费模型）

这一阶段完成的是生产总线所需**持久化数据结构和状态机**，不启动自动云端生成。所有函数在 `drama_factory.jobs.shots`，仅供受信任 Python 进程内部使用；没有新增未经身份验证的 HTTP Worker 或付费接口。

## 已完成

- 根据已通过剧本、人物审批的 Production，一次准备所有 Shot Job。
- 任务键包括 Production、Episode、Series、镜头完整 JSON、角色与场景资产 ID/不可变版本、模型 ID、Provider；使用 SHA256 固定幂等键。任何已有任务的内容、Provider、额度或重试次数不匹配时拒绝默默覆写。
- SQLite WAL + `BEGIN IMMEDIATE` 原子领取，租约与尝试次数上限；Worker 可以按 Series 领取任务，不会因同名镜头串入其他剧集。
- 状态：`pending → leased → submission_intent → submitted → succeeded`；允许明确失败及人工恢复分支。
- 在**任何潜在付费模型调用之前**必须提交 `submission_intent`。如果 Worker 崩溃但没有拿到供应商任务 ID，该任务会隔离到人工调查，**不能盲目重发生成**。
- 当供应商 task ID 已存在，错误恢复只把 job 返回 `submitted`，用于查询或下载**同一个生成结果**，不进入重新申请付费生成的 `pending`。
- 已有镜头结果可登记文件哈希和路径；没有任何真实 API、下载、调用成本假设。
- `shot_job_events` 逐状态追加，并在 SQLite 数据库层通过触发器阻止 UPDATE/DELETE。

## 尚未完成，严禁夸大

- **没有 Worker 执行付费生成**；所谓 claim/intention/submission 是本地状态流程，不是真实对外调用。
- `max_acknowledged_spend_usd` 是操作者记录的金额上限意图，**不是 Google 的账单硬封顶**；实际费用字段始终为空，待未来有可核对账单证据后再入账。
- 供应商结果真正的可信签名/哈希校验、R2 永久存储、对象授权、Webhook/轮询、自动队列、Budget Gate、身份认证、按栏目并发/重试节流均为后续独立 PR。
- 如果外部模型在记录 `submission_intent` 后扣费但 HTTP 回执丢失，**仍不能安全地自动重新生成**。需要人工查 Google 平台后做恢复判断。
- 本地 SQLite 账本不能用于公开可访问的生产 Worker API。正式部署前需身份认证、幂等外部调用、账单核验和合规审计。

## 测试范围

包括两个独立 Series 的任务隔离、审批门禁、幂等任务准备、变更后的输入拒绝、并发式领取排他、租约过期不自动重新付费、供应商任务 ID 的恢复与去重、意图后丢失回执的隔离、事件日志不可修改、额度输入校验。
