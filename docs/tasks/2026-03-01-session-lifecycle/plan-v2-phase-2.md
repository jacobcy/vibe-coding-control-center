---
task_id: "2026-03-01-session-lifecycle"
document_type: task-plan
title: "Session Lifecycle - Phase 2"
author: "Codex GPT-5"
created: "2026-03-01"
last_updated: "2026-03-02"
status: completed
related_docs:
  - docs/tasks/2026-03-01-session-lifecycle/README.md
  - docs/tasks/2026-03-02-cross-worktree-task-registry/plan-v1-initial.md
  - .agent/workflows/vibe-new.md
  - skills/vibe-save/SKILL.md
  - skills/vibe-continue/SKILL.md
---

# Session Lifecycle Phase 2 Plan

> **定位**：这是跨 worktree task registry 完成后的第二阶段计划，只覆盖剩余的 session lifecycle 集成项。

## 1. 当前状态

跨 worktree task registry 的基础能力已经落地：

- 共享真源已固定到 `$(git rev-parse --git-common-dir)/vibe/`
- 共享文件已存在：
  - `registry.json`
  - `worktrees.json`
  - `tasks/<task-id>/task.json`
  - `tasks/<task-id>/memory.md`
- 当前 worktree 已有 `.vibe/current-task.json`
- `vibe-new`、`vibe-save`、`vibe-continue` 已接入共享真源概念

因此，Phase 2 不再重复实现共享真源本身，而是只完成 session lifecycle 的剩余闭环。

## 2. Goal

在已有跨 worktree registry 基础上，补齐当前 worktree 的 session 缓存与读取/写回行为，使 `/vibe-new`、`/vibe-save`、`/vibe-continue` 能围绕真实共享真源形成一个可立即使用的本地会话闭环。

## 3. Non-Goals

- 不重新设计 shared registry
- 不改共享真源路径
- 不重写 cross worktree task/subtask 模型
- 不新增 `vibe-switch`
- 不在本阶段实现完整的 `vibe-task` 看板，除非作为明确交付项单独完成

## 4. 已完成 vs 剩余

### 4.1 已完成

- 共享真源路径与分层策略
- `task + optional subtasks` 模型
- `.gitignore` 对 worktree 本地 `.vibe/` 的忽略
- `vibe-new` 的共享真源接线说明
- `vibe-save` / `vibe-continue` 的共享真源读取说明

### 4.2 剩余缺口

1. 本地 `.vibe/` 缓存还不完整
   - 当前只有 `current-task.json`
   - 缺少 `focus.md`
   - 缺少 `session.json`

2. 文档示例字段与真实共享真源字段未完全对齐
   - 实际字段：
     - `schema_version`
     - `worktree_name`
     - `worktree_path`
     - `current_task`
     - `subtask_id`
   - 这些字段必须成为 Phase 2 的唯一读取契约

3. `vibe-task` 仍是设计概念
   - 已明确：本阶段延期，不实现
   - 不得把它写成 Phase 2 的必需依赖

## 5. 真实 Schema 契约

### 5.1 `registry.json`

```json
{
  "schema_version": "v1",
  "generated_at": "2026-03-02T05:49:00+08:00",
  "tasks": [
    {
      "task_id": "2026-03-02-cross-worktree-task-registry",
      "title": "Cross-Worktree Task Registry",
      "status": "done",
      "current_subtask_id": null,
      "assigned_worktree": "wt-claude-refactor",
      "next_step": "Review the completed registry design and decide whether to integrate runtime readers into command implementations.",
      "updated_at": "2026-03-02T05:49:00+08:00"
    }
  ]
}
```

### 5.2 `worktrees.json`

```json
{
  "schema_version": "v1",
  "worktrees": [
    {
      "worktree_name": "wt-claude-refactor",
      "worktree_path": "/Users/jacobcy/src/vibe-center/wt-claude-refactor",
      "branch": "refactor",
      "current_task": "2026-03-02-cross-worktree-task-registry",
      "status": "active",
      "dirty": true,
      "last_updated": "2026-03-02T05:49:00+08:00"
    }
  ]
}
```

### 5.3 `task.json`

```json
{
  "task_id": "2026-03-02-cross-worktree-task-registry",
  "title": "Cross-Worktree Task Registry",
  "status": "done",
  "subtasks": [
    {
      "subtask_id": "task-1-registry-schema",
      "title": "Define shared registry schema",
      "status": "done",
      "next_step": "Shared schema created and validated with jq."
    }
  ],
  "assigned_worktree": "wt-claude-refactor",
  "next_step": "Implementation plan complete; next work is optional command-level integration.",
  "plan_path": "docs/tasks/2026-03-02-cross-worktree-task-registry/plan-v1-initial.md"
}
```

### 5.4 本地 `.vibe/`

Phase 2 完成后，当前 worktree 的 `.vibe/` 应至少包含：

- `current-task.json`
- `focus.md`
- `session.json`

这 3 个文件都必须是缓存，不得成为真源。

## 6. Phase 2 任务拆分

### Task 1: 对齐 `vibe-save` 到真实 schema

**Files**
- Modify: `skills/vibe-save/SKILL.md`

**目标**
- 明确所有读取和写回都使用已落地的真实字段名
- 删除或修正与旧示例不一致的字段表述

**必须对齐的字段**
- `schema_version`
- `current_subtask_id`
- `worktree_name`
- `worktree_path`
- `current_task`
- `subtask_id`

**验证命令**

```bash
rg -n "schema_version|current_subtask_id|worktree_name|worktree_path|current_task|subtask_id" skills/vibe-save/SKILL.md
```

**预期结果**
- 命中所有真实字段
- 不再使用旧字段名 `version`、`name`、`path`、`current_task_id`、`id`

### Task 2: 对齐 `vibe-continue` 到真实 schema

**Files**
- Modify: `skills/vibe-continue/SKILL.md`

**目标**
- 让 `/continue` 的读取说明与真实共享真源字段完全一致
- 保持 `/continue` 只处理当前 worktree

**验证命令**

```bash
rg -n "schema_version|current_subtask_id|worktree_name|worktree_path|current_task|subtask_id" skills/vibe-continue/SKILL.md
```

**预期结果**
- 命中所有真实字段
- 不再使用旧字段名

### Task 3: 补齐本地 `.vibe/` 缓存契约

**Files**
- Modify: `.agent/workflows/vibe-new.md`
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`

**目标**
- 明确 `vibe-new` 创建或刷新：
  - `.vibe/current-task.json`
  - `.vibe/focus.md`
  - `.vibe/session.json`
- 明确 `vibe-save` 刷新 `focus.md` / `session.json`
- 明确 `vibe-continue` 读取这两个缓存文件

**验证命令**

```bash
rg -n "focus.md|session.json|current-task.json" .agent/workflows/vibe-new.md skills/vibe-save/SKILL.md skills/vibe-continue/SKILL.md
find .vibe -maxdepth 2 -type f | sort
```

**预期结果**
- 三个文件在文档契约中均有明确职责
- 本地 `.vibe/` 最终至少有 3 个文件

### Task 4: 明确 `vibe-task` 是否纳入本阶段

**Files**
- Modify: `docs/tasks/2026-03-01-session-lifecycle/plan-v2-phase-2.md`

**目标**
- 将 `vibe-task` 的状态写成显式结论，避免继续保持二义性

**决策**
- Phase 2 明确延期 `vibe-task`
- `vibe-task` 不作为 Phase 2 阻断项
- 原因：当前最小闭环是本地进入、保存、继续，不是全局看板

**验证命令**

```bash
rg -n "vibe-task|延期|本阶段" docs/tasks/2026-03-01-session-lifecycle/plan-v2-phase-2.md
```

**预期结果**
- `vibe-task` 的状态被明确为“本阶段延期，不作为阻断项”

## 7. Files To Modify

- `.agent/workflows/vibe-new.md`
- `skills/vibe-save/SKILL.md`
- `skills/vibe-continue/SKILL.md`
- `docs/tasks/2026-03-01-session-lifecycle/plan-v2-phase-2.md`

## 8. Files Not To Modify

- `skills/vibe-orchestrator/SKILL.md`
- `$(git rev-parse --git-common-dir)/vibe/registry.json` 的路径设计
- `$(git rev-parse --git-common-dir)/vibe/worktrees.json` 的路径设计
- task/subtask 模型

## 9. Reproducible Validation

1. 核对真实共享真源：

```bash
COMMON=$(git rev-parse --git-common-dir)
jq . "$COMMON/vibe/registry.json"
jq . "$COMMON/vibe/worktrees.json"
jq . "$COMMON/vibe/tasks/2026-03-02-cross-worktree-task-registry/task.json"
```

Expected:
- 全部通过

2. 核对本地缓存契约：

```bash
find .vibe -maxdepth 2 -type f | sort
```

Expected:
- 至少包含 `current-task.json`
- Phase 2 完成后应包含 `focus.md` 与 `session.json`

3. 核对 skill/workflow 字段契约：

```bash
rg -n "schema_version|current_subtask_id|worktree_name|worktree_path|current_task|subtask_id" .agent/workflows/vibe-new.md skills/vibe-save/SKILL.md skills/vibe-continue/SKILL.md
```

Expected:
- 三处文档都与真实 schema 一致

## 10. Expected Result

- 当前 worktree 的 session lifecycle 闭环成立：
  - `vibe-new` 进入
  - `vibe-save` 保存
  - `vibe-continue` 恢复
- 所有 reader/writer 都使用真实共享真源字段
- 本地 `.vibe/` 缓存完整且仍然是非真源
- 不重新打开 cross-worktree registry 的设计范围

## 11. Change Summary

| File | Type | Approx Change |
|------|------|---------------|
| `.agent/workflows/vibe-new.md` | modify | `+8~15` |
| `skills/vibe-save/SKILL.md` | modify | `+10~20` |
| `skills/vibe-continue/SKILL.md` | modify | `+10~20` |
| `docs/tasks/2026-03-01-session-lifecycle/plan-v2-phase-2.md` | modify | `rewrite` |
| **Total** | 4 files | `~+30~55` |

## 12. Execution Decision

这个 Phase 2 plan 在补齐以上 4 项后即可立即执行。当前执行结论为：

1. 本地 `.vibe/` 缓存是必须完成项
2. schema 示例与真实字段完全对齐是必须完成项
3. `vibe-task` 已明确延期，不属于本阶段阻断项

其中 1 和 2 完成后，Phase 2 即可收敛；`vibe-task` 留待后续独立交付。
