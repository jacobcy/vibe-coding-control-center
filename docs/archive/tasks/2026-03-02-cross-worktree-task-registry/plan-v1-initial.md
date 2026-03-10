---
task_id: "2026-03-02-cross-worktree-task-registry"
document_type: task-plan
title: "Cross-Worktree Task Registry - Plan V1"
author: "Codex GPT-5"
created: "2026-03-02"
last_updated: "2026-03-02"
related_docs:
  - docs/tasks/2026-03-02-cross-worktree-task-registry/README.md
  - docs/standards/git-workflow-standard.md
  - docs/tasks/2026-03-01-session-lifecycle/plan-v1-checkpoint.md
---

# Cross-Worktree Task Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 设计并实现一个跨 worktree 的共享任务注册表，让用户可以看到每个 worktree 当前绑定的 task、subtask 状态和下一步动作，并据此决定进入哪个 worktree 工作。

**Architecture:** 引入跨 worktree 的共享状态目录，集中保存 task registry、subtask 进度、worktree 绑定关系和共享 memory；各 worktree 通过本地 `.vibe/` 持有当前任务指针与聚焦缓存，该目录加入 `.gitignore`，不作为真源。现有 session checkpoint 后续改为读取共享 registry 中与当前 worktree 绑定的 task。

**Tech Stack:** Markdown task docs, JSON/YAML shared state design, git worktree metadata, existing `.agent` workflows

---

## Goal

- 定义跨 worktree 的共享任务真源位置与结构。
- 定义 `worktree -> current task` 绑定模型。
- 定义 `task -> optional subtasks` 的执行模型。
- 为后续 session checkpoint、`/vibe-continue` 和任务监控提供统一上游。

## Non-Goals

- 不在本计划中直接实现 `session checkpoint`。
- 不在本计划中改造所有 `skills/*` 读取路径。
- 不引入数据库、守护进程或网络服务。
- 不做多个 worktree 同时编辑同一 task 的并发控制。
- 不新增 `vibe-switch`，不支持在单次对话里跨 worktree 切换执行。

## Design Decision

### Shared Source of Truth

- 共享任务真源不能只放在当前 worktree 的 `.vibe/`，因为它会随 worktree 分叉，无法天然跨 worktree 共享。
- 当前仓库的共享运行时状态固定放在 `$(git rev-parse --git-common-dir)/vibe/`。
- `~/.vibe/` 只用于全局配置、默认行为和可选的跨仓库索引，不承载当前仓库的任务真源。
- 当前 worktree 的 `.vibe/` 仅作为本地聚焦缓存层，必须加入 `.gitignore`。

### Registry Model

- `registry.json`: 所有 task 的全局摘要索引
- `worktrees.json`: 所有 worktree 与当前 task 的映射
- `tasks/<task-id>/task.json`: 单个 task 的真源
- `tasks/<task-id>/memory.md`: 单个 task 的共享记忆
- `worktree/.vibe/current-task.json`: 当前 worktree 的任务指针
- `worktree/.vibe/focus.md`: 当前任务的聚焦摘要，可重建
- `worktree/.vibe/session.json`: 当前 worktree 的短期会话缓存

### Task Model

- 每个 task 可以没有 subtasks，也可以包含多个 subtasks
- task 的完成由 subtasks 完成情况或整体状态驱动
- `worktree.current_task` 同时只能有一个
- `vibe-continue` 仅继续当前 worktree 的 `current_task`
- 跨 worktree 总览交由未来的 `vibe-task` 负责

### Status Enum V1

- `task.status` / `subtask.status`
  - `todo`
  - `in_progress`
  - `blocked`
  - `done`
  - `archived`
- `worktree.status`
  - `active`
  - `idle`
  - `missing`

## Proposed Files

- Create: `$(git rev-parse --git-common-dir)/vibe/`
- Create: `$(git rev-parse --git-common-dir)/vibe/registry.json`
- Create: `$(git rev-parse --git-common-dir)/vibe/worktrees.json`
- Create: `$(git rev-parse --git-common-dir)/vibe/tasks/`
- Modify: `.gitignore`
- Modify: `.agent/workflows/vibe-new.md`
- Modify: `skills/vibe-continue/SKILL.md`
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `.agent/context/task.md` or replace with pointer-only format
- Modify: `.agent/context/memory.md` or replace with pointer-only format

## Task 1: 定义共享 registry schema

**Files:**
- Create: `$(git rev-parse --git-common-dir)/vibe/registry.json`
- Create: `$(git rev-parse --git-common-dir)/vibe/worktrees.json`
- Create: `$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/task.json`

**Step 1: 设计 registry.json**

字段至少包含：
- `task_id`
- `title`
- `status`
- `current_subtask_id`
- `assigned_worktree`
- `next_step`
- `updated_at`

**Step 2: 设计 task.json**

字段至少包含：
- `task_id`
- `title`
- `status`
- `subtasks`
- `assigned_worktree`
- `next_step`
- `plan_path`

**Step 3: 设计 worktrees.json**

字段至少包含：
- `worktree_name`
- `worktree_path`
- `branch`
- `current_task`
- `status`
- `dirty`
- `last_updated`

**Step 4: 定义校验方式**

Run:
```bash
jq . <shared-registry>/registry.json
jq . <shared-registry>/worktrees.json
jq . <shared-registry>/tasks/<task-id>/task.json
```

Expected:
- 两个文件都能被 `jq` 正常解析
- registry 只保留摘要而非完整 task 正文
- task 记录能表达 optional subtasks
- worktree 记录能表达单 current task 模型和工作树状态

## Task 2: 设计 `vibe-new` 的任务创建与 worktree 绑定规则

**Files:**
- Modify: `.agent/workflows/vibe-new.md`
- Modify: `.agent/context/task.md`
- Modify: `.gitignore`

**Step 1: 新任务进入规则**

- 无论在哪个 worktree 讨论出新任务，都先落到共享真源
- 然后创建或分配目标 worktree
- 在目标 worktree 生成本地 `.vibe/current-task.json`

**Step 2: 本地聚焦缓存规则**

- 当前 worktree 的 `.vibe/` 保存任务指针、focus 摘要、session 缓存
- `.vibe/` 加入 `.gitignore`
- `.vibe/` 内文件可随时重建，不作为真源
- `current-task.json` 只保存任务指针
- `focus.md` 只保存聚焦摘要
- `session.json` 只保存短期会话缓存

**Step 3: 决策输出**

Run:
```bash
rg -n "subtask|current task|\\.vibe|gitignore|worktree" .agent/workflows/vibe-new.md .agent/context/task.md .gitignore
```

Expected:
- 文档中明确使用 task/subtask 模型
- 明确 `.vibe/` 是本地缓存且被忽略
- 明确新任务先落共享真源，再绑定 worktree

## Task 3: 设计共享 memory 迁移策略

**Files:**
- Modify: `.agent/context/memory.md`
- Create: shared `memory/`

**Step 1: 真源迁移策略**

- `.agent/context/memory.md` 从真源改为入口索引或兼容层
- 共享 memory 迁移到统一真源目录
- 当前 worktree 的 `.vibe/` 仅保留聚焦摘要，不保留共享 memory 真源

**Step 2: 兼容策略**

- 现有 skill 在未完全迁移前，允许读取 `.agent/context/*`
- 新设计需要定义过渡期，避免一次性改爆所有 skill

**Step 3: 验证迁移设计**

Run:
```bash
rg -n "shared|pointer|compat|memory" docs/tasks/2026-03-02-cross-worktree-task-registry/plan-v1-initial.md
```

Expected:
- 明确写出真源、兼容层、迁移边界

## Task 4: 定义监控与保存视图

**Files:**
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`

**Step 1: 监控视图**

- 为未来 `vibe-task` 预留总览字段：
  - 路径
  - branch
  - current task
  - subtasks summary
  - next step
  - dirty/clean

**Step 2: 保存与恢复职责**

- `vibe-save` 从当前 worktree 的 `.vibe/current-task.json` 读取任务指针
- `vibe-save` 将状态回写共享真源，并可刷新本地 `.vibe/`
- `vibe-continue` 只继续当前 worktree 绑定的 task，不提供跨 worktree 选择

**Step 3: 验证输出字段**

Run:
```bash
rg -n "current task|subtask|next step|dirty|shared|\\.vibe" skills/vibe-continue/SKILL.md skills/vibe-save/SKILL.md
```

Expected:
- 至少覆盖当前 worktree 恢复和全局总览所需的关键字段

## Risks

### 风险 1: 共享真源路径选型不当

- **影响**: 共享目录可能要么不能跨 worktree 共享，要么不利于审查
- **对策**: 固定使用 `$(git rev-parse --git-common-dir)/vibe/`，并让仓库内文档只保存 schema 和说明
- **回滚条件**: 若共享路径无法稳定访问，先退回 pointer-only 方案，只做 worktree 绑定不做共享 memory

### 风险 2: 现有 skill 全部读取 `.agent/context/*`

- **影响**: 一次性迁移会波及多个 skill
- **对策**: 先定义 pointer/compat 层，再逐步迁移
- **回滚条件**: 若兼容层复杂度超过预期，暂停迁移，只先做 registry 读取

### 风险 3: task/subtask 边界由人工维护，可能不一致

- **影响**: subtask 粒度可能过粗或过细
- **对策**: 初版只要求支持 optional subtasks，不强制拆分
- **回滚条件**: 如果 subtask 维护成本过高，允许只维护 task-level 状态

## Test Command

```bash
jq . <shared-registry>/tasks.json
jq . <shared-registry>/worktrees.json
rg -n "subtask|current task|\\.vibe|gitignore|worktree" .agent/workflows/vibe-new.md .gitignore
git worktree list
```

## Expected Result

- 用户能看到“有哪些 worktree、每个 worktree 当前在做什么 task、subtask 进展和下一步是什么”。
- `vibe-new` 负责新任务落共享真源并绑定目标 worktree。
- `vibe-continue` 只恢复当前 worktree 的 task。
- 后续 session checkpoint 可以作为该 registry 的下游能力，而不是继续做独立状态系统。

## Change Summary

| File Group | Type | Approx Change |
|-----------|------|---------------|
| shared registry | new | `+40~80` |
| `.agent/workflows/vibe-new.md` | modify | `+20~35` |
| `skills/vibe-{save,continue}.SKILL.md` | modify | `+30~60` |
| `.agent/context/{task,memory}.md` | modify | `+10~30` |
| `.gitignore` | modify | `+1~3` |
| **Total** | 7-9 files | `~+110~210` |

## Dependency Note

- 当前 [session-checkpoint plan](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/tasks/2026-03-01-session-lifecycle/plan-v1-checkpoint.md) 应暂停执行。
- 应先完成本任务的设计与真源决策，再重写或缩减 session checkpoint 的实现计划。
