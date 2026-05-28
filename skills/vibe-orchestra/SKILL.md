---
name: vibe-orchestra
description: Use when the user wants to inspect running issues in assignee pool, or judge which issue to start next. Do not use for RFC/blocked issues or roadmap triage.
---

# /vibe-orchestra - Assignee Issue Pool 管理

查看 assignee issue pool 中运行中的 issues，建议下一个值得处理的 issue。

## 核心原则

- **只管 assignee pool**：运行中的 issues
- **只做建议**：不强制调度
- **基于真源**：只读 shell 和 supervisor materials

## Scope

**只看 assignee issue pool**：
- 已分配给 manager 的 issues
- 正在运行或 ready 的 issues
- pool 中下一个值得处理的 issue

**不看**：
- RFC issues（由 `vibe-task` 管理）
- Blocked issues（由 `vibe-task` 管理）
- Backlog triage（由 `vibe-roadmap` 管理）

## Workflow

### Step 1: 查看运行状态

```bash
vibe3 task status
```

必要时查看 serve status：

```bash
vibe3 serve status
```

### Step 2: 过滤 assignee pool

找出已分配给 manager 的 issues：

```bash
gh issue list --assignee <manager-username> --limit 20
```

### Step 3: 判断优先级

参考 `supervisor/governance/assignee-pool.md`，按以下顺序排序：

`milestone -> roadmap/* -> priority/[0-9] -> issue number`

结合当前人工上下文：
- 是否有人已明确接手某个 issue
- 是否有活跃 PR 或 review follow-up

### Step 4: 提出建议

```text
📋 Assignee Issue Pool 状态

Running Issues
- #123: in_progress, wt-foo
- #456: ready, no worktree

Next Issue
- 建议处理 #456
- 原因：pool 中唯一 ready 且无阻塞

Reason
- milestone: Phase 1
- roadmap: p1
- priority: 5
```

## 与其他 Skills 的区别

- **vibe-orchestra**: 管理运行中的 assignee issues
- **vibe-task**: 看 RFC 和 blocked issues（问题 issue）
- **vibe-roadmap**: 版本规划和 backlog triage

## Restrictions

- 不看 RFC 或 blocked issues
- 不做 roadmap triage
- 不写代码
- 不替代人类做最终决策