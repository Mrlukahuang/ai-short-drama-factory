# PR-31c3d — 未来 TxLab v5 双 Runner 验收的证据合同（离线、只验结构）

v4 已经真实验收**同一个远端隔离 Turso 数据库上的串行事务**，而 c3a 的多进程竞赛与 c3c 的顺序穷举仍只有**同机本地**证据。下一步双 GitHub Runner 要写同一个隔离 v5 数据库时，不能只凭「两个 Job 都是绿灯」就宣布成功，必须核实确实为两个**不同 GitHub Runner Job**、相同实验批次、共同数据库观察、且没有重复预算、重复提交或旧 Worker 越权。

本轮新增 `inspect_proposed_v5_evidence`，接收严格白名单字段的三个**纯虚构**字典：Runner A、Runner B、第三个独立 read-only 观察者。每条记录必须声明同一个首次 GitHub Actions Run ID、三个**不同**的 Job ID、相同实验随机 nonce 的 SHA256 摘要、`isolated_turso_remote` 隔离后端、精确 `pr31_v5_` 前缀。两 Writer 结果在合成 `0.60` 限额下必须一个 accepted / 一个 denied（本规范只定义这一种竞争场景）；read-only 观察者须确认 paused/epoch≥2，且恰好一笔 held、一条意图审计、一条 gate 审计、没有旧 token 成功写入、没有重复任务或任何供应商调用，FK 完好，没有 unknown COMMIT。

任一缺失、多余字段（特别是 raw Task ID、URL、Token）、凭据、不同 Run/Job ID、重复 ACK、模糊网络提交、审计缺失、Boolean 假冒整数、假本地 SDK 报告都触发脱敏固定拒绝，不返回原始数据。测试涵盖一份字段自洽但**完全伪造的合成例子**，以及大量破坏字段、来源、状态或内容的负面用例。

**极其重要：即使三个字典自洽，也只能得到 `proposed_receipt_shape_consistent=true`，绝不等于「两台 Runner 真实运行过」。** 字典可能是客户端自行伪造的；`remote_multi_runner_verified=false`、`remote_fencing_verified=false`、`may_authorize_another_remote_test=false`、`may_resume_production=false`、`live_cutover_permitted=false` 永远保持 false。以后真正的远端验收，还必须由人工独立核对 GitHub job 身份、数据库端独立只读 SQL、服务器事务/时钟和收费供应商独立账单。

本 PR **没有远端 Workflow、数据库 URL、Secrets、生成调用、写入端点或任何真实云端访问**；所有断言在 Python 3.11/3.13 普通免费离线 CI 中执行。TxLab v1/v2/v3/v4 仍 `if:false` 硬锁，新增 TxLab v5 真正远端写入/任务并发需重新获得明确单次授权。
