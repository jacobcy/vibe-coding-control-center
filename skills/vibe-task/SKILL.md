---
name: vibe-task
description: Use when the user wants a cross-worktree flow/task overview, asks which existing flow or task context to resume next in the current repo, or mentions "/vibe-task". Do not use for project-level roadmap prioritization or task-flow runtime repair.
---

# /vibe-task - Cross-Worktree Flow Overview

查看当前仓库下各个 worktree 承载的 flow/task 现场，建议下一步优先回到哪个。

## 核心原则

- **只做总览**：不做复杂审计或修复
- **基于真源**：只读 shell 输出，不补充字段
- **简单建议**：给出优先级建议，不强制调度

## Workflow

### Step 1: 运行 CLI

```bash
vibe3 task status
```

必要时补充：

```bash
vibe3 flow show
```

### Step 2: 解析输出

从 CLI 输出中提炼：

- worktree 名称、路径、branch
- flow state、task status
- PR 状态、dirty/clean
- next step

**不补充 CLI 未提供的字段**。

### Step 3: 生成建议

用简洁报告向用户说明：

1. 当前有哪些 worktree
2. 每个 worktree 承载的 flow/task
3. 哪个值得优先回到（理由）

优先级规则：

- blocked → 优先提示阻塞
- in_progress + dirty → 建议收口
- done/idle → 说明无明显优先级

### Step 4: 输出格式

```text
Worktrees
- wt-foo: task=issue-123, state=active, dirty
- wt-bar: task=issue-456, state=blocked, clean

Recommendation
- 优先回到 wt-foo
- 原因：该现场 dirty 且 next step 已明确
```

## 职责边界

**vibe-task 负责**：
- 跨 worktree flow/task 总览
- 下一步优先级建议

**其他 skills 负责**：
- runtime 绑定修复 → `vibe-check`
- roadmap 规划 → `vibe-roadmap`
- issue intake → `vibe-issue`

## Restrictions

- 不做复杂审计或修复
- 不补充 CLI 未提供的字段
- 不强制调度（只给建议）
- 不读底层 JSON/SQLite