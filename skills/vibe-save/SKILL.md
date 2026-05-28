---
name: vibe-save
description: Use when the user wants to save session context. This is a human-facing session handoff entrypoint that preserves work state via vibe3 handoff, not an automated persistence workflow.
---

# /vibe-save - Human-Facing Session Handoff Entrypoint

该技能是人机协作的 session 保存入口，负责整理当前会话并写入 handoff。

## Core Principle: Human-Facing Interaction Only

**`vibe-save` 只负责人机交互**：
- 判断当前会话哪些内容值得保留
- 整理 handoff 内容（已完成、当前判断、阻塞点、下一步）
- 写入 `vibe3 handoff append`
- 提供明确的恢复提示

**`vibe-save` 不承担的职责**（由基础设施承接）：
- 不定义"哪些字段算恢复现场"的业务语义
- 不决定 session 是否应该自动恢复
- 不承担 flow / task 状态同步

这些恢复语义由 `vibe3 handoff`、`vibe3 flow` 等基础设施承接。

## Semantic Boundary

- **vibe-save**: Session handoff 保存入口
- **vibe-continue**: Session handoff 恢复入口
- **vibe3 handoff**: Handoff 基础设施（存储、链、查询）
- **vibe3 flow/task**: Flow 与 task 状态真源
- **claude-memory**: 长期项目共识存储（仅形成稳定共识时使用）

**vibe-save 不等于自动状态同步**：
- `vibe-save` 只写入 handoff，不自动回写 flow/task 状态
- Flow/task 状态同步由各自的基础设施命令负责

## Resume Contract (Shared with vibe-continue)

`vibe-save` 和 `vibe-continue` 共享以下恢复契约：

**最小恢复现场**（由 handoff 承接）：
- 当前任务（task_id、title、status）
- 当前现场（branch、flow、worktree、pr、dirty）
- 本轮已完成
- 当前判断
- 阻塞点
- 下一步
- 关键文件

**恢复顺序**（vibe-continue 负责）：
- 先读 flow/task 状态（共享真源）
- 再读 handoff（本地补充）
- 交叉核对现场

## Human-Facing Workflow

### Step 1: Read Current Scene Facts

优先读取基础设施事实：

```bash
vibe3 flow show
vibe3 handoff show
```

必要时补充：

- `git status --short`
- 当前 branch
- 当前 PR / review 事实（如涉及）

### Step 2: Write Handoff

在写入前必须先审阅已有内容，并核对共享真源与现场事实。

若发现现有 handoff 与当前事实不一致，必须先修正，再退出。

使用 `vibe3 handoff append` 写入，至少覆盖：

1. 当前任务
2. 当前现场
3. 本轮已完成
4. 当前判断
5. 阻塞点
6. 下一步
7. 关键文件

Handoff 应优先回答"下个会话接手时需要知道什么"。

### Step 3: Sync Shared Truth (Optional)

如果当前目录承载的 `flow` 已能识别当前 `task`：

- 使用现有 Shell API 同步最小必要事实
- 优先同步 `next_step`，必要时同步 `status` 或 `pr_ref`
- 不在 save 阶段替上层流程做新的任务拆分或优先级判断

```bash
vibe3 handoff append "session save: <summary>" --actor vibe-save --kind milestone
```

如果当前目录尚未识别出当前 `flow` 对应的 `task`：

- 只运行 `vibe3 handoff append` 写入当前状态
- 明确向用户说明本次未回写共享 task 状态

### Step 4: Long-Term Memory (Optional)

只有在本次会话产出了稳定的项目约束、长期适用的定义或反复复用的规则时，才使用 `claude-memory` MCP 工具记录。

如果只是完成当前任务、记录 blockers 或保存下一步，不写记忆，更不默认创建新知识库。

### Step 5: Output Save Summary

摘要应说明：

- Handoff 是否已写入（`vibe3 handoff show` 可验证）
- 是否同步了共享 task 状态
- 是否使用了 `claude-memory` 记录稳定共识
- 当前最关键的下一步是什么

## Recommended Handoff Format

```markdown
# Current Task

- task_id:
- title:
- status:

# Current Scene

- branch:
- flow:
- worktree:
- pr:
- dirty:

# Completed This Session

- ...

# Current Judgment

- ...

# Blockers

- ...

# Next Step

- ...

# Key Files

- ...
```

## Minimal Stop Points

- Save complete (handoff written)
- Handoff inconsistent, requires manual fix
- No active flow, only handoff saved

## Design Principles

1. `vibe-save` 只负责人机交互，不定义恢复语义
2. Handoff 是补充来源，不代替 flow/task 真源
3. Claude-memory 只记录稳定共识，不承担临时状态保存
