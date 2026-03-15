---
document_type: plan
title: Phase 02 - Flow & Task State (SQLite)
status: draft
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
---

# Phase 02: Flow & Task State (SQLite)

**Goal**: Implement the state management layer for Flows and Tasks using SQLite.

## ⚠️ 实现规范（强制）

**必须遵守**: [docs/v3/implementation-spec-phase2.md](../implementation-spec-phase2.md)

该文档定义了：
- ✅ 必须使用的技术栈（typer, rich, pydantic, loguru）
- ✅ 强制的目录结构
- ✅ 严格的分层职责
- ✅ 类型注解要求
- ✅ 测试要求
- ✅ 代码量限制

**违反规范将导致验收失败，不予合并。**

## 1. Context Anchor (Optional)

If you require more than technical scope, refer to the [Vibe 3.0 Master Plan](v3-rewrite-plan.md).

## 2. Pre-requisites (Executor Entry)

- [ ] Executor 01 has completed `bin/vibe3` skeleton.
- [ ] `scripts/python/vibe_core.py` is accessible.

## 3. Database Schema (Source of Truth)

Refer to `scripts/python/lib/store.py` for the current table definitions.
- `flow_state`: Primary state for branch-centric flows.
- `task_links`: Mapping between local tasks and remote issue URLs.

## 4. Technical Requirements

- **Service Layer**: Implement `Vibe3Store` to handle all SQL queries.
- **Manager Layer**: `FlowManager` and `TaskManager` must use `Vibe3Store` for persistence.
- **State Transitions**: Implement logic for `new`, `bind`, and `status`.

## 5. Success Criteria (Technical)

- [ ] `vibe3 flow new <slug> --task <id>` successfully inserts a record into SQLite.
- [ ] `vibe3 task link <url>` updates the correct task record with the remote link.
- [ ] `vibe3 flow status --json` correctly aggregates state and returns valid JSON.
- [ ] All database transactions are properly closed/handled in the Service layer.
- [ ] 0 unit testing failures for the `Manager` modules.