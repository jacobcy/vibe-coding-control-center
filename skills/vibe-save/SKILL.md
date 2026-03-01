---
name: vibe-save
description: Use when the user wants to save session context, says "/save", or when ending a session and you want to preserve work state. Saves tasks, decisions, and solutions to project memory.
---

# /save - Session Context Save

会话上下文保存命令。在会话结束前自动提取和保存有价值的信息到项目记忆系统。

**核心原则:** 保存现在，延续未来。

**Announce at start:** "我正在使用 save 技能来保存本次会话的上下文。"

## 文件职责分离

| 文件 | 职责 | 内容 |
| ---- | ---- | ---- |
| `memory.md` | 认知对齐目录 | 达成的概念共识、关键定义、文件目录索引 |
| `memory/<topic>.md` | 复杂概念展开 | 深入的概念定义、设计决策（可选，按需创建） |
| `task.md` | 任务状态 | 已完成的工作 + 待办事项 |

**核心区分：**
- `memory.md` = 认知（我们达成了什么共识）
- `task.md` = 任务（我们做了什么、要做什么）

## 工作流程

### Step 1: 分析对话内容

回顾本次会话，识别：

1. **认知对齐** - 达成了哪些概念共识？（写入 memory.md）
2. **复杂概念** - 是否有需要深入展开的概念？（按需写入 memory/<topic>.md）
3. **任务状态** - 完成了什么？待办是什么？（写入 task.md）

### Step 2: 更新认知对齐目录

更新 `.agent/context/memory.md`：

- 在 **认知对齐目录** 中添加/更新达成的概念共识
- 记录关键定义和术语
- 更新文件目录索引（如有新文件类型）

**判断是否写入 memory.md：**
- 是否达成了新的概念共识？→ 写入
- 是否定义了新的术语或流程？→ 写入
- 是否只是完成任务？→ 不写入，只更新 task.md

### Step 3: 更新复杂概念（可选）

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

### Step 4: 更新任务状态

更新 `.agent/context/task.md`：

- 将 **Current** 中完成的任务移到 **Recent**
- 更新 **Current** 为新的进行中任务
- 添加 **Backlog** 待办事项

### Step 5: 输出摘要报告

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
  • .agent/context/memory.md
  • .agent/context/task.md
  • .agent/context/memory/<topic>.md (如有)
```

### Step 6: 分析可学习模式

分析保存的内容是否包含可复用模式：

- **error_resolution**: 错误解决方案
- **debugging_techniques**: 调试技巧
- **workarounds**: 临时解决方案
- **project_specific**: 项目特定约定

如果发现可复用模式，建议运行 `/learn` 提取为全局 skill。

### Step 7: 触发 Governance Hook

作为 Vibe Skills 治理体系的一部分，在 `vibe flow done` 阶段将自动触发 `save` 技能：
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

1. **认知与任务分离** - memory.md 记录共识，task.md 记录任务
2. **topic 按需创建** - 复杂概念才需要独立文档，不是强制
3. **主题式组织** - 比日期式更利于检索
4. **分节更新** - 只替换有变化的部分
5. **与 /learn 独立** - `/save` 保存项目上下文，`/learn` 提取全局模式
