---
task_id: "2026-03-16-orchestra-integration"
document_type: task-readme
title: "Orchestra 调度器设计：任务板驱动的自主 Implementation Run"
current_layer: prd
status: todo
author: "Kiro"
created: "2026-03-16"
last_updated: "2026-03-17"
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/standards/glossary.md
  - src/vibe3/flow/
  - src/vibe3/task/
---

# Task: Orchestra 调度器设计

## 概述

**Orchestra** 是 Vibe Center v3 的调度器子系统，负责从任务板（GitHub Issues）拉取任务并自动分发给 Agent 执行。

本任务参考 [openai/symphony](https://github.com/openai/symphony) 的调度工程理念，设计适合 v3 多 Agent 编排体系的自动化调度层。

核心结论：**借鉴 Symphony 的状态机和 reconciliation loop 设计，用 Python 实现 Orchestra 调度器，叠加在 v3 的 handoff 责任链之上**。

## 当前状态

- 层级: PRD（需求分析层）
- 状态: 见 frontmatter `status` 字段
- 最后更新: 2026-03-17

## 文档导航

### PRD / 需求分析
- [prd-orchestra-integration.md](prd-orchestra-integration.md)
- [github-issue-draft.md](github-issue-draft.md)

## 关键约束

- Orchestra 调度器使用 Python 实现，遵循 v3 技术栈。
- 状态机和 reconciliation loop 通过 `vibe3 flow` + `vibe3 task` Python API 实现。
- WORKFLOW.md 规范作为 `AGENTS.md` 的补充格式，不替换现有文档体系。
- 任何新增 CLI 命令必须符合最小变更原则，优先扩展现有命令。
