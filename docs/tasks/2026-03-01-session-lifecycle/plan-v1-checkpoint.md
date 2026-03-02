---
document_type: task-plan
title: Session Checkpoint 实施计划
date: 2026-03-01
last_updated: 2026-03-02
status: paused
author: Codex GPT-5
related_docs:
  - docs/tasks/2026-03-01-session-lifecycle/README.md
  - .agent/workflows/vibe-new.md
  - skills/vibe-save/SKILL.md
  - skills/vibe-continue/SKILL.md
  - .agent/context/task.md
  - .agent/context/memory.md
---

# Session Checkpoint Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `/vibe-new`、`/vibe-save`、`/vibe-continue` 增加一个最小可用的 session checkpoint 机制，让新 session 能快速恢复最近一次任务上下文。

**Architecture:** 保留 `.agent/context/task.md` 和 `.agent/context/memory.md` 作为人类可读真源；新增一个轻量 `.agent/context/status.json` 作为恢复缓存层。`/vibe-new` 负责初始化 checkpoint，`/vibe-save` 负责更新 checkpoint，`/vibe-continue` 负责读取并展示 checkpoint，不改 `vibe-orchestrator`，也不做 Gate 级实时持久化。

**Tech Stack:** Markdown workflow/skill docs, JSON (`jq` 校验), Zsh project conventions

---

> **状态说明：** 该计划保留为早期设计记录。由于后续引入了 cross-worktree task registry，本计划应暂停执行，不能再作为当前权威实现方案。

## Goal

- 为当前真实入口 [`.agent/workflows/vibe-new.md`](../../../../.agent/workflows/vibe-new.md) 接上 session checkpoint。
- 让 [`skills/vibe-save/SKILL.md`](../../../../skills/vibe-save/SKILL.md) 在保存会话时写入最小状态。
- 让 [`skills/vibe-continue/SKILL.md`](../../../../skills/vibe-continue/SKILL.md) 在恢复会话时优先读取该状态。
- 将实现范围控制在 4 个文件内，避免扩展成新的生命周期子系统。

## Non-Goals

- 不新增 `vibe-init`。
- 不修改 [`skills/vibe-orchestrator/SKILL.md`](../../../../skills/vibe-orchestrator/SKILL.md)。
- 不记录每个 Gate 的实时 `progress`。
- 不让 `status.json` 成为权威状态源。
- 不修改 `bin/` 或 `lib/` Shell 代码。

## Files To Modify

- Create: `.agent/context/status.json`
- Modify: `.agent/workflows/vibe-new.md`
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`

## Checkpoint Schema

```json
{
  "version": 1,
  "last_session_at": "",
  "current_task": {
    "id": "",
    "framework": "",
    "plan_path": ""
  },
  "resume": {
    "source_of_truth": [
      ".agent/context/task.md",
      ".agent/context/memory.md"
    ],
    "next_step": "",
    "last_actor": ""
  },
  "git": {
    "branch": "",
    "dirty": false,
    "head": ""
  }
}
```

## Task 1: 创建初始 checkpoint 文件

**Files:**
- Create: `.agent/context/status.json`

**Step 1: 创建最小 schema**

- 写入空白但合法的 JSON 结构。
- `source_of_truth` 固定指向 `task.md` 与 `memory.md`。
- 不写 `current_gate`、`progress`、`environment` 等易漂移字段。

**Step 2: 校验 JSON 格式**

Run:
```bash
jq . .agent/context/status.json
```

Expected:
- 命令退出码为 `0`
- 输出格式化 JSON，且包含 `version`, `current_task`, `resume`, `git`

## Task 2: 调整 `/vibe-new` 入口为 checkpoint 初始化点

**Files:**
- Modify: `.agent/workflows/vibe-new.md`

**Step 1: 在 workflow 中明确真实入口职责**

- 在调用 `vibe-orchestrator` 之前增加 session startup 说明：
  - 读取已有 `status.json`
  - 刷新 `current_task.id`
  - 刷新 `resume.last_actor = "vibe-new"`
  - 刷新当前 git 摘要

**Step 2: 保持现有入口契约**

- 仍由 workflow 作为 `/vibe-new` 用户入口。
- 不新建平行入口，不让 `skills/vibe-new/SKILL.md` 成为必需依赖。

**Step 3: 校验入口文档已接线**

Run:
```bash
rg -n "status.json|session startup|vibe-orchestrator" .agent/workflows/vibe-new.md
```

Expected:
- 至少命中 3 处
- 同时包含 `status.json` 和 `vibe-orchestrator`

## Task 3: 扩展 `/vibe-save` 为 checkpoint 写入点

**Files:**
- Modify: `skills/vibe-save/SKILL.md`

**Step 1: 增加 status.json 写入职责**

- 在现有 `memory.md` / `task.md` 更新之后，新增 `status.json` 更新步骤：
  - `last_session_at = now`
  - `resume.next_step = 当前明确的下一步`
  - `resume.last_actor = "vibe-save"`
  - `git.branch`, `git.dirty`, `git.head`

**Step 2: 保持真源分层**

- 明确写出：`task.md` 和 `memory.md` 仍是真源，`status.json` 仅用于恢复加速。

**Step 3: 校验保存技能文档**

Run:
```bash
rg -n "status.json|next_step|source_of_truth|last_session_at" skills/vibe-save/SKILL.md
```

Expected:
- 至少命中 4 处
- 明确出现“真源”或等价描述

## Task 4: 扩展 `/vibe-continue` 为 checkpoint 读取点

**Files:**
- Modify: `skills/vibe-continue/SKILL.md`

**Step 1: 调整读取顺序**

- 先读 `.agent/context/status.json`
- 再回退到 `.agent/context/task.md` 与 `.agent/context/memory.md`
- 如果 `status.json` 缺失或过期，继续按旧流程工作，不阻断

**Step 2: 调整输出内容**

- 在恢复报告中增加：
  - 当前任务 ID
  - 上次会话时间
  - 推荐下一步
  - 真源文件路径提示

**Step 3: 校验恢复技能文档**

Run:
```bash
rg -n "status.json|next_step|source_of_truth|fallback" skills/vibe-continue/SKILL.md
```

Expected:
- 至少命中 4 处
- 明确出现回退策略

## Reproducible Validation

1. 在实现完成后运行：
```bash
jq -e '.version == 1 and .resume.source_of_truth[0] == ".agent/context/task.md"' .agent/context/status.json
```
Expected:
- 输出 `true`

2. 进行一次人工 dry-run：
- 触发 `/vibe-new session-checkpoint`
- 触发 `/vibe-save`
- 新 session 触发 `/vibe-continue`

Expected:
- `/vibe-save` 的摘要包含 `.agent/context/status.json`
- `/vibe-continue` 的恢复报告包含 `current_task` 与 `next_step`
- `task.md`/`memory.md` 仍被表述为真源

## Expected Result

- `/vibe-new` 不再是只调用 orchestrator 的空入口，而是会初始化 session checkpoint。
- `/vibe-save` 和 `/vibe-continue` 通过 `status.json` 建立最小恢复闭环。
- 整体不引入新 skill，不改 Shell，不增加 Gate 级状态同步复杂度。

## Change Summary

| File | Type | Approx Change |
|------|------|---------------|
| `.agent/context/status.json` | new | `+22` |
| `.agent/workflows/vibe-new.md` | modify | `+10/-2` |
| `skills/vibe-save/SKILL.md` | modify | `+18/-4` |
| `skills/vibe-continue/SKILL.md` | modify | `+20/-6` |
| **Total** | 4 files | `~+70/-12` |

## Execution Notes

- 这是一个单逻辑变更，执行阶段应合并为 1 个 commit。
- 若实现中发现必须修改 `skills/vibe-orchestrator/SKILL.md` 或新增 `vibe-init`，视为计划失效，停止执行并回到讨论阶段。
