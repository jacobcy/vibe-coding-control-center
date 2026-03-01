---
name: vibe-task
description: Use when the user wants a cross-worktree task overview, says "vibe task" or "/vibe-task", asks which worktree to enter next, or wants to review current task status across worktrees.
---

# /vibe-task - Cross-Worktree Task Overview

查看当前仓库下各个 worktree 绑定的任务总览，并给出下一步优先进入哪个 worktree 的建议。

**核心原则:** CLI 负责读取事实，skill 负责解释事实。

**Announce at start:** "我正在使用 vibe-task 技能来查看跨 worktree 的任务总览。"

## Trigger Examples

- `vibe task`
- `/vibe-task`
- `查看 worktree 任务`
- `任务总览`
- `现在该进哪个 worktree`
- `哪个 worktree 该优先处理`

## Hard Boundary

- 必须先运行 `bin/vibe task`
- 不得直接读取 `registry.json`
- 不得直接读取 `worktrees.json`
- 不得自己重写 task 匹配逻辑

如果 CLI 失败，直接报告失败原因并停止，不要绕过 CLI。

## Workflow

### Step 1: 运行 CLI

```bash
bin/vibe task
```

目标：

- 获取当前所有 worktree 的任务总览
- 读取每个 worktree 的 `current task`
- 读取每个 worktree 的 `current subtask`
- 读取每个 worktree 的 `next step`
- 读取每个 worktree 的 `dirty` / `clean` 状态

### Step 2: 解析 CLI 输出

从 `Vibe Task Overview` 输出中提炼：

- worktree 名称
- 路径
- branch
- state
- current task
- title
- status
- current subtask
- next step

不得补充 CLI 未提供的字段。

### Step 3: 生成对话摘要

用简洁报告向用户说明：

1. 当前有哪些 worktree
2. 每个 worktree 正在处理什么 current task
3. 哪些 worktree 是 dirty，哪些是 clean
4. 哪个 worktree 最值得优先进入
5. 为什么推荐它

优先级建议规则：

- 若某个 worktree 的 task `status` 为 `blocked`，优先提示阻塞
- 若存在 `in_progress` 且 `dirty` 的 worktree，优先建议回到该 worktree 收口
- 若多个 worktree 都是 `done` 或 `idle`，明确说明暂无明显优先级差异

### Step 4: 输出格式

输出至少包含：

- `Worktrees`
- `Current task`
- `Current subtask`
- `Next step`
- `State`
- `Recommendation`

示例结构：

```text
Worktrees
- wt-claude-refactor: current task = 2026-03-02-cross-worktree-task-registry, state = active dirty

Recommendation
- 优先进入 wt-claude-refactor
- 原因：它仍处于 dirty 状态，且 next step 已明确
```

## Failure Handling

如果 `bin/vibe task` 失败：

- 直接展示 CLI 返回的阻塞原因
- 明确告诉用户当前无法生成可靠总览
- 不要自行 fallback 到共享 registry 文件

## Terminology Contract

本 skill 统一使用以下术语：

- `worktree`
- `current task`
- `current subtask`
- `next step`
- `dirty`
- `clean`

不要改写成其他近义词。
