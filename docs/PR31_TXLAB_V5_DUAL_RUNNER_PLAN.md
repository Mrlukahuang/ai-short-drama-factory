# TxLab v5 — 单次隔离双 Runner 实验（授权已消耗，观察者未验收）

## 实际单次执行证据与不通过部分（2026-10-14）

**授权已使用且 v5 写入入口永久锁止，不允许 rerun 或自动补写。**

[远端 Actions #38509779430](https://github.com/Mrlukahuang/ai-short-drama-factory/actions/runs/38509779430)，事件 `push`，Run attempt=1，整体状态 **failure**（不是 green）。按照五个真实 GitHub Job 日志：

- Setup `115675379919`：success，日志打印新对象数 `schema_objects=6`、`synthetic_only=true`、`production_touched=false`、`paid_provider_calls=0`。
- Writer actor-a `115675529609`：success，脱敏 output JSON 表示 `outcome=denied`。
- Writer actor-b `115675529344`：success，脱敏 output JSON 表示 `outcome=accepted`。两 Job 不同，收到同一 run ID 和 synthetic nonce。**不能仅凭这些 status 证明数据库端最终完整性。**
- Seal `115675656460`：success，已按本地操作合同把隔离 gate 改为 paused/epoch=2，并禁止旧 token 继续产生新预算写入。
- 第三个独立 SELECT-only Observer `115675757454`：**failure**，只获得安全错误 `TxLab v5 stage=observe category=unknown`，不能确定是远端 SQL、query-only PRAGMA、服务端视图或证据校验失败。没有通过独立只读对账，所以 `remote_multi_runner_verified=false`、`remote_fencing_verified=false`，不允许升级为已通过。

以上严格区分“actor 竞争运行”和“远端完整验收”。因为此前数据库事务可能已提交，**禁止再次触发此 Workflow**，绝不解锁之前的 v1–v4。为后续排障，可以新建不修改数据库的专用**只读**验收器，分阶段输出固定类别及汇总计数；这应被视为新的只读查询而非重新执行 v5。



## 授权与成本边界

2026-10-14 用户明确授权自行开展**预计不超过 2 USD 的测试**并持续推进，超过 2 USD 须先申请。预计本实验 GitHub Actions 最多 **5 个标准 Linux Runner × 6 分钟 = 30 Linux 分钟**；参考 GitHub 官方基础单价 USD 0.006/分钟，理论 Actions 用量上限约 USD **0.18**（若免费额度可用则实际可能为零）。远端 Turso 的 6 个 Schema 对象、两笔就绪登记、至多一笔真实合成预算预留、3 笔测试审计、一次 epoch 暂停和有限读回，在 Turso 免费额度内通常几乎无成本，但**无法从 GitHub 连接器读取用户实际扣费、剩余额度或确定绝对现金上限**。因此这是保守用量限制/成本估算，不是账单保证。绝不调用付费图片、视频、TTS Provider，`paid_provider_calls=0`。

## 隔离、执行与门禁

- 严格复用已配置的**专用 TxLab 隔离数据库** Secrets，`validate_lab_url` 禁止正式数据库域名；新对象全部 `pr31_v5_*`，禁止旧实验/生产表读取修改。只接受全新空前缀；不自动清理、不修复部分 DDL、不重试。
- `.github/workflows/txlab-v5-dual-runner-once.yml` 的初始版本 **`setup.if: ${{ false && ... }}`**，本准备 PR 和随后其他 PR 即使在 main 上触发 Workflow，也不进行任何远端 SQL。一个单独全绿审查/激活 PR 才能在限定的新**唯一 Merge commit 标识** `PR31-V5-EXECUTE-ONCE-20261014` 下开启 Setup；History gate 校验首次 `github.run_attempt=1`、精确 main commit 和同 SHA 的唯一 GitHub Workflow run，拒绝 Re-run/新 commit。所有下游 actor / seal / observer 也受 `run_attempt=1` 与上游成功控制。用原 TxLab concurrency group 串行跨版本实验。
- 五个独立 Actions Job 分别运行于 **五台独立调度的 GitHub Runner**：setup、actor-a、actor-b、seal、observer。真正同时争抢的是 actor-a/b：各自安装独立 `libsql==0.1.11`、连接同一专用远端库，在新 `ready` 表用提交后读回的双进程 barrier 保证两端已启动，再独立 `BEGIN IMMEDIATE` 读取同一暂停/epoch 和合成预算 60 cents，尝试持久写入 40 cents 的合成 held 状态与两个 append-only 审计；仅一方可成功。遇到 SQLite BUSY 时**绝不重试写入**，只在独立只读观察到对方已成功后将该方标记为被拒绝，未知提交状态则直接失败。
- seal Job **仅在两 actor 成功退出**时启动，暂停 gate epoch=2，事务追加 pause 审计，尝试旧 epoch 条件写入必须匹配 0 行；observer **全新 Runner 上只读**检查 gate、准备就绪行数、held、审计、FK，核对两个来源不同的 GitHub Job ID 与一次 Run ID/批次 SHA256。合成字典通过结构校验后仍不自动设置 `remote_multi_runner_verified=true`，须由总指挥独立检查 GitHub job 元数据及远端 SQL 日志后更新里程碑。
- 只允许一次真实 DDL/事务机会；任一阶段失败绝不 rerun，也不得复用 v1/v2/v3/v4 授权。运行后必须通过另一 PR 将 v5 workflow `if:false` 永久硬锁。

## 本 PR 的真实验收边界

准备 PR **仅包含被禁用的 Workflow、代码、无云端的 SQLite + native SDK 回归测试和文档**；绝未实际运行远端 v5。单独激活 PR 合并触发前，须确认 Python 3.11、3.13、FFmpeg 和真实 SDK 本地专项全部通过。该 v5 测试只验证两个真实 Runner 对同一远端隔离数据库的**一笔合成预算竞争和持久暂停**，不代表完整生产 Schema、全局权限、服务器租约时钟、网络 ACK 丢失或任何真实模型计费安全已经全部验收。

## 外部来源

- GitHub Actions 计费：https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Turso 官方定价：https://turso.tech/pricing

**生产数据库和 Worker 完全保持不动；项目“完成”不能用一次 v5 绿色运行替代。**
