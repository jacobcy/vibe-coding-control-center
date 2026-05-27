# Task Status 过滤逻辑

> 本文档定义 `vibe3 task status` 的完整 issue 过滤决策树（**展示侧/读取侧**）。
> 代码位置：`src/vibe3/commands/status.py`（过滤逻辑）、`src/vibe3/commands/status_render.py`（渲染逻辑）、`src/vibe3/services/task_status_classifier.py`（状态分类）。
>
> **写入侧治理流程**（谁/何时打 `orchestra-scanned` / `orchestra-governed` / `roadmap-reviewed`）：参见
> [docs/governance/governance-roadmap-closed-loop.md](../../governance/governance-roadmap-closed-loop.md)。

## 核心原则

**state 标签是进入主流程的标志。** 没有 state = 没进过主流程，有 state = 进过主流程。

## 完整决策树

```
orchestrated_issues (all open issues)

[Rule 0] state == BLOCKED
  --> Blocked Issues (standalone, regardless of assignee)

[Rule 0] flow.pr_ref exists
  --> Flows with PRs (completed / ready to merge)

[Rule 1] roadmap/rfc label
  --> RFC (human decision needed, always shown)

[Rule 1] roadmap/epic label
  --> Epic (umbrella issue, always shown)

supervisor label
  --> Supervisor Issues (standalone)

--- Main flow filtering for remaining issues ---

No state label (never entered main flow):

  No assignee [Rule 4]
    --> SKIP (roadmap-intake never picked up)

  Local manager assignee:
    Has orchestra-governed [Rule 7]
      --> State Missing anomaly
    No orchestra-governed [Rule 5]
      --> Waiting Governance (awaiting assignee-pool)

Has state label (entered main flow):

  state == READY:
    No assignee or assignee not local manager [Rule 2]
      --> Ready Exception
    Local manager assignee [Rule 8 + 9]
      --> Ready Queue (awaiting manager dispatch)

  state in {CLAIMED, HANDOFF, IN_PROGRESS, REVIEW}:
    No assignee [Rule 2]
      --> Active Exception
    Assignee not local manager [Rule 3]
      --> Remote Tasks
    Local manager assignee [Rule 9]
      --> Assigned Intake

  state == MERGE_READY / DONE:
    --> Completed (may appear in PR section)
```

## 规则详解

| 规则 | 触发条件 | 展示区块 | 说明 |
|------|---------|---------|------|
| 0 | state == BLOCKED | Blocked Issues | 被阻塞，独立展示，不管 assignee |
| 0 | flow.pr_ref 存在 | Flows with PRs | 完成/待合入，独立展示 |
| 1 | roadmap/rfc 标签 | RFC | 需要人类设计决策，始终展示 |
| 1 | roadmap/epic 标签 | Epic | umbrella issue，始终展示 |
| 2 | 有 state 但无 assignee | Exception | 异常：进过主流程但丢失 assignee |
| 2 | state/READY + assignee ≠ 本机 manager | Ready Exception | 异常：非本机 assignee |
| 3 | state ∈ active + assignee ≠ 本机 manager | Remote Tasks | 被别的系统拿走 |
| 4 | 无 state + 无 assignee | SKIP | roadmap-intake 没收进来 |
| 5 | 无 state + 有 assignee + 无 governed | Waiting Governance | 等待 assignee-pool 检查 |
| 7 | 无 state + 有 governed | State Missing | 异常：处理过但缺 state |
| 8 | state/READY + 有 governed | Ready Queue | 等待 manager 启动 |
| 9 | state ∈ active + assignee = 本机 manager | Assigned Intake | 正常进行中 |

## governed 标签的约束

> 注：以下约束是 governance agent 的内部逻辑，不在 status 展示层实现。

`orchestra-governed` 表示 assignee-pool 已对该 issue 做出决策。合理的结果只有三种：
- **roadmap/rfc** — 需要人类决策
- **roadmap/epic** — 拆分为 sub-issues
- **close** — 过滤掉（不再出现在 status 中）

如果 governed 存在但不是上述三种结果之一，则必须配套有 `state/*` 标签。

## 与 governance 的关系

- `orchestra-scanned`：roadmap-intake 层已审查 → 等待 assignee-pool
- `orchestra-governed`：assignee-pool 层已决策 → 必须有 state 或 rfc/epic
- `roadmap-reviewed`：roadmap decider 已审查

三层标签实现治理闭环。详见 `supervisor/governance/assignee-pool.md`。
