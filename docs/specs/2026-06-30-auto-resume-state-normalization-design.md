# Auto-Resume State Normalization Design

**Date:** 2026-06-30
**Issue:** #3238
**Status:** Proposed

## 1. Context

Issue #3238 的直接故障链包含多个远端 `state/*` label：executor 添加
`state/handoff` 后，旧的 `state/in-progress` 仍然存在。Noop gate 只观察到
`state/in-progress`，把有效进展误判为 `state unchanged`，随后触发 blocked / resume
循环。

PR #3247 当前尝试用全局 `STATE_PRIORITY_ORDER` 从多个 label 中选择一个状态。
这个策略不能修复原场景，因为该顺序明确规定 `state/in-progress` 高于
`state/handoff`。当执行前状态是 `state/in-progress`，执行后同时存在这两个 label
时，noop gate 仍会得到相同状态。

系统已经具备远端状态替换能力：`LabelService.set_state()` 会先添加目标 label，再
删除其他 `state/*` label。缺口在于 `confirm_issue_state()` 当读取到的第一个状态已
等于目标状态时会提前返回 `confirmed`，不会执行归一化。

## 2. Goal

Auto-resume 完成后，远端 issue 必须满足以下后置条件：

```text
state_labels == [target_state.to_label()]
```

Auto-resume 的资格继续只由 issue body 真源、blocked reason 和 dependency closure
决定。多个 state label 是需要归一化的信号异常，不是选择 blocked 真源或恢复目标的
依据。

## 3. Non-goals

- 不修改 body/dependency 的真源模型。
- 不增加新的 CLI 命令。
- 不改变手工 `task resume` 的目标状态推断规则。
- 不调整全局 `STATE_PRIORITY_ORDER`；该顺序仍可用于 check 的冲突展示与一般状态
  分类，但不能证明 agent 是否产生了状态进展。
- 不通过“先删除全部 label，再添加目标 label”实现替换。

## 4. Design

### 4.1 Strict state replacement primitive

在 `LabelService` 提供显式的状态归一化原语，例如：

```python
replace_issue_state(
    issue_number: int,
    target: IssueState,
    *,
    actor: str,
) -> Literal["confirmed", "normalized"]
```

该原语复用现有 `set_state()` 的安全顺序：

1. 读取远端全部 labels；读取失败则抛出 `SystemError`。
2. 确保目标 label 存在。
3. 先添加目标 `state/*` label。
4. 删除所有不等于目标的 `state/*` label。
5. 即使当前解析出的状态已经等于目标，只要存在重复状态，也必须执行清理。

不允许把远端读取失败解释成“当前没有 state label”。否则系统只能添加目标 label，
无法证明旧 label 已被清除。

### 4.2 Auto-resume integration

`BlockedStateService.reconcile_blocked()` 在确认以下条件后进入恢复分支：

- body 没有 `blocked_reason`；
- body `Blocked by` 中没有未关闭依赖；
- GitHub body 可读。

恢复分支继续调用 `infer_resume_label()` 生成 `target_state`，但 label 写入必须使用严格
替换原语，而不是允许 `confirm_issue_state()` 短路的普通确认路径。

```text
body truth permits resume
  -> infer target state
  -> replace all remote state labels with target
  -> write body projection as active
  -> rebuild local cache as active
  -> return target state
```

Body 清理、远端 label 归一化和 DB cache 重建仍由同一个 reconciler 编排，不新增
平行 auto-resume 实现。写入顺序必须保持 fail closed：先归一化远端 label，再把 body
投影写为 active，最后重建本地 cache。若 body 写入失败，body 仍保持 blocked 真源，
下一轮 reconcile 可以重新收敛；不得在 label 归一化失败后提前清除 body block。

### 4.3 Ordinary label confirmation

普通幂等状态确认继续使用 `confirm_issue_state()`。它可以在单一远端状态已等于目标时
返回 `confirmed`，避免无意义写入。

严格替换只用于要求“最终必须只有一个状态”的边界：

- auto-resume；
- manual resume；
- 其他明确承担状态归一化职责的恢复路径。

调用方不得通过 `force=True` 隐式猜测是否需要归一化；应显式选择 confirm 或
replace 语义。

## 5. Failure Semantics

- 远端 label 列表不可读：fail closed，不更新 body 为 active，不把 DB cache 改为
  active，不允许 dispatch。
- 添加目标 label 失败：抛出 `SystemError`，保留原 blocked/cache 状态。
- 删除旧 label 失败：抛出 `SystemError`，不声称 resume 成功；下一轮 reconcile 可重试。
- DB cache 重建失败：远端 body/label 已是权威结果，记录错误并由 check 后续重建；
  调用方不得根据陈旧 cache 重复推断另一个目标状态。

为避免无状态窗口，任何失败路径都不得先批量删除全部 `state/*` label。

## 6. Noop Gate Boundary

Noop gate 不应使用全局 label 优先级来判断 agent 是否产生进展。它需要比较执行前后
的完整 `state/*` label 集合，至少满足：

- 执行前 `{state/in-progress}`；
- 执行后 `{state/in-progress, state/handoff}`；
- 结果必须判定为存在状态变化，而不是 `state unchanged`。

Auto-resume 的严格替换用于恢复一致状态；noop gate 的集合比较用于避免制造错误 block。
两者分别关闭故障链的生产端和恢复端，不能互相替代。

## 7. Tests

必须覆盖以下回归：

1. `replace_issue_state` 在目标已存在且另有旧状态时，保留目标并删除旧状态。
2. `replace_issue_state` 先添加目标再删除旧状态。
3. 远端 labels 读取失败时，replace fail closed 且不执行任何写入。
4. Auto-resume 从多状态异常恢复后，远端只剩推断目标。
5. Auto-resume label 归一化失败时，不更新 DB 为 active、不允许 dispatch。
6. Noop gate 对 `{in-progress} -> {in-progress, handoff}` 判定为发生变化。
7. 单一目标状态下普通 `confirm_issue_state` 保持幂等，不产生额外写入。

## 8. Rejected Alternatives

### Require a single state before auto-resume

拒绝。它能阻止误恢复，但不能自动修复已经存在的多状态异常，会把 flow 留在 blocked，
依赖另一个周期任务清理。

### Select the highest-priority state

拒绝。全局安全优先级不等同于生命周期进展顺序；在 #3238 的真实标签组合中仍选择
`state/in-progress`。

### Delete all state labels, then add the target

拒绝。删除与添加之间的任意失败都会留下无状态 issue，扩大 dispatch 与 check 的竞态
窗口。

## 9. Acceptance Criteria

- Auto-resume 成功返回时，远端恰好存在一个目标 `state/*` label。
- #3238 的 `in-progress + handoff` 场景不会触发错误的 noop block。
- 任何远端 label 读写失败都不会被报告为 resume 成功。
- Body 真源、label 信号和 DB cache 仍通过单一 reconciler 收敛。
- 现有普通状态确认路径保持幂等，且没有新增命令或第二套状态机。
