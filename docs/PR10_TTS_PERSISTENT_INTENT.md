# PR-10g｜已审核 TTS 逐句持久化任务、三级预算与未知回执隔离（仅离线）

## 已解决的生产风险

PR-10e/10f 已验证 Gemini 3.8 Flash-Lite 能生成真实语音（一次、3.56 秒），但单句试验**没有**可复用在短剧生产的持久化任务队列，Google TTS 真实单句测试 #38525869818 已消耗并在 PR-94 锁止，严禁再次运行。这一步不会连接 Google、也不会解除该锁止；只建构即将支持真实任务的 SQLite 离线安全基础。

`tts_tasks` 记录**每个 Production/Shot/有序 Cue 的唯一指纹**、模型、预设声线、导演审核段落总时长、费用允许额和单向状态；不能重新登记另一种模型、声音或已批准文字以绕过同一句的历史请求。绝不存储明文台词、私人 Gemini SDK 请求、Google key、演员声纹或二进制 WAV。

完整状态机（绝对禁止对处于任何已提交状态的句子自动重试）：

```
prepared --(共享 Column/Series/Provider hold)--> prepared
prepared --(先持久提交 paid intent)--> submission_intent
submission_intent --(已有 interaction id)--> acknowledged
submission_intent --(ACK 丢失 / 不确定)--> quarantined
acknowledged --(仅离线已验证 WAV receipt)--> verified
```

准备阶段必须重用 PR-10e 的人工批准演员→音色/声音素材、逐字剧本、Director `start_second/end_second`、同意登记和独立 TTS review 的门禁。新 `tts_task_events` 触发器禁止 SQL 更新/删除历史事件；所有状态转移和预算预留使用本地 SQLite `BEGIN IMMEDIATE` 原子事务，不依赖云端 SDK，双线程竞争只有一次成功。

## 预算仍然是本地预授权，不是供应商硬限额

`tts_budget_reservations` 使用已有 `budget_policies` 的 Column/Series/Provider 三层限额、当日美元值和最大并发活跃数；`reserve_tts_task_budget` 会读取**视频与 TTS 两个 ledger** 中的 held 与已对账金额；原 `reserve_job_budget` 也改为对两种任务联合计算，杜绝视频先占额度后 TTS 再占同一额度的双花。所有 TTS 任务没有当前全部三层 Policy 均不能写入付费提交意图。单次预算的 USD 0.02 等数值是用户自我承诺、不是可强制阻断 Google 账单的 Provider 硬上限。

当 TTS `submission_intent` 提交到数据库后，无论供应商成功、断线、超时、没有 interaction_id 或实际是否计费，**不会返回到 prepared**。不确定时只能隔离为 `quarantined`，预算保持 `held`，不释放、不重试。已具备确切供应商 ID 的记录只做本地关联，输出 WAV 在通过 Base64/PCM/时长检验并与 SHA256 相等后只能记录技术元数据。真正的声音语义正确、独立声音版权和已付款发票并未验证，`publish_approved=false`。

人工最终账单核对 `record_tts_vendor_charge` 只接收发票证据引用和审核人，不能自动用估算覆盖真实费用；超预留会留下审计事件，不能解锁隔离任务。未配置任何 SDK 提交函数，普通 CI 运行均为 Fake SDK/本地 SQLite。

## 测试与缺口

强制本地测试覆盖单镜台词指纹不可变、多次预算调用幂等、SQLite 两线程并发竞争、已提交意图只成功一次、ACK 不确定隔离/禁止复发、视频和 TTS 双方向预算相互挤占、WAV 格式伪响应验证、事件 SQL 不可变、人工账单记录证据要求。

**仍未验证：** 实际 Google Interactions task ID 回传和可恢复 GET API、跨进程 libSQL 原子隔离、最终账单/真实语音、字幕语言/语速质量、操作员身份认证、真实并发远端 Worker。这不是生产上线，且绝不自动向第三方传递已批准但含私有内容的剧本。
