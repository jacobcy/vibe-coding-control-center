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
- `$(git rev-parse --git-common-dir)/vibe/registry.json`：task 摘要、`next_step`、current subtask
- `$(git rev-parse --git-common-dir)/vibe/worktrees.json`：当前 worktree 路径、branch、`dirty/clean`
- `$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/task.json`：task/subtask 详情
- `$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/memory.md`：共享记忆真源

`.agent/context/task.md` 和 `.agent/context/memory.md` 作为兼容层保留，用于旧 skill 和入口索引。

## 工作流程

### Step 1: 读取当前 task 指针与共享状态

```bash
# 读取当前 worktree 指针和共享 task registry
pointer_file=".vibe/current-task.json"
task_file=".agent/context/task.md"
memory_index=".agent/context/memory.md"
governance_file=".agent/governance.yaml"
```

分析以下内容：
- **Current Task**: 当前 worktree 绑定的任务
- **Current Subtask**: 当前进行中的 subtask
- **Next Step**: 共享 registry 中记录的下一步动作
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
3. **Subtasks Summary** - subtask 状态概览
4. **Next Step** - 当前下一步动作
5. **Worktree View** - path、branch、dirty/clean

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
