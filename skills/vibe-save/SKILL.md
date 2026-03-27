---
name: vibe-save
description: Use when the user wants to save session context, says "/vibe-save", or when ending a session and you want to preserve work state. Save a clear local handoff in task.md and sync only minimal shared task facts.
---

# /vibe-save - Session Handoff Save

`/vibe-save` 的首要目标不是散落保存大量文件，而是把当前会话整理成一份清晰、可继续的本地 handoff。

**核心原则：**

- 以 `.agent/context/task.md` 为默认保存载体。
- 共享真源只同步最小必要事实，不在 skill 中堆叠额外业务推断。
- 只有当本次会话形成了稳定、可复用的项目共识时，才更新 `.agent/context/memory.md`。
- 任何共享状态判断都必须先读 shell 输出，再决定是否写回。
- `spec_standard/spec_ref` 是 execution spec 扩展字段，只能通过 Shell API 同步。

**Announce at start:** "我正在使用 /vibe-save 技能来保存当前会话的 handoff。"

## Truth Sources

以下语义以标准为准，不在本 skill 中重写：

- `docs/standards/v3/skill-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/python-capability-design.md`
- `docs/standards/v3/git-workflow-standard.md`
- `docs/standards/v3/handoff-governance-standard.md`
- `docs/standards/glossary.md`

特别约束：

- `.agent/context/task.md` 的读取、写入与修正义务以 `docs/standards/v3/handoff-governance-standard.md` 为准。
- Shell 可以调用 `git` / `gh` / worktree 动作，但 skill 不得把这些机械步骤改写成"自动判断"或"自动修复"。见 `docs/standards/v3/python-capability-design.md`。

## Command Boundary

- `/vibe-save` 负责判断这次会话哪些内容值得保留。
- `uv run python src/vibe3/cli.py task status` 之类的 Shell 命令只用于同步共享真源中的最小必要事实。
- `git` / `gh` 可以用于读取当前 branch、dirty、PR 等现场事实。
- 不得直接编辑 `.git/vibe/*.json`。
- 不得假设 `.agent/governance.yaml` 中的 hook 已经自动执行。
- 不得把 execution spec 扩展字段改写成 GitHub 官方层身份。

## Default Save Policy

`/vibe-save` 默认只做三件事：

1. 更新 `.agent/context/task.md`，作为下个会话继续工作的主 handoff。
2. 如果当前目录承载的 `flow` 已能从共享真源识别当前 `task`，则通过 Shell 命令同步最小共享事实，例如 `status`、`next_step`、必要时的 `pr_ref`。
3. 仅当本次会话形成稳定项目共识时，才更新 `.agent/context/memory.md`。

默认不做：

- 不默认创建 `memory/<topic>.md`。
- 不把 `uv run python src/vibe3/cli.py flow status` 之类查询命令描述成"自动对齐"。
- 不把 save 描述成由 governance hook 自动编排完成。

## Workflow

### Step 1: 读取当前现场事实

优先读取：

- `$(git rev-parse --git-common-dir)/vibe/registry.json`
- `$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/task.json`（如果当前目录承载的 `flow` 已能从共享真源识别 `task`）
- `.agent/context/task.md`

如果 task 已存在，还应先读 shell 输出或 task 真源中的：

- `spec_standard`
- `spec_ref`

必要时补充读取：

- 当前 `git status --short`
- 当前 branch
- 当前 PR / review 事实（如会话内容涉及）

可通过以下命令获取：

```bash
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py task list
```

### Step 2: 审阅并更新 `.agent/context/task.md`

在写入前必须先完整审阅已有内容，并先核查共享真源与现场事实。

若发现现有 handoff 与当前事实不一致，必须先修正，再退出当前 skill。

推荐将 `task.md` 保持为单文件 handoff，至少覆盖：

1. 当前任务
2. 当前现场
3. 本轮已完成
4. 当前判断
5. 阻塞点
6. 下一步
7. 关键文件

`task.md` 应优先回答"下个会话接手时需要知道什么"，而不是扩展成认知档案库。

### Step 3: 仅在必要时同步共享真源

如果当前目录承载的 `flow` 已能识别当前 `task`：

- 使用现有 Shell API 同步最小必要事实。
- 优先同步 `next_step`，必要时同步 `status` 或 `pr_ref`。
- 若 execution spec 在本会话已明确，使用 `uv run python src/vibe3/cli.py task status` 同步状态。
- 不在 save 阶段替上层流程做新的任务拆分、归属判断或优先级判断。

同步 handoff 到共享存储：

```bash
uv run python src/vibe3/cli.py handoff append "session save: <summary>" --actor vibe-save --kind milestone
```

如果当前目录尚未识别出当前 `flow` 对应的 `task`：

- 只更新本地 `task.md` handoff。
- 明确向用户说明本次未回写共享 task 状态。

### Step 4: 仅在形成稳定共识时更新 `memory.md`

只有在本次会话产出了稳定的项目约束、长期适用的定义或反复复用的规则时，才更新 `.agent/context/memory.md`。

如果只是完成当前任务、记录 blockers 或保存下一步，不写 `memory.md`，更不默认创建新的 topic 文件。

### Step 5: 输出保存摘要

摘要应说明：

- `task.md` 是否已更新
- 是否同步了共享 task 状态
- 是否更新了 `memory.md`
- 当前最关键的下一步是什么

## Recommended `task.md` Shape

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

## Design Decisions

1. `task.md` 是默认 handoff 载体，避免 save 默认散落出过多文件。
2. 共享真源只同步最小必要事实，不把 save 扩展成 workflow 编排器。
3. `memory.md` 只记录稳定共识，不承担每次会话的临时状态保存。

## 命令映射说明

| 旧命令 (vibe2) | 新命令 (vibe3) |
|---------------|---------------|
| `vibe task update` | `uv run python src/vibe3/cli.py task status` |
| `vibe flow status` | `uv run python src/vibe3/cli.py flow status` |
| N/A | `uv run python src/vibe3/cli.py handoff append` |