---
name: vibe-integrate
description: Use when the user wants to assess, unblock, and merge one or more PRs, especially stacked PRs, based on CI state, review state, merge order, and post-PR handoff readiness.
---

# /vibe-integrate - PR 整合与合并

## 核心职责

`/vibe-integrate` 负责把 PR 从"已发出"推进到"可合并并已合并"。

**核心职责**：处理 PR 直到可合并状态

### 简单场景（快速通道）

- 纯文本修改
- 文档更新
- 配置调整
- **不要求 review evidence**

### 复杂场景（完整流程）

- 代码逻辑修改
- 架构调整
- **必须有 review evidence**：
  - 优先：在线 Codex/Copilot review
  - 备选：`uv run python src/vibe3/cli.py review base` 本地 review

## 停止点

- PR 已合并 → 进入 `/vibe-done`
- PR 未合并但有阻塞 → 停留并说明阻塞项

## 必读文档

- `docs/standards/v3/git-workflow-standard.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/handoff-governance-standard.md`

## 完整流程

```
/vibe-integrate
  ├─ Step 1: 建立整合上下文
  │   ├─ uv run python src/vibe3/cli.py flow show
  │   ├─ uv run python src/vibe3/cli.py flow status
  │   └─ 确认要处理的 PR、stacked 关系
  │
  ├─ Step 2: PR Review 状态审核（分层处理）
  │   ├─ 简单场景（文档/配置）
  │   │   └─ 跳过 review evidence 要求
  │   │
  │   └─ 复杂场景（代码逻辑/架构）
  │       ├─ 检查在线 Codex/Copilot review
  │       ├─ 无在线 review → 等待或触发 @codex comment
  │       └─ 备选：uv run python src/vibe3/cli.py review base
  │
  ├─ Step 3: 审核合并条件
  │   ├─ CI 是否通过
  │   ├─ review evidence 是否存在（复杂场景）
  │   ├─ 阻塞性 review threads 是否已处理
  │   └─ merge base / stack 顺序是否正确
  │
  ├─ Step 4: 处理阻塞项
  │   ├─ 修复 CI 或 review 阻塞问题
  │   ├─ 推送并重新检查状态
  │   └─ 只修当前 PR 的 follow-up
  │
  ├─ Step 5: 按顺序合并
  │   ├─ CI 通过
  │   ├─ review evidence 存在（复杂场景）
  │   ├─ 阻塞性 review 已处理
  │   └─ 堆叠上游已先合并
  │
  └─ Step 6: 写入 handoff
      ├─ PR 已合并 → 自动进入 /vibe-done
      └─ 有阻塞 → 停留并说明阻塞项
```

## 核心边界

- 允许：检查 CI、检查 review threads、判断堆叠顺序、修复小型 follow-up、推动 merge
- 不允许：直接关闭 task、直接关闭 issue、手工修改共享真源 JSON
- 若 flow 还没有 PR 事实，这不是 `/vibe-integrate` 的阶段，应回到 `/vibe-commit`
- 本 skill 是 `vibe-commit -> vibe-done` 之间的强制中间阶段；只要 PR 已创建，就不能跳过它直接宣告收口

## Workflow

### Step 1: 建立整合上下文

优先读取：

```bash
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py flow status
```

必要时再看：

```bash
uv run python src/vibe3/cli.py flow list
uv run python src/vibe3/cli.py task list
```

结合 `vibe3 handoff show` 输出，先确认：

- 当前要处理哪些 PR
- 哪些 PR 是独立的，哪些是 stacked
- 哪些 flow 已经进入 `open + had_pr`

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能把旧 handoff 继续传给下一个环节。

### Step 2: PR Review 状态审核（分层处理）

**重要：根据 PR 类型选择审核策略。**

#### 简单场景（快速通道）

满足以下任一条件，跳过 review evidence 要求：

- 纯文本修改（README、文档、注释）
- 配置调整（.gitignore、.editorconfig）
- 非逻辑性变更（格式化、重命名）

直接进入 Step 3。

#### 复杂场景（完整流程）

涉及以下任一条件，必须有 review evidence：

- 代码逻辑修改（函数、类、算法）
- 架构调整（新增模块、重构）
- 安全相关（认证、授权、加密）

**Review evidence 来源优先级**：

1. **优先：在线 Codex/Copilot review**

    ```bash
    uv run python src/vibe3/cli.py review pr [pr_number]
    ```

    - 检查 PR 上是否有 Codex/Copilot 的 review comment
    - 若无在线 review，在 PR 中添加 `@codex` comment 触发 review
    - 等待 10 分钟后重新检查

2. **备选：本地 review**
    ```bash
    uv run python src/vibe3/cli.py review base
    ```

   - 在线 review 不可用时使用
   - 将 review 结果回贴到 PR comment

**等待在线 Review 完成后再继续**：

- 不可在 Codex/Copilot 的 review 尚未出现在 PR 上时就断言”无阻塞”
- 若 review decision 是 `PENDING` 且没有 review threads，说明 reviewer 尚未完成，**必须等待或告知用户让其确认**
- 默认按异步场景处理：若用户当前不在线或没有急迫性，可先等待 10 分钟，再重新运行一次 `vibe flow review [pr]` 检查是否已有新的在线 review evidence
- 若等待一段时间后仍没有 Codex 在线 comment / review thread，默认由 agent 自动在 PR 中补一条 `@codex` comment 触发评论，再继续停留在 `/vibe-integrate`
- 若 review decision 是 `CHANGES_REQUESTED`，必须先处理 follow-up，不可直接提 merge
- 若再次等待后仍没有任何线上 review，不要把”作者自己看过”当成 review evidence；应优先使用 `vibe flow review --local` 或 browser/subagent 生成外部审查结果，再把结果回贴到 PR comment

### Step 3: 审核合并条件

对每个候选 PR，至少检查：

- CI 是否通过
- review evidence 是否存在
- 是否还有阻塞性的 unresolved review threads
- merge base / stack 顺序是否正确
- 当前分支是否还需要 review follow-up patch

常用证据入口：

```bash
gh pr view <pr>
gh pr checks <pr>
uv run python src/vibe3/cli.py review pr <pr>
```

### Step 4: 处理阻塞项

若发现 CI 或 review 阻塞：

- 在对应分支上修复阻塞问题
- 运行受影响的本地验证命令
- 推送并重新检查远端 CI / review 状态

限制：

- 只修当前 PR 的 follow-up
- 不得借机把下一个目标混进同一个 PR
- 不得直接改 `.git/vibe/*.json`
- 若当前 PR 已 merged，则旧 plan 视为 terminal state；此阶段只允许补交付证据或 follow-up 链接，不得把新需求写回旧 plan
- merge 后出现的新目标必须重新进入 `repo issue` intake，而不是继续挂在已完成 plan 下

### Step 5: 按顺序合并

只有同时满足以下条件，才允许 merge：

- CI 通过
- 已存在 review evidence
- 阻塞性 review 已处理完成（`APPROVED` 或所有 unresolved thread 已 resolve）
- 堆叠上游已先合并
- 当前 PR 已达到可合并状态

遇到 stacked PR 时，必须按依赖顺序推进，不得跳序合并。

### Step 5.5: 交接到 `/vibe-done`

只有出现以下两类结果之一，才允许把下一步交给 `/vibe-done`：

1. 当前 PR 已经 merged
2. 当前 PR 尚未 merged，但已经满足：
   - review evidence 存在
   - CI 通过
   - 无阻塞性 review
   - 当前 PR 已达到可 merge 状态

若还不满足，`next` 必须继续留在 `/vibe-integrate`，并明确写出阻塞项。

### Step 6: 写入 handoff

完成后运行：

```bash
uv run python src/vibe3/cli.py handoff append "vibe-integrate: PR review completed" --actor vibe-integrate --kind milestone
```

```markdown
## Skill Handoff

- skill: vibe-integrate
- updated_at: <ISO-8601>
- flow: <feature-or-none>
- branch: <branch-or-none>
- task: <task-id-or-none>
- pr: <merged-or-pending-pr-ref>
- issues: <issue-refs-or-none>
- completed: <本轮已合并或已解除阻塞的 PR>
- next: <若已满足条件，交给 vibe-done；否则明确继续 vibe-integrate，并写清 review evidence / CI / unresolved threads 中哪一项仍阻塞>

## Issues Found (可选)

- type: <flow|doc|command|other>
- severity: <low|medium|high>
- description: <问题描述>
- context: <发现场景>
- suggestion: <改进建议（可选）>
```

## Restrictions

- 不得把 Codex / Copilot 的 review 线程一律当噪声忽略
- 不得在未验证 CI 的情况下声称"可合并"
- 不得在 review 尚未完成（无 review threads、decision 为 PENDING）的情况下声称"无阻塞"
- 不得跳过 stack 顺序
- 不得直接关闭 task 或 issue
- 若 PR 尚未达到合并条件，必须停在整合阶段并说明阻塞项
