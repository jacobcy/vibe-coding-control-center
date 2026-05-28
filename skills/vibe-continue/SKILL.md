---
name: vibe-continue
description: Use when the user wants to resume work on an existing branch or flow. This is a human-facing resume entrypoint that explains current context and suggests next steps, not an automated bootstrap workflow.
---

# /vibe-continue - Human-Facing Resume Entrypoint

该技能是人机协作的恢复入口，负责读取当前 flow 上下文并提供继续建议。

## Core Principle: Human-Facing Interaction Only

**`vibe-continue` 只负责人机交互**：
- 识别当前目录承载的 flow 对应 task
- 读取共享真源（flow/task 状态）
- 读取本地 handoff（补充来源）
- 交叉核对现场一致性
- 给出继续建议

**`vibe-continue` 不承担的职责**（由基础设施承接）：
- 不定义恢复现场的业务语义
- 不自动修复现场不一致
- 不发明未验证的修复命令

这些恢复语义由 `vibe3 flow`、`vibe3 handoff` 等基础设施承接。

## Semantic Boundary

- **vibe-continue**: Session 恢复入口
- **vibe-save**: Session 保存入口
- **vibe3 flow/task**: Flow 与 task 状态真源
- **vibe3 handoff**: Handoff 基础设施（补充来源）
- **vibe-new**: 执行现场 bootstrap 入口

**vibe-continue 不等于 vibe-new**：
- `vibe-continue` 恢复已存在的 flow 现场
- `vibe-new` 创建新的 flow/worktree/workflow 现场

## Resume Contract (Shared with vibe-save)

`vibe-save` 和 `vibe-continue` 共享以下恢复契约：

**最小恢复现场**（由 handoff 承接）：
- 当前任务（task_id、title、status）
- 当前现场（branch、flow、worktree、pr、dirty）
- 本轮已完成
- 当前判断
- 阻塞点
- 下一步
- 关键文件

**恢复顺序**（vibe-continue 执行）：
- 先读 flow/task 状态（共享真源）
- 再读 handoff（本地补充）
- 交叉核对现场

## Human-Facing Workflow

### Step 1: Identify Current Flow & Task

优先从基础设施读取：

```bash
vibe3 flow show
vibe3 handoff status
vibe3 handoff show @current
```

识别内容：
- 当前 task
- `next_step`
- `plan_path`
- 当前 runtime 绑定事实
- `primary_issue_ref`（若存在）

如果共享真源中无法识别当前 flow，不要把 handoff 记录直接抬升成替代真源；它只能作为本地 handoff 线索。

### Step 2: Read Local Handoff

运行 `vibe3 handoff status` 和 `vibe3 handoff show @current`，把输出作为以下信息的补充来源：
- 本轮已完成
- 当前判断
- blockers
- 关键文件

若其内容与当前真源或现场不一致，必须在退出前修正 handoff，不能直接沿用旧判断。

如果 handoff 缺失，不阻断 continue；只说明当前缺少本地 handoff。

### Step 3: Cross-Check Current Scene

用确定性事实补全当前视图：
- 当前 branch
- dirty / clean
- 当前 PR 状态

Continue 阶段可以报告不一致，但不要把查询命令说成"自动对齐"，也不要调用未验证的隐式修复动作。

### Step 4: Provide Resume Suggestion

建议优先级如下：

1. 如果 `plan_path` 存在，优先建议按计划继续
2. 如果只有 `next_step`，则建议按当前 task 的下一步继续
3. 如果 handoff 记录与真源不一致，则把它明确标注为本地补充线索，而不是共享事实

## Suggested Output

```
📋 Session Resume

📁 Current Scene
  • worktree: <worktree>
  • branch: <branch>
  • state: dirty|clean

📌 Current Task
  • task: <task-id>
  • next step: <next-step>
  • plan: <plan-path|none>

📝 Local Handoff
  • handoff: present|missing（`vibe3 handoff show`）
  • blockers: <summary>

💡 Suggested Action
  • continue with <plan-path|next-step>
```

## Minimal Stop Points

- Resume context ready
- Blocked with explicit reason
- Next workflow suggested

## Design Principles

1. `vibe-continue` 先恢复共享事实，再读取本地 handoff
2. Handoff 的作用是补充解释，不代替真源
3. Continue 报告现场差异，但不发明未验证的自动修复动作
