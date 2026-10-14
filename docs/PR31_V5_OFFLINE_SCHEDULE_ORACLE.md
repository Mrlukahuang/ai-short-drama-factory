# PR-31c3c：TxLab v5 候选协议的离线执行顺序穷举与真实 SDK 对照

## 工程目的

在 TxLab v4 串行远端实验成功，PR-31c3a 本地多 OS 进程、PR-31c3b 暂停/恢复只读审查之后，下一风险是**所有单独功能都能工作，但某个交错顺序使预算超额、旧 Worker 越过 pause 或重复登记模拟 Task ID**。

新模块 `pr31_v5_offline_schedule_oracle.py` 是完全纯粹的有限状态协议**规范**，只讨论两个虚构 Worker A/B、一个 provider 的合成日限额 0.60、每个 worker 的假预留 0.40、二者原先领取的旧 epoch=1 令牌，以及 `intent_a`、`intent_b`、`task_a`、`task_b`、`pause`、`resume` 六个原子操作。所有符号没有真实 Job/Task ID、剧情、金额或账号。不能使用这个模拟器执行 SQL 或 Provider 调用。

## 验证内容

1. **全排列穷举 6! = 720 个不同操作顺序**，每一步用纯模型给出成功/拒绝。断言：任意顺序最多一条合成 `held + intent`，只能在该 intent 之后登记它对应的合成 Task，pause 之后旧 epoch 无权再写；即便 resume 增加 epoch，原旧 token 也永久失效。
2. 在第四项强制 native SDK CI 中，基于带专用 marker 的本地隔离 SQLite 文件逐条执行 **24 个四操作排列**，加 6 条人工刻意打乱的六操作序列；每一步比较**真实 `libsql==0.1.11` SDK 事务**与纯模型预期，逐次检查 gate epoch、held 预留、预算/镜头/gate 审计数、submission_intent/submitted 状态。
3. 紧接每一步验证：不接受抢先记录 Task ID；不存在第二条预算预留；resume 不恢复旧权限；任何拒绝操作都不能产生半笔账本或审计。
4. 模型安全输出永远返回 `remote_multi_runner_verified=false`、`remote_txlab_write_calls=0`、`paid_provider_calls=0`、`may_resume_production=false`、`live_cutover_permitted=false`。

## 证据边界

这种方式检测的是**已定义的原子操作边界下，多种串行化顺序的实现偏离**。它不模拟数据库底层任意指令级交错，亦**不证明远端 Turso 对两个不同 GitHub Runner 的网络锁、隔离级别、服务端租约时间、不同连接视图或模糊 COMMIT 的真实性**。30 条 SDK 差分测试全部在同一 GitHub Runner 的临时本地数据库执行，720 条纯模型无数据库。早前 v1–v4 一次性远端写入权限都已经消耗且处于 `if:false`；此 PR 不创建、修改或解锁远端手动 workflow，不访问任何 Secrets，不改变生产 Worker。

远端 v5 真正**两个独立 GitHub Runner 写同一隔离库**仍在 PR-31c3 正式验收范围内，必须以后单次明确授权，且之前必须单独设计跨 Runner 同步、数据库服务端事务与不重试失联策略。模型通过只能说明下一次验收风险更可控，并不能当作通过证明。
