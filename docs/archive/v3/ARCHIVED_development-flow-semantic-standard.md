---
document_type: standard
title: Development Flow Branch Semantic Standard
status: active
scope: branch-naming
authority:
  - branch-semantic-source-of-truth
author: AI Agent
created: 2026-04-03
related_docs:
  - docs/standards/v3/skill-standard.md
  - docs/standards/glossary.md
---

# 开发流分支语义标准

本文档定义两条分支命名语义，用于区分人机协作与自动化调度。

## 1. 分支命名规则

| 分支模式 | 语义 | 启动方式 | 场景 |
|---|---|---|---|
| `dev/issue-<id>` | 人机协作分支 | `/vibe-new`（skill） | 开发者主导的功能开发、bug 修复 |
| `task/issue-<id>` | 自动化分支 | `vibe3 run` / orchestra / manager | Agent 自主执行、CI 触发、批量任务 |

## 2. 判断规则

- 通过 `/vibe-new` 或 `/vibe-start` 启动的任务，使用 `dev/issue-<id>` 分支
- 通过 `vibe3 run`、heartbeat、orchestra 分诊启动的任务，使用 `task/issue-<id>` 分支
- 已有的 `task/` 分支不强制迁移；新创建的人机协作分支统一使用 `dev/` 前缀

## 3. 约束

- 分支前缀只有 `dev/` 和 `task/` 两种，不引入新前缀
- `main` 分支不参与此语义（始终是集成分支）
- 临时分支（如 `hotfix/`、`release/`）不在本标准范围内
