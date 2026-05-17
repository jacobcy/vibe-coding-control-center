---
name: vibe-new
description: Use when starting or switching to a new human-collaboration task. Confirm the target issue, create or switch to the corresponding dev/issue branch, register and bind the flow, and link the branch to a draft PR when appropriate. Do not use for resuming an existing branch; use vibe-continue instead.
---

# /vibe-new - Workflow Selector + Bootstrap Orchestrator

从 issue 到 branch / flow / PR 创联的人机协作入口。

**核心定位**：workflow selector + infra bootstrapper。

---

## Interaction Layer

**职责**：理解用户意图，选择合适的 workflow，明确本 skill 不进入实现阶段。

### Step 1: 读取当前上下文

```bash
vibe3 flow show       # 当前 branch 的 flow 详情
git status            # 当前分支状态
```

**检查点**：
- 当前 branch 是否已有 flow？
- 当前 flow 是否已绑定 task issue？
- 当前 flow 是否已有 PR？（有 PR 则不得在此 flow 继续开发新目标）

### Step 2: 确认目标来源

**场景判断**：
- 用户指定 issue number → 直接使用
- 用户给的是 spec / plan / 需求草案 → **先调用 `/vibe-issue`** 查重并创建 issue
- 无 issue → 调用 `/vibe-issue` 创建

**重要**：如果输入是 spec / plan 而不是 issue number，不直接进入 bootstrap，先完成 issue intake。

### Step 3: 询问执行环境

**询问用户**：
```
请选择执行环境：
1. 当前仓库（继续在当前目录开发）
2. 新建 worktree（独立物理环境）

选择？
```

**说明**：
- 当前仓库：适合快速迭代、已有依赖环境
- 新建 worktree：适合并行任务、隔离依赖
- Orchestra 使用 task/issue-XXX 前缀（自动化场景）
- Skill 使用 dev/issue-XXX 前缀（人机合作场景）
- 底层共享同一个 WorktreeManager 抽象

### Step 4: 提示可选 workflow

告知用户可选的后续 workflow：
- `superpowers:writing-plans` → 创建实现计划
- `superpowers:executing-plans` → 执行现有计划
- `openspec` → OpenSpec 流程
- repo-native vibe3 workflow → 本仓库标准流程

---

## Bootstrap Layer

**职责**：编排原子能力，完成基础设施准备，不实现业务逻辑。

### 伪代码流程

```
@resolve_target_issue(...)
@resolve_target_branch(...)

# Step 1: 切换或创建分支（若需要）
if current_branch != target_branch:
    $ git checkout -b dev/issue-123

# Step 2: 注册 flow（幂等）
$ vibe3 flow update --actor <identity>

# Step 3: 绑定 task issue
$ vibe3 flow bind 123 --role task

# Step 4: 保存 baseline
$ vibe3 snapshot save --as-baseline

# Step 5: 记录 handoff
$ vibe3 handoff append "vibe-new: flow ready" --actor vibe-new --kind milestone

# Step 6: 按需创建 PR draft（若已具备条件）
if has_commits_and_ready_for_pr:
    $ vibe3 pr create --agent -t "..." -b "..."

# Step 7: 处理 worktree（若用户选择新 worktree）
if user_chose_new_worktree:
    $ wtnew dev/issue-123  # Shell 命令，创建独立物理环境
```

### 原子能力清单

**核心命令**：
- `git checkout -b <branch>` — 创建或切换分支
- `vibe3 flow update --actor <identity>` — 注册当前分支为 flow
- `vibe3 flow bind <issue> --role task` — 绑定 issue 到当前 flow
- `vibe3 snapshot save --as-baseline` — 保存开发起点 baseline
- `vibe3 handoff append` — 记录稳定恢复点
- `vibe3 pr create --agent` — 创联 PR draft（按需）
- `wtnew <branch>` — 创建独立 worktree（按需，shell 命令）

**共享抽象**：
- Orchestra 和 Skill 共享 `WorktreeManager._find_or_create_worktree_for_branch()`
- 区别仅在 branch 前缀：task/（自动化）vs dev/（人机合作）
- 保证无论哪个入口创建的 worktree/flow 都具有一致性

---

## Stop Conditions

完成后输出：

```markdown
## Bootstrap Complete

- ✅ Issue confirmed: #<issue-number>
- ✅ Branch ready: dev/issue-<id>
- ✅ Flow registered and task bound
- ✅ Baseline saved
- ✅ Handoff recorded
- ✅ Execution environment: <current-repo or worktree-path>

**Next Steps**:
- 开始编码
- 完成后运行 `/vibe-commit`
- 或进入相应的实现 workflow
```

**停止边界**：
- 不写业务代码
- 不进入实现阶段
- 不跨 worktree 调度
- 不修改已有 flow 的目标（已有 PR 的 flow 只做 review follow-up）

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

## Restrictions

- 不得把 handoff 当真源，必须先核查 `vibe3 flow show` 输出
- 不得在没有 issue 的情况下创建 flow
- 如果当前输入只是 spec / plan，不得跳过 `/vibe-issue` 直接建 flow
- 正确使用 `flow update` 和 `flow bind`：
  - `flow update --actor <identity>` - 注册当前分支为 flow（幂等），**必须设置 actor 署名**
  - `flow bind` - 绑定 issue 到当前 flow
  - 不要混用其他命令尝试注册或绑定
- 恢复已有 branch / flow 时不要再用已废弃的 `/vibe-start`，统一使用 `/vibe-continue`

