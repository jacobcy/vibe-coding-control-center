---
task_id: "2026-03-16-symphony-integration"
document_type: task-readme
title: "Symphony 整合方案：任务板驱动的自主 Implementation Run"
current_layer: prd
status: todo
author: "Kiro"
created: "2026-03-16"
last_updated: "2026-03-16"
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/standards/glossary.md
  - lib/flow.sh
  - lib/task.sh
  - lib/flow_runtime.sh
---

# Task: Symphony 整合方案

## 概述

[openai/symphony](https://github.com/openai/symphony) 是一个将任务板（Linear/GitHub Issues）与自主 coding agent 连接的编排框架。
本任务评估其与 Vibe Center 的架构契合度，并制定整合方案。

核心结论：**不直接引入 Symphony 运行时，而是将其核心逻辑（WORKFLOW.md 规范 + Orchestrator 模式）移植进 Vibe Center 的三层架构**。

## 当前状态

- 层级: PRD（需求分析层）
- 状态: 见 frontmatter `status` 字段
- 最后更新: 2026-03-16

## 文档导航

### PRD / 需求分析
- [prd-symphony-integration.md](prd-symphony-integration.md)

## 关键约束

- 不引入 Elixir 运行时，整合方案必须保持 Zsh 技术栈。
- Symphony 的 Orchestrator 状态机逻辑通过 `vibe flow` + `vibe task` Shell 能力层实现，不绕过合法通道。
- WORKFLOW.md 规范作为 `AGENTS.md` 的补充格式，不替换现有文档体系。
- 任何新增 Shell 命令必须符合 CLAUDE.md §HARD RULES 第 4 条（最小变更）。
