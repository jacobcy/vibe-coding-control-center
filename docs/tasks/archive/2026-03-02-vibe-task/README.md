---
task_id: "2026-03-02-vibe-task"
document_type: task-readme
title: "Vibe Task Unified Entry"
author: "Codex GPT-5"
created: "2026-03-02"
last_updated: "2026-03-10"
related_docs:
  - docs/tasks/2026-03-02-cross-worktree-task-registry/plan-v1-initial.md
  - docs/tasks/2026-03-01-session-lifecycle/plan-v2-phase-2.md
  - bin/vibe
  - skills/vibe-task/SKILL.md
---

# Task: Vibe Task Unified Entry

> 历史语义说明（2026-03-10）：本归档任务产生于 `vibe-task` 入口语义仍在收敛的阶段。现行语义已经统一为“跨 worktree 的 flow/task 总览”；如果下文提到 worktree，总是指物理承载目录，而不是用户真正要进入的运行时对象。

## 概述

该任务负责把跨 worktree 的 flow/task 总览能力整理成统一入口：

- `vibe task`：CLI 只读事实入口
- `vibe-task`：skill 解释层

两者共享同一份 `git-common-dir/vibe/` 数据源，不重复实现解析逻辑。

## 当前状态

- **层级**: Plan（执行计划层）
- **状态**: 见 frontmatter `status` 字段（唯一真源）
- **最后更新**: 2026-03-02

## 文档导航

### Plan（执行计划层）
- [plan-v1-initial.md](plan-v1-initial.md)

## 关键约束

- CLI 是唯一底层事实入口。
- skill 必须先调用 `bin/vibe task`，不得直接读 registry。
- 不实现 `vibe-switch`，不在本任务中扩张成调度系统。
