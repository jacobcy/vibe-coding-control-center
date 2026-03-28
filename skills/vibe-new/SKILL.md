---
name: vibe-new
description: Use when starting a new development task. Handles the full setup from issue selection to flow creation, issue binding, and PR draft creation — ready to code. Replaces the old vibe-new + vibe-start two-step sequence.
---

# /vibe-new - 开始新任务

`/vibe-new` 是任务启动的全流程入口，覆盖从 issue 确认到 PR draft 创建的完整准备阶段。

**完成后状态**：flow 已创建、issue 已绑定、PR draft 已发出，可直接开始编写代码。

---

## 核心职责

1. 确认或创建目标 issue
2. 创建或注册 flow（绑定分支）
3. 绑定 issue 到 flow
4. 创建 PR draft（占位）
5. 停止并等待用户开始编码

**不做的事**：不写业务代码，不进入实现，不跨 worktree 调度。

---

## 停止点

完成后输出：

- ✅ issue 已确认
- ✅ flow 已创建/注册
- ✅ issue 已绑定到 flow
- ✅ PR draft 已创建
- **下一步**：开始编码，完成后运行 `/vibe-commit`

---

## 完整流程

```
/vibe-new <feature>
  ├─ Step 1: 读取当前上下文
  │   ├─ vibe3 flow show
  │   ├─ vibe3 flow status
  │   └─ 检查当前 branch、flow、已绑定 issue
  │
  ├─ Step 2: 确认目标 issue
  │   ├─ 用户指定 → 直接使用
  │   ├─ 无 issue → 调用 /vibe-issue 创建
  │   └─ gh issue view <number> 确认内容
  │
  ├─ Step 3: 准备 flow
  │   ├─ 场景A：需要新分支
  │   │   └─ vibe3 flow create <name> --task <issue> --base main
  │   ├─ 场景B：已在目标分支，首次注册
  │   │   ├─ vibe3 flow add
  │   │   └─ vibe3 flow bind <issue> --role task
  │   └─ 场景C：已有 flow，只需绑定新 issue
  │       └─ vibe3 flow bind <issue> --role task
  │
  ├─ Step 4: 创建 PR draft
  │   └─ vibe3 pr create --base main
  │
  └─ Step 5: 写入 handoff 并停止
      └─ vibe3 handoff append "vibe-new: ready to code" --actor vibe-new --kind milestone
```

---

## Workflow

### Step 1: 读取当前上下文

```bash
vibe3 flow show       # 当前 branch 的 flow 详情
vibe3 flow status     # 所有活跃 flow 一览
```

检查点：
- 当前 branch 是否已有 flow？（`flow show` 能正常输出）
- 当前 flow 是否已绑定 task issue？
- 当前 flow 是否已有 PR？（有 PR 则不得在此 flow 继续开发新目标）

若当前 flow 已有 PR，必须先执行 `vibe3 flow done` 或切换到新分支，再开始新任务。

### Step 2: 确认目标 issue

```bash
# 查看 issue 内容
gh issue view <number>

# 若无 issue，调用 /vibe-issue 创建
```

### Step 3: 准备 flow

**场景 A：当前在 main/无关分支，需要新建分支开发**

```bash
# 创建新分支 + flow，同时绑定 task issue
vibe3 flow create <name> --task <issue-number> --base main
```

> `--base main` 确保从最新主干拉取。`<name>` 建议用 `task/<issue>-brief` 格式。

**场景 B：已经 `git checkout -b` 切到新分支，需要注册 flow**

```bash
# 注册当前分支为 flow
vibe3 flow add

# 绑定 task issue
vibe3 flow bind <issue-number> --role task
```

**场景 C：已有 flow，需要追加绑定更多 issue**

```bash
# 绑定关联 issue（非主任务）
vibe3 flow bind <issue-number> --role related

# 绑定依赖 issue
vibe3 flow bind <issue-number> --role dependency
```

### Step 4: 创建 PR draft

```bash
vibe3 pr create --base main
```

PR draft 用于：
- 占位（表明此分支已有开发计划）
- 触发 CI 流水线
- 记录开发范围（在 PR body 中关联 issue）

> 若创建失败（无提交），先做一次空 commit：`git commit --allow-empty -m "chore: init flow"`

### Step 5: 写入 handoff 并停止

```bash
vibe3 handoff append "vibe-new: flow ready, PR draft created" \
  --actor vibe-new --kind milestone
```

记录格式：

```markdown
## Skill Handoff

- skill: vibe-new
- updated_at: <ISO-8601>
- issue: <issue-number>
- flow: <flow-slug>
- branch: <branch-name>
- pr: <pr-draft-number>
- next: 开始编码，完成后运行 /vibe-commit
```

然后停止，等待用户开始编码。

---

## 有依赖时的处理

如果当前任务依赖另一个 issue 未完成：

```bash
# 完成 flow 创建后，立即标记为 blocked
vibe3 flow blocked --task <blocking-issue-number> --reason "需要 #X 先完成"

# 可安全切走处理其他任务
git checkout <other-branch>

# 依赖解除后切回来继续
git checkout <this-branch>
vibe3 flow show
```

---

## 核心边界

- 允许：读取 flow 状态、创建 flow、绑定 issue、创建 PR draft、写入 handoff
- 不允许：修改业务代码、进入实现阶段、跨 worktree 调度、未经授权创建物理 worktree（`wtnew`、`git worktree add`）
- 若当前 flow 已有 PR：只能为下一个目标准备新 flow，不得继续在当前 flow 堆新目标

## Restrictions

- 不得把 handoff 当真源，必须先核查 `vibe3 flow show` 输出
- 不得在没有 issue 的情况下创建 flow（issue 是 flow 的规划依据）
- 不得把 `flow bind` 和 `flow add` 混用（`add` 注册分支，`bind` 绑定 issue）
