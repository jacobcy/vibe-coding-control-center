---
name: vibe-continue
description: Use when the user wants to resume previous work, says "/vibe-continue", or starts a new session and wants to load saved context. Restore from shared task facts first, then use vibe3 handoff show as context source.
---

# /vibe-continue - Resume Current Flow

`/vibe-continue` 的目标是恢复当前目录承载的 `flow` 所对应任务的上下文，但恢复顺序必须是"共享事实优先，本地 handoff 补充"，而不是反过来。

**核心原则：**

- 先读共享真源（`vibe3 flow show`），再读 handoff（`vibe3 handoff show`）。
- `vibe3 handoff show` 是 handoff 来源，不是共享真源。
- handoff 的维护义务以 `docs/standards/v3/handoff-governance-standard.md` 为准；发现与现场不一致时必须修正。
- 不在 continue 阶段发明不存在的 Shell 修复动作。

**Announce at start:** "我正在使用 /vibe-continue 技能来恢复当前 flow 的任务上下文。"

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

**快速命令参考**：

```bash
uv run python src/vibe3/cli.py flow show    # 查看当前 flow 状态
uv run python src/vibe3/cli.py handoff show # 查看 handoff 记录
```

特别约束：

- `flow` 不等于 `worktree`、`branch` 或 `workflow`。见 `docs/standards/glossary.md`。

## Command Boundary

- `/vibe-continue` 负责解释当前现场并给出继续建议。
- Shell 命令只用于读取共享真源和当前现场的确定性事实。
- `git` / `gh` 可用于补充 branch、dirty、PR 等现场事实。
- 如果需要某个环境修正动作，必须使用仓库中真实存在且已文档化的入口；不要发明未验证的修复命令。

## Restore Order

`/vibe-continue` 默认按以下顺序恢复：

1. 当前 `git` 现场（`git branch --show-current`、`git status --short`、必要时 `gh pr view`）
2. `$(git rev-parse --git-common-dir)/vibe/registry.json`
3. `$(git rev-parse --git-common-dir)/vibe/tasks/<task-id>/task.json`
4. `vibe3 handoff show`（当前 flow 的 handoff 记录）

必要时再补充：

- 当前 branch
- `git status --short`
- 当前 PR / review 事实

## Workflow

### Step 1: 识别当前目录承载的 flow 对应 task

优先从 `git` 现场、共享 `registry.json` 与 task detail 识别：

```bash
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py status
uv run python src/vibe3/cli.py handoff show
```

识别内容：

- 当前 task
- `next_step`
- `plan_path`
- 当前 runtime 绑定事实
- `primary_issue_ref`（若存在，它就是 `task issue` 的显式落点）

如果共享真源中无法识别当前 flow，不要把 handoff 记录直接抬升成替代真源；它只能作为本地 handoff 线索。

### Step 2: 读取本地 handoff

运行 `vibe3 handoff show`，把输出作为以下信息的补充来源：

- 本轮已完成
- 当前判断
- blockers
- 关键文件

若其内容与当前真源或现场不一致，必须在退出前修正 handoff，不能直接沿用旧判断。

如果它缺失，不阻断 continue；只说明当前缺少本地 handoff。

### Step 3: 交叉核对当前现场

用确定性事实补全当前视图，例如：

- 当前 branch
- dirty / clean
- 当前 PR 状态

continue 阶段可以报告不一致，但不要把查询命令说成"自动对齐"，也不要调用未验证的隐式修复动作。

### Step 4: 给出继续建议

建议优先级如下：

1. 如果 `plan_path` 存在，优先建议按计划继续。
2. 如果只有 `next_step`，则建议按当前 task 的下一步继续。
3. 如果 handoff 记录与真源不一致，则把它明确标注为本地补充线索，而不是共享事实。

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

## Design Decisions

1. continue 先恢复共享事实，再读取本地 handoff。
2. handoff 的作用是补充解释，不是代替真源。
3. continue 报告现场差异，但不发明未验证的自动修复动作。
