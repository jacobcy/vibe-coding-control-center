---
name: vibe-save
description: Use when the user wants to save session context, says "/save", or when ending a session and you want to preserve work state. Saves tasks, decisions, and solutions to project memory.
---

# /save - Session Context Save

会话上下文保存命令。在会话结束前自动提取和保存有价值的信息到项目记忆系统。

**核心原则:** 保存现在，延续未来。

**Announce at start:** "我正在使用 save 技能来保存本次会话的上下文。"

## 工作流程

### Step 1: 分析对话内容

回顾本次会话，识别：

1. **讨论的主题** - 本次对话涉及哪些技术领域？
2. **做出的决策** - 有哪些关键的架构或设计决策？
3. **解决的问题** - 遇到了什么问题？如何解决的？
4. **未完成的任务** - 有哪些任务被搁置或待办？
5. **可复用的模式** - 是否有值得记录的最佳实践？

### Step 2: 更新主题文件

对于每个识别到的主题：

```bash
# 检查是否存在对应主题文件
memory_file=".agent/context/memory/<topic>.md"

if [[ -f "$memory_file" ]]; then
    # 分节更新：只替换有变化的部分
    # - 更新 Key Decisions
    # - 添加 Problems & Solutions
    # - 添加 Related Tasks
    # - 更新 Last Updated
    # - 递增 Sessions 计数
else
    # 创建新主题文件
fi
```

### Step 3: 更新索引文件

更新 `.agent/context/memory.md`：

- 在 **Topic Index** 表格中添加/更新主题记录
- 更新 **Key Decisions** 如果有新决策
- 更新 **Execution Log** 记录本次会话

### Step 4: 更新任务文件

更新 `.agent/context/task.md`：

- 生成任务 ID: `<topic>-YYYYMMDD-NNN`
- 添加未完成任务到 **Backlog**
- 标记已完成的任务

### Step 5: 输出摘要报告

向用户展示保存结果：

```
📋 Session Summary

📁 Topics: N
  • <topic-1> (new/updated)
  • <topic-2> (updated)

✅ Tasks Added: N
  • <topic>-YYYYMMDD-NNN: Task description

💡 Key Decisions: N
  • Decision summary

🔧 Problems Solved: N
  • Problem → Solution

📂 Files Updated:
  • .agent/context/memory/<topic>.md (created/updated)
  • .agent/context/memory.md (index updated)
  • .agent/context/task.md (N tasks added)
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

## 文件格式

### memory/<topic>.md

```markdown
# <Topic Name>

## Summary
<!-- 1-2 句主题概述 -->

## Key Decisions
<!-- 关于此主题的关键决策 -->

## Problems & Solutions
### <Problem 1>
- **Issue**: ...
- **Solution**: ...
- **Lesson**: ...（可选，复杂问题才有）

## Related Tasks
- [ ] <topic>-YYYYMMDD-NNN: Task description
- [x] <topic>-YYYYMMDD-NNN: Completed task

## References
- 相关文件、链接等

---
Created: YYYY-MM-DD
Last Updated: YYYY-MM-DD
Sessions: N
```

### task.md 任务格式

```markdown
- [ ] [<topic>-YYYYMMDD-NNN] Task description
  - Context: 来自 [memory/<topic>.md](memory/<topic>.md)
  - Created: YYYY-MM-DD
  - Blocked by: 需要先完成 TASK-XXX（可选）
```

## 分节更新策略

更新现有主题文件时，使用**分节更新**：

1. **读取**现有文件内容
2. **识别**哪些部分有新内容
3. **只替换**有变化的部分
4. **保留**未变化的部分
5. **更新** Last Updated 时间戳
6. **递增** Sessions 计数

**示例:**
```
现有: config-system.md 有 3 个 Key Decisions, 1 个 Problem

本次对话新增:
- 1 个新 Key Decision
- 1 个新 Problem

结果:
- Key Decisions: 3 old + 1 new = 4 total (替换此节)
- Problems & Solutions: 1 old + 1 new = 2 total (替换此节)
- 其他部分: 保留
- Last Updated: 更新为当前日期
- Sessions: 递增
```

## 任务识别类型

| 类型 | 示例 | 处理方式 |
|------|---------|----------|
| **显式** | "帮我实现用户登录功能" | 直接提取 |
| **隐式** | "这个问题以后再处理" | 标记为待办 |
| **部分** | "先做 A，B 以后再说" | A 标记完成，B 待办 |
| **阻塞** | "等 XXX 完成后才能继续" | 记录阻塞原因 |

## 与 /learn 的关系

| 方面 | `/save` | `/learn` |
|------|---------|----------|
| **目的** | 保存项目上下文 | 提取可复用模式 |
| **存储位置** | 项目级 `.agent/context/memory/` | 全局 `~/.claude/skills/learned/` |
| **触发方式** | 手动 `/save` + Hook 提醒 | Stop Hook (自动, 需配置) |
| **内容** | 主题、任务、决策、解决方案 | 模式、技巧、最佳实践 |

**集成流程:**
- `/save` 存储项目特定知识到 `memory/`
- 保存后分析是否有可复用模式
- 如有模式，建议运行 `/learn` 提取为全局 skill

## 设计决策

1. **命名: `/save`** - 描述动作（保存上下文），而非告别
2. **主题式组织** - 比日期式更利于检索
3. **分节更新** - 只替换有变化的部分，实用且可靠
4. **自动识别主题** - Agent 分析并命名主题
5. **任务 + 上下文双追踪** - 任务在 task.md，上下文在主题文件，双向引用
6. **问题复杂度分级记录** - 简单问题简短记录，复杂问题结构化记录
7. **主题前缀任务 ID** - `<topic>-YYYYMMDD-NNN` 格式，可读且可追溯
8. **与 continuous-learning 独立** - `/save` 保存项目上下文，`/learn` 提取全局模式
