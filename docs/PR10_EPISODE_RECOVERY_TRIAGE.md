# PR-10m｜整集已审核 TTS 任务只读恢复总览（离线）

已有 PR-10g–10l 实现了单句 TTS 的持久预算预留、不可重复提交意图、Fake SDK 提交和只读审计/既有音频回读，但没有整集层面的恢复门禁：其中一句成功并不意味着剩余每句已经创建任务、已核验或可以继续生产。

`inspect_episode_tts_recovery(db, production_id)` 在**同一个本地 SQLite 读事务**中读取指定 Production 的已审核 `EpisodeDraft`、所有 TTS 任务及逐任务的不可变事件，复用原有 PR-10j 审计分类器。逐句以 `(shot_id, cue_index)` 覆盖全部已经审核的结构化对白；任何少任务、未知镜头、重复任务、缺少结构化说话人、损坏的审计状态或预算预留不一致都会整体 fail-closed。最多接受 96 句，避免无界查询。

输出为不含台词、角色/声音/任务 ID、Google interaction ID、用户路径或账单原文的**计数摘要**：prepared/submission_intent/quarantined/acknowledged/verified 数量，held/reconciled/missing 数量，是否存在 ACK 未知、是否有已知交互需要只读回收、是否所有语音仅在格式层面验证。就算全是 `verified`，依然永远 `publish_approved=false`、`automatic_generation_or_retry_allowed=false`、`production_cutover_permitted=false`，因为语音真实性、商用授权、供应商账单和真实生产 Worker 仍未验收。

新测试验证两句均准备、一个 verified + 一个 quarantined、其中一句指向错误镜头、其中一条审计被篡改都会整集阻断；检查只读探针不会改变任何账本/预算，也不会发送 Google 请求。**不开放实际付费生成、不重试已消耗 TTS/TxLab 工作流、不移动生产数据库。**
