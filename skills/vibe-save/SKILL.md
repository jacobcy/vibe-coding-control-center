---
name: vibe-save
description: Use when the user wants to save session context, says "/vibe-save", or when ending a session and you want to preserve work state. Saves tasks, decisions, and solutions to project memory.
---

# /vibe-save - Session Context Save

会话上下文保存命令。在会话结束前自动提取和保存有价值的信息到项目记忆系统。

**核心原则:** 保存现在，延续未来。
**审阅优先原则:** 在任何写入操作之前，必须优先审阅目标文件的已有内容。若发现已有内容存在陈旧、错误或冲突（如状态不一致、陈旧的 next_step 等），必须先进行修正对齐，然后再追加或更新本次会话的新内容。不允许无视已有错误直接堆砌新内容。


**Announce at start:** "我正在使用 /vibe-save 技能来保存本次会话的上下文。"

**命令边界:** `/vibe-save` 是 skill 层入口；`vibe flow status`、`vibe task update` 是 shell 层工具。对 shell 参数、子命令或 flag 有任何不确定时，先运行对应命令的 `-h` / `--help`。shell 命令只服务 agent 执行，不是面向用户的命令教学清单。

## Shared Task Source
 
1. **定位**: 先通过 `vibe flow status` 与 `.vibe/current-task.json` 确认当前 flow / task 指针。
2. **真源**:
   - `registry.json`：task 执行态真源，保存 task 摘要、runtime 绑定事实、`next_step`。
   - `worktrees.json`：开放 flow / worktree 现场真源，保存当前目录与 branch 的绑定事实。
   - `tasks/<task-id>/memory.md`：共享任务记忆真源。
 
**指令**: 物理层状态已通过 `vibe flow status` 自动对齐。认知层保存需调用 `vibe task update --next-step ...` 沉积当前进度。

`/vibe-save` 只处理当前 worktree 绑定的 current task。

## Schema 契约

`/vibe-save` 必须区分三类数据：

- **共享真源字段**
  - `registry.json`：`task_id`、`title`、`status`、`current_subtask_id`、`runtime_worktree_name`、`runtime_worktree_path`、`runtime_branch`、`runtime_agent`、`next_step`
- **查询展示字段**
  - `dirty` / `clean` 只允许作为 `vibe flow status` 一类查询结果展示，不得写成共享真源字段
- **本地缓存字段**
  - `.vibe/current-task.json`、`.vibe/focus.md`、`.vibe/session.json` 只用于当前目录缓存，可重建，不得冒充共享 schema

不得回退到旧字段名或旧模型表述，例如 `assigned_worktree`、`worktree_name`、`current_task`、`current_task_id`、`version`、`name`、`path`。

## 文件职责分离

| 文件 | 职责 | 内容 |
| ---- | ---- | ---- |
| `memory.md` | 认知对齐目录 | 达成的概念共识、关键定义、文件目录索引 |
| `memory/<topic>.md` | 复杂概念展开 | 深入的概念定义、设计决策（可选，按需创建） |
| `task.md` | 短期 handoff | 当前操作者、当前 flow/task、next step、blockers / capability gap |

**核心区分：**
- `.agent/context/memory.md` = 跨任务复用的认知索引与共识入口。
- `.agent/context/task.md` = 当前目录的短期 handoff，不是共享任务真源。

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

再从共享真源或查询结果读取：

- `current_subtask_id`
- `runtime_worktree_name` / `runtime_worktree_path` / `runtime_branch` / `runtime_agent`
- `next_step`
- subtasks summary（`subtasks[].subtask_id`）
- shared memory 路径
- 当前 worktree 的 `dirty/clean` 状态（仅来自查询结果）

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

更新当前工作树的短期 handoff `.agent/context/task.md`：
1. **审查**: 审阅已有的 `Task Info`、`Gate Progress` 和 `Completed/Pending Tasks`。
2. **修正**: 确保当前操作者、flow / branch、task、next step 与真实状态一致。若已有记录中的 blockers 已解决，应予以更新或移除。
3. **更新**: 
   - 刷新 current task 摘要
   - 记录当前操作者、当前 flow / task / next step、subtasks summary
   - **重点记录 blockers、capability gap 与下一步建议**，便于下个会话 `/vibe-continue` 加载。

### Step 6: 同步共享 Task 状态

- 使用 CLI 工具命令（如 `vibe task update <task-id> --next-step ...`）将进度更新到共享真源。
- **严禁** AI 层直接手工编辑底层的 `.git/vibe/registry.json` 或 `worktrees.json`。这些路径只用于读取、定位和解释；所有共享状态写入都必须通过 shell API（如 `vibe task update`）完成。
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

📌 Current Handoff:
  • current actor: <agent>
  • flow/task: <flow> / <task-id>
  • next step: <next-step>
  • capability gap: <none|gap>

📁 Topic 文件:
  • memory/<topic>.md (created/updated/skipped)

📂 文件更新:
  • $(git rev-parse --git-common-dir)/vibe/registry.json
  • $(git rev-parse --git-common-dir)/vibe/worktrees.json
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

| 方面 | `/vibe-save` | `/learn` |
| ---- | ------- | -------- |
| **目的** | 保存项目上下文 | 提取可复用模式 |
| **存储位置** | 项目级 `.agent/context/` | 全局 `~/.claude/skills/learned/` |
| **触发方式** | 手动 `/vibe-save` + Hook 提醒 | Stop Hook (自动, 需配置) |
| **内容** | 认知、任务、决策 | 模式、技巧、最佳实践 |

## 设计决策

1. **共享真源优先** - `/vibe-save` 先读 `.vibe/current-task.json` 与 shell 查询，再回写共享 registry 与 task memory
2. **认知与 handoff 分离** - memory 记录共识，task 记录当前操作者、flow/task、next step 与 blockers
3. **compat 层保留** - `.agent/context/*` 暂不废弃，但 `.agent/context/task.md` 只作为本地 handoff
4. **本地缓存可重建** - `.vibe/` 只保留 focus/session 缓存，不保存共享真源
5. **与 /learn 独立** - `/vibe-save` 保存项目上下文，`/learn` 提取全局模式
