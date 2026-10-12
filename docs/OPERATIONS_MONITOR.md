# PR-20：多栏目生产监控（只读内部 API）

此阶段新增 `drama_factory.jobs.monitor.production_operations(db, *, column_id=None, series_id=None, now=None)`，从现有 SQLite 中读取审核生产、独立镜头任务、Google 恢复锁及预算预留，不发起任何 API 计费、数据库更新或后台任务。

## 可看到的信息

- 按栏目筛选多个独立 Series；按单独 Series 进一步筛选（如果 Series 不属于选中的栏目，直接拒绝）。
- 每条 Series 的 Production 总数及状态、Shot Job 的 `pending/leased/submission_intent/submitted/succeeded/failed/cancelled` 数量、使用的 Provider。
- 需要人工处理的摘要：已记录付费意图但实际费用未知；付费提交结果丢失且没有 Provider Task ID；已提交可恢复任务；仍有 Google 下载锁；过期 Worker 租约。
- 栏目预算、剧集预算和 Provider 预算在选定 UTC 日期的预留美元数、已人工核实美元数、剩余本地授权额度及活跃任务占用数。
- Provider 预算属于**整个工厂的全局额度**，即使只筛选单条 Series，也显示该 Provider 的全局使用量。否则会误认为其他栏目已花过的钱不存在。

## 安全边界

**当前只作为受信任本地 Python 函数使用，没有公开 FastAPI 路由。** 未来开放操作 UI 前必须增加登录、权限、日志脱敏与操作审计。报告刻意不暴露 Google File ID、供应商 Task ID、Secret、原始视频路径或创作提示词；只返回内部 Series ID、栏目 ID、聚合状态和金额。

报告中的“费用未知”只表示已发生或可能发生供应商请求但账单尚未手工核实，**不代表零费用，也不代表 Google 账单真实金额**。预算使用量是本地软件门禁统计，不是供应商硬账单限制。

## 离线测试

`pytest -q tests/test_operations_monitor.py`

测试涵盖两部剧共享预算、失败/提交/下载锁告警、按栏目和 Series 过滤、跨栏目非法筛选拦截、过期租约、空栏目与只读无副作用。普通 Python CI 即可执行，不需要 FFmpeg 或 Google API。
