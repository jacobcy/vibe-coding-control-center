---
task_id: "2026-03-02-vibe-task"
document_type: task-readme
title: "Vibe Task Unified Entry"
current_layer: "plan"
status: "in-progress"
author: "Codex GPT-5"
created: "2026-03-02"
last_updated: "2026-03-02"
related_docs:
  - docs/tasks/2026-03-02-cross-worktree-task-registry/plan-v1-initial.md
  - docs/tasks/2026-03-01-session-lifecycle/plan-v2-phase-2.md
  - bin/vibe
  - skills/vibe-task/SKILL.md
gates:
  scope:
    status: "passed"
    timestamp: "2026-03-02T00:00:00+08:00"
    reason: "已明确该任务专注于跨 worktree 总览的统一入口，不再混入 session lifecycle 设计。"
  spec:
    status: "passed"
    timestamp: "2026-03-02T00:00:00+08:00"
    reason: "已明确 CLI 为底层事实入口，skill 只包装 CLI 输出。"
  plan:
    status: "passed"
    timestamp: "2026-03-02T00:00:00+08:00"
    reason: "已生成 plan-v1-initial.md。"
  test:
    status: "pending"
    timestamp: ""
    reason: ""
  code:
    status: "pending"
    timestamp: ""
    reason: ""
  audit:
    status: "pending"
    timestamp: ""
    reason: ""
---

# Task: Vibe Task Unified Entry

## 概述

该任务负责把跨 worktree 的任务总览能力整理成统一入口：

- `vibe task`：CLI 只读事实入口
- `vibe-task`：skill 解释层

两者共享同一份 `git-common-dir/vibe/` 数据源，不重复实现解析逻辑。

## 当前状态

- **层级**: Plan（执行计划层）
- **状态**: In Progress
- **最后更新**: 2026-03-02

## 文档导航

### Plan（执行计划层）
- [plan-v1-initial.md](plan-v1-initial.md)

## 关键约束

- CLI 是唯一底层事实入口。
- skill 必须先调用 `bin/vibe task`，不得直接读 registry。
- 不实现 `vibe-switch`，不在本任务中扩张成调度系统。
