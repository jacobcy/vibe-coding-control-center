---
name: continue
description: Use when the user wants to resume previous work, says "/continue", or starts a new session and wants to load saved context. Reads task.md and memory/ to restore state.
---

# /continue - Resume Saved Tasks

继续上次保存的任务。自动读取 task.md 和 memory/ 中的状态，识别未完成的任务。

**核心原则:** 无缝衔接，延续进度。

**Announce at start:** "我正在使用 continue 技能来恢复上次保存的任务。"

## 工作流程

### Step 1: 读取任务状态

```bash
# 读取任务文件
task_file=".agent/context/task.md"
memory_index=".agent/context/memory.md"
```

分析以下内容：
- **Current Objectives**: 当前正在进行的任务
- **Backlog**: 待办任务列表
- **Completed**: 已完成任务（用于上下文）

### Step 2: 识别活动主题

从 task.md 中提取任务 ID 的主题前缀：
- `save-20260221-005` → 主题: `save-command`
- `config-20260221-001` → 主题: `config-system`

读取相关主题文件：
```
.agent/context/memory/<topic>.md
```

### Step 3: 加载上下文

为每个活动主题加载：
1. **Summary** - 主题概述
2. **Key Decisions** - 相关决策
3. **Problems & Solutions** - 已解决的问题
4. **Related Tasks** - 任务状态
5. **References** - 相关文件

### Step 4: 输出继续报告

```
📋 Session Resume

📁 Active Topics: N
  • <topic-1>: <summary>

📌 Current Objectives: N
  • [ ] <task-id>: Task description (in progress)

📋 Backlog: N items
  • [ ] <task-id>: Task description

📂 Context Loaded:
  • .agent/context/memory/<topic>.md
  • .agent/context/task.md

💡 Suggested Action:
  → 继续执行 <task-id>: <description>
  → 运行: /superpowers:executing-plans docs/plans/<plan-file>
```

### Step 5: 提供继续选项

根据任务状态提供选项：

| 状态 | 建议 |
|------|------|
| 有计划文件 | 运行 `/superpowers:executing-plans <plan>` |
| 有进行中任务 | 直接继续该任务 |
| 只有 Backlog | 让用户选择优先级 |

## 文件格式依赖

### task.md 结构

```markdown
# TASK

## Current Objectives
<!-- 当前正在进行的任务 -->
- [ ] [<task-id>] Task description (in progress)

## Backlog
<!-- 待办任务 -->
- [ ] [<task-id>] Task description
  - Context: 来自 [memory/<topic>.md](memory/<topic>.md)

## Completed
<!-- 已完成任务 -->
- [x] [<task-id>] Completed task
```

### 任务 ID 格式

`<topic>-YYYYMMDD-NNN`

- `topic`: 主题标识（对应 memory/<topic>.md）
- `YYYYMMDD`: 创建日期
- `NNN`: 序号

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

1. **P0**: 读取 task.md 并识别当前任务
2. **P0**: 加载相关主题的 memory 文件
3. **P1**: 输出继续报告和建议
4. **P2**: 自动调用 executing-plans 如果有计划文件

## 示例输出

```
📋 Session Resume

📁 Active Topics: 1
  • save-command: /save 命令的会话上下文保存功能

📌 Current Objectives: 0
  (无进行中任务)

📋 Backlog: 2 items
  • [ ] save-20260221-005: 与 /learn 集成 (P2)
  • [ ] save-20260221-006: 将项目包装成 Plugin

📂 Context Loaded:
  • .agent/context/memory/save-command.md
  • .agent/context/task.md

💡 Suggested Actions:
  1. 继续 save-20260221-005: 与 /learn 集成
  2. 继续 save-20260221-006: 将项目包装成 Plugin
  3. 运行计划: /superpowers:executing-plans docs/plans/2026-02-21-save-command-design.md

你想继续哪个任务？
```

## 设计决策

1. **不自动执行** - 只加载上下文，让用户确认后才开始
2. **主题关联** - 通过任务 ID 前缀自动关联主题文件
3. **计划优先** - 如果有计划文件，优先建议使用 executing-plans
4. **与 /save 互补** - `/save` 写入，`/continue` 读取
