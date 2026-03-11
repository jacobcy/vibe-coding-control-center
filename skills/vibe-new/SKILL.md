---
name: vibe-new
description: Use when the user wants to create or intake the next delivery target from roadmap items, handoff blockers, or missing task specs, and needs plan/task binding without entering implementation.
---

# /vibe-new - Intake, Plan, And Task Binding

`vibe-new` 只处理规划入口，不进入执行。它负责把目标整理成可执行的 `roadmap item -> plan -> task -> flow` 链路。

先读这些真源：

- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/skill-standard.md`
- `docs/standards/skill-trigger-standard.md`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/handoff-governance-standard.md`
- `.agent/context/task.md`

只要 shell 参数或对象归属不确定，先运行对应 `vibe <command> -h`。

## 核心边界

- 允许：读取 handoff、检查 roadmap 窗口、补 issue/roadmap item、生成 plan、创建或更新 task、绑定 task 到 plan、必要时创建新的逻辑 flow
- 不允许：修改业务代码、进入实现、伪造没有 plan 的 task、擅自新建或切换物理 worktree
- 若当前 flow 已有 PR，只允许为下一个目标准备新的逻辑 flow，不得继续在当前 flow 中开发新目标

## Workflow

### Step 1: 读取当前上下文

优先读取：

```bash
vibe flow show --json
vibe roadmap status --json
```

必要时补充：

```bash
vibe task list --json
vibe task show <task-id> --json
```

检查点：

- 当前 flow 是否已有 `current_task`
- 当前 flow 是否已经 `open + had_pr`
- 当前 roadmap 窗口是否存在 `current` / `p0` item
- `.agent/context/task.md` 是否存在 handoff blocker 或待 intake 事项

### Step 2: 选择 intake 来源

按以下顺序选择目标来源：

1. 当前 flow 已绑定但缺少 `spec_standard/spec_ref` 的 task
2. `.agent/context/task.md` 中明确记录的 handoff blocker
3. 当前 roadmap 窗口内已存在但尚未形成 execution record 的 roadmap item
4. 用户显式指定的目标

如果以上来源都不存在，停止并报告“当前没有可 intake 的目标”。

### Step 3: 补齐规划对象

规则固定如下：

- 缺少 `repo issue` 或 bug 边界不清时，先委托 `vibe-issue`
- 缺少 roadmap item 时，先运行 `vibe roadmap add ...`
- 缺少 plan 时，默认委托 `writing-plans`
- 只有 plan 已落地后，才允许 `vibe task add` 或 `vibe task update`

task 与 plan 的绑定方式：

```bash
vibe task add <task-id> ... --spec-standard <standard> --spec-ref <plan-path>
vibe task update <task-id> --spec-standard <standard> --spec-ref <plan-path>
```

`spec_standard` 表示采用的规范体系；`spec_ref` 表示具体 plan 或 execution spec 入口文件。

### Step 4: 处理 flow 现场

当 task 与 plan 已绑定后，再决定是否需要新的逻辑 flow：

- 若当前目录还没有承载目标 flow，默认使用：

```bash
vibe flow new <slug> --branch origin/main
```

- 若只是把已有 task 绑定到当前目录承载的 flow，使用：

```bash
vibe task update <task-id> --bind-current
```

- 未经人类明确授权，不得使用 `wtnew`、`vnew`、`git worktree add`

### Step 5: 写入 handoff 与停止点

完成后更新 `.agent/context/task.md`，至少记录：

```markdown
## Skill Handoff
- skill: vibe-new
- updated_at: <ISO-8601>
- target: <roadmap-item-or-task>
- plan: <spec-ref-path>
- task: <task-id>
- flow: <flow-or-none>
- next: /vibe-start
```

然后停止，不进入执行。

## Restrictions

- 不得创建没有 `spec_standard/spec_ref` 的 task
- 不得把 handoff 直接当真源，必须先核查 shell 输出
- 不得把 `flow`、`task`、`roadmap item` 混成同一对象
- 不得在 skill 里把物理 worktree 当默认隔离手段
