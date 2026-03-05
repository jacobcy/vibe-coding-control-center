---
name: vibe-save
description: Use when the user wants to save session context, says "/save", or when ending a session and you want to preserve work state. Saves tasks, decisions, and solutions to project memory.
---

# /save - Session Context Save

会话上下文保存命令。在会话结束前自动提取和保存有价值的信息到项目记忆系统。

**核心原则:** 保存现在，延续未来。
**审阅优先原则:** 在任何写入操作之前，必须优先审阅目标文件的已有内容。若发现已有内容存在陈旧、错误或冲突（如状态不一致、陈旧的 next_step 等），必须先进行修正对齐，然后再追加或更新本次会话的新内容。不允许无视已有错误直接堆砌新内容。


**Announce at start:** "我正在使用 save 技能来保存本次会话的上下文。"

## Shared Task Source
 
1. **定位**: 根据当前目录路径 `$(pwd)` 在 `$(git rev-parse --git-common-dir)/vibe/worktrees.json` 中定位当前 `task_id`。
2. **真源**:
   - `registry.json`：包含 task 摘要与全局索引。
   - `worktrees.json`：worktree 状态与 task 绑定。
   - `shared/`：存放跨 worktree 的流程状态文件。
 
**指令**: 物理层状态已通过 `vibe flow status` 自动对齐。认知层保存需调用 `vibe task update --next-step ...` 沉积当前进度。

`/save` 只处理当前 worktree 绑定的 current task。

## Schema 契约

`/save` 只使用以下真实字段名，不使用旧示例字段：

- `registry.json`：`schema_version`、`task_id`、`current_subtask_id`、`assigned_worktree`、`next_step`
- `worktrees.json`：`schema_version`、`worktree_name`、`worktree_path`、`current_task`、`dirty`、`last_updated`
- `task.json`：`task_id`、`status`、`subtasks[].subtask_id`、`assigned_worktree`、`next_step`、`plan_path`

不得回退到旧字段名 `version`、`name`、`path`、`current_task_id`、`id`。

## 文件职责分离

| 文件 | 职责 | 内容 |
| ---- | ---- | ---- |
| `memory.md` | 认知对齐目录 | 达成的概念共识、关键定义、文件目录索引 |
| `memory/<topic>.md` | 复杂概念展开 | 深入的概念定义、设计决策（可选，按需创建） |
| `task.md` | 任务状态 | 已完成的工作 + 待办事项 |

**核心区分：**
- `.agent/context/memory.md` = **[Tracked]** 跨项目、跨任务的人类/AI公共知识池与共识（我们达成了什么架构规约）。
- `.agent/context/task.md` = **[Untracked]** 仅仅是当前物理环境（Worktree）中的临时草稿本和 AI 上下文切片区（我们在这个分支里做了什么、Blockers 是什么）。不被 Git 追踪。

## 工作流程

### Step 1: 分析对话内容

回顾本次会话，识别：

1. **认知对齐** - 达成了哪些概念共识？（写入 memory.md）
2. **复杂概念** - 是否有需要深入展开的概念？（按需写入 memory/<topic>.md）
3. **任务状态** - 完成了什么？待办是什么？（写入 task.md）

### Step 2: 读取当前 task 指针与共享状态

先读取 `.vibe/current-task.json`，确认：

- `task_id`
- `task_path`
- `registry_path`
- `worktree_name`

再从共享真源读取：

- `schema_version`
- `current_task` / `current_subtask_id`
- `worktree_path`
- next step
- subtasks summary（`subtasks[].subtask_id`）
- shared memory 路径
- 当前 worktree 的 `dirty/clean` 状态

### Step 3: 更新认知对齐目录

更新 `.agent/context/memory.md`：

1. **审查**: 完整阅读 `memory.md`，检查现有的概念共识、定义和索引。
2. **修正**: 若当前会话的结论推翻了旧共识，或发现旧记录有误，必须先修正旧内容。
3. **更新**:
   - 在 **认知对齐目录** 中添加/更新达成的概念共识
   - 记录关键定义和术语
   - 更新文件目录索引（如有新文件类型）

**判断是否写入 memory.md：**
- 是否达成了新的概念共识？→ 写入
- 是否定义了新的术语或流程？→ 写入
- 是否只是完成任务？→ 不写入，只更新 task.md

同时回写共享 memory 真源 `tasks/<task-id>/memory.md`，`.agent/context/memory.md` 仅作为入口索引和兼容层。

### Step 4: 更新复杂概念（可选）

对于需要深入展开的复杂概念，创建 `memory/<topic>.md`：

```markdown
# <Topic Name>

## 概述
<!-- 1-2 句概念定义 -->

## 核心概念
<!-- 概念的详细展开 -->

## 设计决策
<!-- 为什么这样设计 -->

## 参考
- 相关文件、链接等

---
Created: YYYY-MM-DD
Last Updated: YYYY-MM-DD
```

**判断是否需要创建 topic 文件：**
- 概念是否复杂到需要独立文档？→ 创建
- 是否会多次引用？→ 创建
- 是否只是简单共识？→ 不创建，保留在 memory.md 即可

### Step 5: 更新任务状态（Un-tracked）

更新当前工作树的缓存 `.agent/context/task.md`：
1. **审查**: 审阅已有的 `Task Info`、`Gate Progress` 和 `Completed/Pending Tasks`。
2. **修正**: 确保 `Status`、`Worktree` 等基础信息与真实物理状态一致。若已有记录中的 blockers 已解决，应予以更新或移除。
3. **更新**: 
   - 刷新 current task 摘要
   - 记录当前 worktree、next step、subtasks summary
   - **重点记录当期疑难杂症 (Blockers) 和临时方案**，便于下个会话 `/vibe-continue` 加载。
- 该文件在 `.gitignore` 内，不必让用户为此做出 `git add` 或提交动作。

### Step 6: 同步共享 Task 状态

- 使用 CLI 工具命令（如 `vibe task update <task-id> --next-step ...`）将进度更新到共享真源。
- **严禁** AI 层直接手工编辑底层的 `.git/vibe/registry.json` 或 `worktrees.json`。所有的信息沉积都必须由 Shell API (`vibe task`) 处理。
- 刷新本地只读缓存：`.vibe/current-task.json`、`.vibe/focus.md`、`.vibe/session.json`
- `.vibe/focus.md` 保存当前 worktree 的聚焦摘要（task、subtask、next step）
- `.vibe/session.json` 保存当前 worktree 的短期会话缓存（`worktree_name`、`current_task`、`current_subtask_id`、时间戳）
- `.vibe/` 仅作为本地缓存，可重建，不保存共享 memory 真源

### Step 7: 输出摘要报告

向用户展示保存结果：

```
📋 Session Summary

🧠 认知对齐:
  • <概念1> - 简要描述
  • <概念2> - 简要描述

📁 Topic 文件:
  • memory/<topic>.md (created/updated/skipped)

✅ 任务状态:
  • 完成: <task-1>, <task-2>
  • 待办: <task-3>, <task-4>

📂 文件更新:
  • $(git rev-parse --git-common-dir)/vibe/registry.json
  • $(git rev-parse --git-common-dir)/vibe/worktrees.json
  • $(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/task.json
  • $(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/memory.md
  • .agent/context/memory.md
  • .agent/context/task.md
  • .vibe/current-task.json / .vibe/focus.md / .vibe/session.json
```

### Step 8: 分析可学习模式

分析保存的内容是否包含可复用模式：

- **error_resolution**: 错误解决方案
- **debugging_techniques**: 调试技巧
- **workarounds**: 临时解决方案
- **project_specific**: 项目特定约定

如果发现可复用模式，建议运行 `/learn` 提取为全局 skill。

### Step 9: 触发 Governance Hook

- 保存行为受 `.agent/governance.yaml` 的 `flow_hooks.done` 配置编排。
- 在最后归档前，必须确保上下文沉积工作已完成。

## 示例：本次会话的保存

### memory.md 更新

```markdown
## 2026-02-27: Vibe Workflow Paradigm（开发范式）

### 核心共识

**Vibe Guard 流程**：`PRD → Spec → Execution Plan → Test → Code → AI Audit`

### 关键概念

| 概念 | 定义 |
| ---- | ---- |
| PRD（认知层） | 定目标，人类主导 |
| Spec（规范层） | 定法律，AI 刺客找茬后锁定 |
| ... | ... |
```

### task.md 更新

```markdown
## Current
（无当前任务）

## Recent
- vibe-workflow-paradigm PRD 编写
  - status: completed
  - 产出：5 个 PRD 文件

## Backlog
| 优先级 | PRD | 说明 |
| ------ | --- | ---- |
| P1 | test-layer | TDD 顺序、3 次熔断 |
| ... | ... | ... |
```

## 与 /learn 的关系

| 方面 | `/save` | `/learn` |
| ---- | ------- | -------- |
| **目的** | 保存项目上下文 | 提取可复用模式 |
| **存储位置** | 项目级 `.agent/context/` | 全局 `~/.claude/skills/learned/` |
| **触发方式** | 手动 `/save` + Hook 提醒 | Stop Hook (自动, 需配置) |
| **内容** | 认知、任务、决策 | 模式、技巧、最佳实践 |

## 设计决策

1. **共享真源优先** - `/save` 先读 `.vibe/current-task.json`，再回写共享 registry 与 task memory
2. **认知与任务分离** - memory 记录共识，task 记录状态与 next step
3. **compat 层保留** - `.agent/context/*` 暂不废弃，作为迁移过渡入口
4. **本地缓存可重建** - `.vibe/` 只保留 focus/session 缓存，不保存共享真源
5. **与 /learn 独立** - `/save` 保存项目上下文，`/learn` 提取全局模式
