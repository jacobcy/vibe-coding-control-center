---
name: vibe-continue
description: Use when the user wants to resume previous work, says "/continue", or starts a new session and wants to load saved context. Reads task.md and memory/ to restore state.
---

# /continue - Resume Saved Tasks

继续上次保存的任务。自动读取 task.md 和 memory/ 中的状态，识别未完成的任务。

**核心原则:** 无缝衔接，延续进度。

**Announce at start:** "我正在使用 continue 技能来恢复上次保存的任务。"

## Current Worktree Model

`/continue` 只继续当前 worktree 绑定的 current task，不提供跨 worktree 选择。

优先读取：

- `.vibe/current-task.json`：当前 current task 指针
- `.vibe/focus.md`：当前 worktree 的聚焦摘要缓存
- `.vibe/session.json`：当前 worktree 的短期会话缓存
- `$(git rev-parse --git-common-dir)/vibe/registry.json`：包含 `schema_version`、task 摘要、`next_step`、`current_subtask_id`
- `$(git rev-parse --git-common-dir)/vibe/worktrees.json`：包含 `schema_version`、`worktree_name`、`worktree_path`、`current_task`、branch、`dirty/clean`
- `$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/task.json`：task/subtask 详情，subtask 以 `subtask_id` 标识
- `$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/memory.md`：共享记忆真源

**本地工作区缓存重构**：
- `.agent/context/memory.md` (Tracked)：作为人类与AI共享的高阶认知索引池，存放在版本控制中。
- `.agent/context/task.md` (Untracked)：被放入 `.gitignore`。完全作为当前物理 worktree 短期进度的草稿本。如果冷启动时文件缺失，`/vibe-continue` 需要自动通过读取大盘 `registry.json` 和 `focus.md` 重新组装并拉取一份到本地。

## Schema 契约

`/continue` 只使用以下真实字段名：

- `registry.json`：`schema_version`、`task_id`、`current_subtask_id`、`assigned_worktree`、`next_step`
- `worktrees.json`：`schema_version`、`worktree_name`、`worktree_path`、`current_task`、`dirty`、`last_updated`
- `task.json`：`task_id`、`status`、`subtasks[].subtask_id`、`assigned_worktree`、`next_step`、`plan_path`
- `.vibe/session.json`：`worktree_name`、`current_task`、`current_subtask_id`、`saved_at`

不得使用旧字段名 `version`、`name`、`path`、`current_task_id`、`id`。

## 工作流程

### Step 0: Shell-Level Resume
 
 ```bash
 vibe flow continue
 ```
 
 运行 `vibe flow continue` 来从共享存储中恢复任务状态与上下文。
 
 ### Step 1: 恢复方案（根据记忆内容）读取当前 task 指针与共享状态

```bash
# 读取当前 worktree 指针和共享 task registry
pointer_file=".vibe/current-task.json"
focus_file=".vibe/focus.md"
session_file=".vibe/session.json"
task_file=".agent/context/task.md"
memory_index=".agent/context/memory.md"
governance_file=".agent/governance.yaml"
```

分析以下内容：
- **Current Task**: 当前 worktree 绑定的任务
- **Current Subtask**: 当前进行中的 `current_subtask_id`
- **Next Step**: 共享 registry 中记录的下一步动作
- **Focus Summary**: `.vibe/focus.md` 中的聚焦摘要
- **Session Cache**: `.vibe/session.json` 中最近一次保存的短期会话状态
- **Dirty State**: 当前 worktree 是否 dirty
- **Governance Phase**: 当前处于探索期 (`exploration`) 还是收敛期 (`convergence`)。

### Step 2: 识别当前 task 与共享 memory

从 `.vibe/current-task.json` 读取 `task_id`，再加载：

```text
$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/task.json
$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/memory.md
```

### Step 3: 加载上下文

为当前 task 加载：
1. **Summary** - task 标题与摘要
2. **Key Decisions** - 共享 memory 中的相关决策
3. **Subtasks Summary** - subtask 状态概览（按 `subtask_id`）
4. **Next Step** - 当前下一步动作
5. **Worktree View** - `worktree_path`、branch、dirty/clean
6. **Local Cache View** - `focus.md` / `session.json` 的摘要

*如果 `.agent/context/task.md` 不存在或为空 (比如因为它是 git-ignored 被新切出来的 worktree 跳过的)*：
  - 自动创建 `.agent/context/task.md`。
  - 将上一步加载的 Summary / Next Step / Dirty 等从 `registry.json` 当中取得的最新状态渲染进它。

### Step 4: 输出继续报告

```
📋 Session Resume

📁 Current Worktree
  • path: <worktree-path>
  • branch: <branch>
  • state: dirty|clean

📌 Current Task
  • [ ] <task-id>: <title> (in progress)
  • current subtask: <subtask-id>
  • next step: <next-step>

📂 Context Loaded:
  • .vibe/current-task.json
  • .vibe/focus.md
  • .vibe/session.json
  • $(git rev-parse --git-common-dir)/vibe/registry.json
  • $(git rev-parse --git-common-dir)/vibe/worktrees.json
  • $(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/task.json
  • $(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/memory.md
  • .agent/context/task.md

💡 Suggested Action:
  → 继续执行 <task-id>: <next-step>
  → 运行: /superpowers:executing-plans docs/plans/<plan-file>
```

### Step 5: 提供继续选项

根据任务状态提供选项：

| 状态 | 建议 |
|------|------|
| 有计划文件 | 运行 `/superpowers:executing-plans <plan>` |
| 有 current task | 直接继续当前 worktree 绑定的任务 |
| pointer 缺失 | 回退读取 `.agent/context/task.md` 并提示恢复 `.vibe/current-task.json` |

## 文件格式依赖

### `.vibe/current-task.json` 结构

```json
{
  "task_id": "<task-id>",
  "task_path": "<git-common-dir>/vibe/tasks/<task-id>/task.json",
  "registry_path": "<git-common-dir>/vibe/registry.json",
  "worktree_name": "<worktree-name>",
  "updated_at": "YYYY-MM-DDTHH:MM:SS+TZ:TZ"
}
```

### task.json 关键字段

- `status`
- `subtasks`
- `assigned_worktree`
- `next_step`
- `plan_path`

### worktrees.json / registry.json 关键字段

- `schema_version`
- `worktree_name`
- `worktree_path`
- `current_task`
- `current_subtask_id`

## 与 /save 的关系

```
会话 A                        会话 B
   │                            │
   ├─ 执行任务                  ├─ /continue
   ├─ 遇到中断点                │  ↓
   ├─ /save                     │  读取 task.md
   │  ↓                         │  读取 memory/<topic>.md
   │  保存状态                  │  恢复上下文
   │                            │  ↓
   └─ 结束会话                  └─ 继续执行
```

## 实现优先级

1. **P0**: 读取 `.vibe/current-task.json` 并识别当前 worktree 绑定任务
2. **P0**: 加载共享 `task.json` 与共享 `memory.md`
3. **P1**: 输出 current task / current subtask / next step / dirty 状态
4. **P2**: 自动建议 executing-plans，如果 `plan_path` 存在

## 示例输出

```
📋 Session Resume

📁 Current Worktree
  • path: /path/to/wt-claude-refactor
  • branch: refactor
  • state: dirty

📌 Current Task
  • [ ] 2026-03-02-cross-worktree-task-registry: Cross-Worktree Task Registry
  • current subtask: task-4-monitoring-and-save-view
  • next step: Update vibe-save and vibe-continue to read current-task pointer and shared registry fields.

📂 Context Loaded:
  • .vibe/current-task.json
  • .vibe/focus.md
  • .vibe/session.json
  • $(git rev-parse --git-common-dir)/vibe/tasks/2026-03-02-cross-worktree-task-registry/task.json
  • $(git rev-parse --git-common-dir)/vibe/tasks/2026-03-02-cross-worktree-task-registry/memory.md
  • .agent/context/task.md

💡 Suggested Action:
  → 继续当前 worktree 任务
  → 运行计划: /superpowers:executing-plans docs/plans/2026-03-02-cross-worktree-task-registry/plan-v1-initial.md
```

## 设计决策

1. **当前 worktree 优先** - `/continue` 只继续当前指针绑定的 task
2. **共享真源优先** - task/subtask/next step 以共享 registry 和 task.json 为准
3. **compat 层保留** - `.agent/context/*` 作为入口索引，逐步迁移
4. **与 /save 互补** - `/save` 回写共享状态，`/continue` 读取共享状态
