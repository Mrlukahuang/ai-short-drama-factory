## Scope（必填，CI 会检查）

Stage: G
Req: R
AMEND check: 已阅读 AMEND.md，本 PR 不违反任何 Active 条目（是 / 否，否则说明）

## What changed?

## 是否用真实模型验证？
- [ ] 是：附 Actions run / 费用
- [ ] 否：仅 Fake / 离线（不得声称成片可用）

## How verified?
- [ ] `pytest -q`
- [ ] No paid API calls in CI
- [ ] Mock results are not presented as production output
- [ ] `docs/handoff/CURRENT.md` 已更新

## Production gates
- [ ] Schema + migration impact documented（无则写“无”）
- [ ] Cost / retry / idempotency impact documented
- [ ] Rights / face / voice / data security checked
- [ ] Model versions and deprecations verified if relevant（对照 docs/MODEL_LANDSCAPE.md）
- [ ] 借鉴了第三方代码？已登记到 docs/REFERENCE_PROJECTS.md 第 7 节

## Proposed AMEND（可选：认为方向需要调整时写这里，由所有者决定）
