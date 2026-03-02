---
task_id: "2026-03-02-command-slash-alignment"
document_type: task-readme
title: "Command vs Slash Alignment"
current_layer: "plan"
status: "todo"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
related_docs:
  - bin/vibe
  - docs/standards/command-structure.md
gates:
  scope:
    status: "pending"
    timestamp: ""
    reason: "Review the slash/shell boundaries before implementation"
  spec:
    status: "pending"
    timestamp: ""
    reason: ""
  plan:
    status: "passed"
    timestamp: "2026-03-02T10:40:00+08:00"
    reason: "The analysis and plan-v1 is completed and logged."
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

# Task: Command vs Slash Alignment

## 概述

随着系统向双轨生命周期发展，我们的 CLI 工具命令集（`vibe <command>`，依靠 `lib/*.sh` 实现）与 AI Workflow 交互命令集（`/vibe-<command>`，依靠 `skills/*` 和 `.agent/workflows/*` 实现）之间产生了功能重叠和底层隔离。

本任务旨在深度审查两者的边界，并制定一套**映射与代理准则**。
核心原则为：
1. **Shell 赋能 Slash (高低解耦)**: Slash 绝不应使用文本替换工具来直接操作复杂的领域数据（特别是 `.json` Registry 等结构化大盘）。底层脏活、JSON 的查询/序列化更改应该提供稳定 `vibe task update` 或类似的 Shell 接口，由 Slash (AI) 像调用 API 一样触发。 
2. **Slash 包裹 Shell (交互升维)**: 生硬而刻板的 CLI 工作流（例如提 PR，做 Code Review）应该隐藏在能够互动的 Slash 指令（`/vibe-commit`、`/vibe-pr`）背后。

## 当前状态

- **层级**: Plan
- **状态**: Todo
- **最后更新**: 2026-03-02

## 文档导航

### Plan（执行计划层）
- [plan-v1.md](plan-v1.md)
