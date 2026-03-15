---
name: vibe-start
description: Use when the user wants to execute the current flow's bound tasks from their plans, including auto-mode fallback across already-bound tasks, without creating new planning objects.
---

# /vibe-start - Execute Bound Tasks From Plans

`vibe-start` 负责进入新 flow 后，以 `repo issue -> flow` 作为用户主链视角推进执行。它会从 issue 落 task 作为 execution bridge，再执行当前 flow 已具备 execution spec 的 task。它不创建 roadmap item 或 plan；缺少这些对象时应回退到上游入口。

先读这些真源：

- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/skill-standard.md`
- `docs/standards/skill-trigger-standard.md`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/handoff-governance-standard.md`
- `.agent/context/task.md`

只要 shell 参数不确定，先运行对应 `vibe <command> -h`。

## 核心边界

- 允许：读取当前 flow、从 issue 落 task 作为 execution bridge、解析当前 task 的 `spec_standard/spec_ref`、按 plan 执行、运行验证、更新 task 状态、写 handoff
- 不允许：创建新的 roadmap item 或 plan；绕过 plan 自由编码；跨 worktree 调度
- 若发现当前 flow 已有 PR，本 skill 只能处理该 flow 合法范围内的 follow-up 或当前已绑定 task，不得把新目标堆进当前 flow

## Prerequisites

在运行 `vibe-start` 之前，确保以下对象已存在：

1. ✅ **Repo Issue** 已创建（`gh issue view <number>`）
2. ✅ **Roadmap Item** 已创建（`vibe roadmap list` 检查）
3. ✅ **Plan Document** 已存在（例如 `docs/plans/example.md`）
4. ✅ **Task 已创建** 并具备 `spec_standard` 和 `spec_ref`（`vibe task show <task-id>` 检查）
5. ✅ **Task 已绑定到当前 flow**（`vibe flow show` 检查）

若缺少任何前置对象：
- 先运行 `/vibe-new` 创建 flow 并绑定主 issue
- 或手动补齐缺失对象后重新进入

## Workflow

### Step 0: Check Prerequisites

在执行前，验证所有前置对象已就位：

```bash
# 检查当前 flow 状态
vibe flow show --json

# 检查 task 是否已创建并绑定
vibe task list --json

# 检查 plan 文件是否存在
ls docs/plans/<plan-name>.md
```

若发现缺失：
- 缺少 issue → 运行 `/vibe-issue`
- 缺少 roadmap item → 运行 `/vibe-roadmap`
- 缺少 plan → 委托 `writing-plans` 或手动创建
- 缺少 task → 使用 `vibe task add --spec-standard <standard> --spec-ref <plan-path>`
- task 未绑定 flow → 使用 `vibe task update --bind-current`

### Step 1: 读取当前 flow、issue 与 task

先运行：

```bash
vibe flow show --json
```

必要时补充：

```bash
gh issue view <issue-ref> --json number,title,body,labels
vibe task show <task-id> --json
```

检查点：

- 当前 `issue_refs`
- 当前 `primary_issue_ref`
- 当前 `current_task`
- 当前 flow 已绑定的 `tasks[]`
- 每个 task 的 `status`
- 每个 task 的 `spec_standard/spec_ref`

### Step 2: 从 issue 落 task 并选择执行目标

若当前 flow 尚未绑定 task，但 issue 与 plan 已明确：

- 先从 issue 落 task
- 通过 `vibe task add/update ... --spec-standard --spec-ref` 写入 execution spec
- 再把该 task 绑定到当前 flow

若当前 flow 已绑定 task，则直接进入执行目标选择。

默认顺序：

1. `current_task`
2. 当前 flow `tasks[]` 中其余已绑定 task，保持既有顺序

仅在用户开启 `auto` 模式时，允许自动切到下一个已绑定 task。

### Step 3: 校验 execution spec

执行前必须确认 task 已具备可解析的 execution spec：

- `spec_standard` 存在
- `spec_ref` 指向真实存在的 plan / spec 文件
- 若存在 `primary_issue_ref`，按它理解当前 task 的 `task issue`
- 若只有多个 `issue_refs` 而没有 `primary_issue_ref`，只能把这些 issue 当候选来源，不能擅自指定主闭环 issue

若缺失：

- 不执行当前 task
- 回退到 `/vibe-new` 补齐 issue / roadmap / plan 侧准备
- 若当前 flow 没有任何 task，则回退到 `/vibe-task`
- 若 `/vibe-task` 也找不到可绑定 task，再回到 `/vibe-roadmap`

### Step 4: 按 plan 执行

默认委托 `executing-plans`，并严格按 plan checklist 推进：

- 读取第一个未完成项
- 实施改动
- 运行验证命令
- 验证通过后更新计划勾选状态
- 当前 task 完成后，将其状态更新为 `completed`

### Step 5: 处理 blocker 与 auto fallback

若遇到 blocker，区分两类：

- 当前 task 局部阻塞：写入 `.agent/context/task.md`，保留原状态或标记 `blocked`；若是 `auto` 模式，可尝试下一个已绑定 task
- flow 级阻塞：立即停止，不得继续假装推进

handoff 最少记录：

```markdown
## Skill Handoff
- skill: vibe-start
- updated_at: <ISO-8601>
- flow: <flow>
- task: <task-id>
- blocker: <reason-or-none>
- verified: <commands-or-evidence>
- next: </vibe-new|/vibe-task|/vibe-roadmap|/vibe-commit>
```

## Restrictions

- 不得把 `.agent/context/task.md` 当正式执行图纸
- 不得把“跳过”写成“完成”
- 不得在缺 `spec_ref` 时继续编码
- 不得绕过 issue 直接凭空创建 task
- 不得把任意 `issue_ref` 默认写成当前 task 的主 issue
