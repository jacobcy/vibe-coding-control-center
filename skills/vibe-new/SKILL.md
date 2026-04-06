---
name: vibe-new
description: Use when starting or switching to a new human-collaboration task. Confirm the target issue, create or switch to the corresponding dev/issue branch, register and bind the flow, and link the branch to a draft PR when appropriate. Do not use for resuming an existing branch; use vibe-continue instead.
---

# /vibe-new - 新任务入口

从 issue 到 branch / flow / PR 创联的人机协作入口。

如果用户给的是 spec、计划文档或需求草案，而不是明确的 issue，`/vibe-new` 不应直接拿 spec 进入 flow；标准动作是先通过 `/vibe-issue` 查重、确认或创建可追踪的 GitHub issue，再回到 `/vibe-new` 继续 branch / flow / PR 创联。

**完成后状态**：目标 issue 已确认，`dev/issue-<id>` 分支已就绪，flow 已注册并绑定；若当前分支已具备可发 PR 的条件，PR draft 也已创联。

---

## 核心职责

1. 确认目标 issue；若当前输入只是 spec，则先通过 `/vibe-issue` 落 issue
2. 创建或切换到人机协作分支（`dev/issue-<id>`）
3. 注册 flow 并绑定 issue
4. 在合适时创建 PR draft，完成 issue-branch-pr 创联
5. 停止并等待用户开始编码

**不做的事**：不写业务代码，不进入实现，不跨 worktree 调度。

---

## 停止点

完成后输出：

- ✅ issue 已确认
- ✅ branch 已切到目标 `dev/issue-<id>` 现场
- ✅ flow 已创建/注册并绑定 issue
- ✅ PR draft 已创联（若本轮已满足创建条件）
- **下一步**：开始编码，完成后运行 `/vibe-commit`

---

## 完整流程

```
/vibe-new <feature>
  ├─ Step 1: 读取当前上下文
  │   ├─ vibe3 flow show
  │   ├─ vibe3 task status --all --check
  │   └─ 检查当前 branch、flow、已绑定 issue
  │
  ├─ Step 2: 确认目标 issue
  │   ├─ 用户指定 → 直接使用
  │   ├─ 用户给的是 spec / plan / 需求草案 → 调用 /vibe-issue 查重并创建 issue
  │   ├─ 无 issue → 调用 /vibe-issue 创建
  │   └─ gh issue view <number> 确认内容
  │
  ├─ Step 3: 准备 flow
  │   ├─ 场景A：需要新分支
  │   │   ├─ git checkout -b dev/issue-<id>
  │   │   ├─ vibe3 flow update
  │   │   └─ vibe3 flow bind <issue> --role task
  │   ├─ 场景B：已在目标分支，首次注册
  │   │   ├─ vibe3 flow update
  │   │   └─ vibe3 flow bind <issue> --role task
  │   └─ 场景C：已有 flow，只需绑定新 issue
  │       └─ vibe3 flow bind <issue> --role task
  │
  ├─ Step 4: 创联 PR（按需）
  │   └─ vibe3 pr create --base main --yes
  │
  └─ Step 5: 写入 handoff 并停止
      └─ vibe3 handoff append "vibe-new: ready to code" --actor vibe-new --kind milestone
```

---

## Workflow

### Step 1: 读取当前上下文

```bash
vibe3 flow show       # 当前 branch 的 flow 详情
vibe3 task status --all --check  # 全局 flow / issue / PR 上下文总览
```

检查点：

- 当前 branch 是否已有 flow？（`flow show` 能正常输出）
- 当前 flow 是否已绑定 task issue？
- 当前 flow 是否已有 PR？（有 PR 则不得在此 flow 继续开发新目标）

若当前 flow 已有 PR 或当前目标已经变化，必须切到新 branch 进入新 flow；旧 PR 的整合与收口交给 `/vibe-integrate` / `/vibe-done`，不要把旧 flow 继续伪装成新目标。

### Step 2: 确认目标 issue

```bash
# 查看 issue 内容
gh issue view <number>

# 若无 issue，调用 /vibe-issue 创建
```

补充规则：

- 如果用户给的是 `spec_ref`、计划文档路径、设计稿或一段需求描述，先把它当作 issue intake 输入，而不是 flow 输入。
- `/vibe-new` 在这种场景下应先显式切到 `/vibe-issue`：查重现有 issue，必要时用 spec 内容整理并创建新 issue。
- 只有 issue 已存在且可追踪时，才继续创建 `dev/issue-<id>` 分支、执行 `flow update` / `flow bind`，并在后续按需创联 PR。
- spec 的价值是帮助定义 issue 范围与验收边界，不替代 issue 在执行链中的追踪职责。

### Step 3: 准备 flow

**场景 A：当前在 main/无关分支，需要新建人机协作分支**

```bash
# 1. 创建新分支（人机协作统一使用 dev/issue-<id>）
git checkout -b dev/issue-123

# 2. 注册当前分支为 flow
vibe3 flow update

# 3. 绑定 task issue
vibe3 flow bind 123 --role task
```

**场景 B：已经 `git checkout -b` 切到新分支，需要注册 flow**

```bash
# 注册当前分支为 flow
vibe3 flow update

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

### Step 4: 创联 PR draft（按需）

```bash
vibe3 pr create --base main --yes
```

该步骤只在当前分支已经具备可发 PR 的条件时执行。PR draft 用于：

- 占位（表明此分支已有开发计划）
- 触发 CI 流水线
- 记录开发范围（在 PR body 中关联 issue）

若当前分支还没有合适的提交或 diff，不要为了占位制造空 commit；直接写 handoff，等首个有效提交后再创联 PR。

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

- 允许：读取 flow 状态、创建/切换 branch、注册 flow、绑定 issue、按需创建 PR draft、写入 handoff
- 不允许：修改业务代码、进入实现阶段、跨 worktree 调度、未经授权创建物理 worktree（`wtnew`、`git worktree add`）
- 若当前 flow 已有 PR：只能为下一个目标准备新 flow，不得继续在当前 flow 堆新目标

## Restrictions

- 不得把 handoff 当真源，必须先核查 `vibe3 flow show` 输出
- 不得在没有 issue 的情况下创建 flow（issue 是 flow 的规划依据）
- 如果当前输入只是 spec / plan / 需求草案，不得跳过 `/vibe-issue` 直接建 flow
- 不得把 `flow bind` 和 `flow add` 混用（`add` 注册分支，`bind` 绑定 issue）
- 恢复已有 branch / flow 时不要再用已废弃的 `/vibe-start`，统一使用 `/vibe-continue`
