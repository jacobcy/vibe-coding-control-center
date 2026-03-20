---
name: vibe-start
description: Use when the user wants to execute the current flow's bound tasks from their plans, including auto-mode fallback across already-bound tasks, without creating new planning objects.
---

# /vibe-start - 准备执行环境

## 核心职责

`vibe-start` 负责进入新 flow 后准备执行环境，创建 task 和 PR draft，然后停止等待用户指令。

**核心职责**：

- 指定 task → 用指定 task
- 指定 plan → 用指定 plan
- 都没有 → 根据 issue 写 plan
- 创建 task 并绑定到 flow
- 创建 PR draft
- **停止并等待指令**

## 停止点

完成后输出：

- ✅ task 已创建
- ✅ PR draft 已创建
- **下一步**：等待用户指令（手动开发 或 `/vibe-commit`）

## 必读文档

- `docs/standards/v2/git-workflow-standard.md` (flow 生命周期)
- `docs/standards/v2/handoff-governance-standard.md` (handoff 规则与问题记录)
- `.agent/context/task.md` (当前上下文)

相关文档：

- 术语：`docs/standards/glossary.md`
- 动作语义：`docs/standards/action-verbs.md`

## 完整流程

```
/vibe-start [--task <task>] [--plan <plan>]
  ├─ Step 0: Check Prerequisites
  │   ├─ vibe flow show
  │   ├─ vibe task list
  │   └─ 检查 issue、roadmap item、plan、task 是否就位
  │
  ├─ Step 1: 读取当前 flow、issue 与 task
  │   ├─ vibe flow show
  │   ├─ gh issue view <issue-ref>
  │   └─ 检查 issue_refs、primary_issue_ref、current_task
  │
  ├─ Step 2: 从 issue 落 task 并选择执行目标
  │   ├─ 未指定 task/plan → 根据 issue 编写 plan
  │   ├─ 创建 task：vibe task add --spec-standard --spec-ref
  │   └─ 绑定 task 到当前 flow
  │
  ├─ Step 3: 创建 PR draft
  │   ├─ vibe flow pr --base <ref> --msg "<description>"
  │   └─ PR 包含 plan 文件或为空 PR
  │
  └─ Step 4: 写入 handoff 与停止
      ├─ 更新 .agent/context/task.md
      └─ 输出停止点信息，等待用户手动开发或 /vibe-commit
```

## 核心边界

- 允许：读取当前 flow、从 issue 落 task 作为 execution bridge、创建 PR draft、写入 handoff
- 不允许：创建新的 roadmap item 或 plan、绕过 plan 自由编码、跨 worktree 调度、进入执行阶段
- 若发现当前 flow 已有 PR，本 skill 只能处理该 flow 合法范围内的 follow-up 或当前已绑定 task，不得把新目标堆进当前 flow

## Workflow

### Step 1: 读取当前上下文

优先读取：

```bash
vibe flow show
vibe roadmap status
```

必要时补充：

```bash
vibe task list
gh issue view <issue-ref>
vibe roadmap list
```

检查点：

- 当前 flow 的 issue_refs
- 当前 flow 的 primary_issue_ref
- 当前 flow 是否已有 current_task
- 当前 flow 是否已经 open + had_pr

### Step 2: 准备 task 和 plan

**情况 A：用户指定 task**

```bash
vibe task show <task-id>
```

**情况 B：用户指定 plan**

```bash
ls docs/plans/<plan-name>.md
vibe task add --spec-standard <standard> --spec-ref <plan-path>
```

**情况 C：都没有**

- 根据 primary_issue_ref 编写 plan（保存到 `docs/plans/` 目录）
- 使用 `vibe task add --spec-standard openspec --spec-ref <plan-path>` 创建 task
- 使用 `vibe task update --bind-current` 绑定到当前 flow

### Step 3: 创建 PR draft

创建空的 PR draft 或包含 plan 文件的 PR：

```bash
# 创建 PR（首次需要提供 CHANGELOG message）
vibe flow pr --base <ref> --msg "<description>"
```

注意：

- PR 用于占位，不包含实现代码
- 如果已有 plan 文件，应包含在 PR 中
- PR 创建后当前 flow 进入 `open + had_pr` 状态
- 首次发布需要提供有效的 CHANGELOG message
- **PR 创建后需要手动关联到 task**：
  ```bash
  vibe task update <task-id> --pr "gh-<pr-number>"
  ```

### Step 4: 写入 handoff

完成后更新 `.agent/context/task.md`，至少记录：

```markdown
## Skill Handoff

- skill: vibe-start
- updated_at: <ISO-8601>
- flow: <flow>
- task: <task-id>
- plan: <plan-path>
- pr: <pr-draft-ref>
- next: 等待用户指令（手动开发 或 /vibe-commit）

## Issues Found (可选)

- type: <flow|doc|command|other>
- severity: <low|medium|high>
- description: <问题描述>
- context: <发现场景>
- suggestion: <改进建议（可选）>
```

然后停止，不进入执行。

## Restrictions

- 不得把 `.agent/context/task.md` 当正式执行图纸
- 不得把“跳过”写成“完成”
- 不得在缺 `spec_ref` 时继续编码
- 不得绕过 issue 直接凭空创建 task
- 不得把任意 `issue_ref` 默认写成当前 task 的主 issue
