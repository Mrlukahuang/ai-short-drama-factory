# PR-31v5c｜远端 libSQL Observer 查询兼容性修复（离线）

## 已有真实证据

真实 v5 写入运行 [#38509779430](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38509779430) 中，两个 GitHub Worker Job 分别返回 accepted/denied，隔离 gate 的 pause 阶段成功，第三 Job 在观察阶段失败。独立一次性**只读**诊断 [#38510686538](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38510686538) 确认：远端 `PRAGMA query_only=ON` 报 `query_unavailable`，而 `PRAGMA foreign_key_check`、事务 `BEGIN`、纯 `SELECT` 的 gate/ready/hold/audit 快照均为 `ok`，远端最终账本完整一致。

## 修复的边界

保留已消耗 v5 的 Setup/Actor/Seal 原代码不变；仅修改 `stage_observe(...)` 为 **固定 SELECT、BEGIN 和已验证可用的只读检查 PRAGMA foreign_key_check**。不会执行 `PRAGMA query_only=ON` 或 `PRAGMA foreign_keys=ON` 这两种连接参数设置。这样移除了观察失败的一项已证实兼容性障碍，同时继续严格检查 gate epoch=2/paused、两个准备记录、一个 hold、三条审计、外键完整性及两个独立 Job 回执。

**注意：不执行 `PRAGMA query_only=ON` 不等于真实数据库只读凭据。** 本模块不会发起写 SQL；但只读最小权限凭据是否生效，仍是后续独立验收项。新回执明确返回 `read_only_sql_path=true`、`database_level_read_only_token_verified=false`、`remote_multi_runner_verified=false`、`live_cutover_permitted=false`。

离线单测使用一个拒绝任何连接参数设置/写 SQL 的封装：它模拟远端 SDK 对 `query_only` 的拒绝，验证观察仍能完成；同时验证外键异常、伪造 Job IDs 均 fail-closed。第四项必跑 CI 还使用真实 pinned `libsql==0.1.11` 本地 SDK + 这个 SQL 白名单封装验证一致性。**不重开、也不重跑旧 v5 云端工作流；所有旧 TxLab 入口始终硬锁。**

此次修复让未来新实验的观察者可以使用已经验证可用的读路径，但不以离线结果冒充新的远端实测，也绝不宣称生产级权限和网络 COMMIT 故障已经完成。
