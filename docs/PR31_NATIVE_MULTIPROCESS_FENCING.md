# PR-31c3a — Native libSQL **真正不同 OS 进程**的离线 fencing / Crash 实验

本实验弥补以前 native SDK 主要在同一 Python 进程的线程间模拟竞争的空白：新测试在 GitHub Runner **同一台机器、同一个经 marker 验证的临时 SQLite 测试文件**上，通过 `multiprocessing.get_context("spawn")` 启动独立 Python 解释器。每个进程重新建立 `LocalNativeLibsqlLedger(path, offline_test_only=True)`，从磁盘重新检查合成测试 marker，自行打开真正 `libsql==0.1.11` 的 SDK 连接；绝不共享线程锁或 Connection 对象。所有 API 都只调用现有的本地实验 `fenced_claim_local_job`、`fenced_hold_and_record_intent_local`、`fenced_bind_synthetic_provider_task_local`、`set_local_writer_gate`。这些模块没有供应商网络访问权。

测试场景（显式包含在第四项强制 native SDK CI 中）：

1. **六个不同操作系统进程**竞抢两个 pending 镜头，最终恰好两个独立 attempt=1 的 token，另四个无任务；镜头审计和 gate 审计恰好两条。
2. 两个不同进程尝试 `0.40+0.40` 美元的**虚构** Provider 同日日限 `0.60` 美元，只允许一个 held+intent 成功，预算/镜头/闸门审计必须一一对应，无漏账或超额预留。
3. 一个进程执行 pause、另一个进程尝试旧 token，resume 后仍不允许复用 epoch=1 的令牌。
4. **强制进程崩溃于真实 SDK COMMIT 已落盘之后**（`os._exit(73)`）：模拟客户端完全收不到 task receipt，另一个全新进程/连接只读检查已经存在虚构 Provider Task ID 与 held 预算，旧 token 的同请求不能再写入，审计只能有一份。不是网络故障，而是本地硬崩溃验证。
5. **强制进程崩溃于全部事务写操作、gate 审计之后，但 COMMIT 之前**（`os._exit(74)`）：全新进程看到预算、状态、三个审计操作均已回滚，不能残留半笔记录。
6. 不同进程 race：pause 和写入同争一把本地数据库事务锁。只允许写入先提交或 pause 先提交两种合法串行结果，不能有 pause 已经成功后旧 epoch 新的提交。

进程崩溃通过可识别的独立子进程退出码模拟，绝不会关闭 Actions 主进程。离线 CI 不提供 Turso URL/Secrets，不执行额外云端工作流。新的测试是进程级真实并行，比线程测试更贴近远端 Runner 角色，但**各进程仍共享同一机器的 SQLite 文件系统和本地 SQLite 锁：不能据此声称多台 GitHub Runner 连接 Turso 的网络共识、数据库端时钟、远端 COMMIT 模糊状态已通过**。

现阶段真实远端只有 TxLab v4 的**串行**业务子集验收。旧 v1/v2/v3/v4 授权均已使用，工作流全部 `if:false` 硬锁。真正 PR-31c3 多 Runner 远端事务/租约与外部侧效需要新批准；生产 Worker、迁移和收费 Provider 一律保持关闭。
