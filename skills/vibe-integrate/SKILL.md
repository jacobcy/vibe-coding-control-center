---
name: vibe-integrate
description: Use when the user wants to assess, unblock, and merge one or more PRs, especially stacked PRs, based on CI state, review state, merge order, and post-PR handoff readiness.
---

# /vibe-integrate - PR 整合编排

`/vibe-integrate` 负责把 PR 从"已发出"推进到"可合并并已合并"。它延续用户主链里的 `issue -> flow -> PR` 视角，处理的是 `open + had_pr` 的 flow，而不是新的开发 flow。

先读这些真源：

- `docs/standards/git-workflow-standard.md`
- `docs/standards/worktree-lifecycle-standard.md`
- `docs/standards/v2/command-standard.md`
- `docs/standards/v2/handoff-governance-standard.md`
- `.agent/context/task.md`

## 核心边界

- 允许：检查 CI、检查 review threads、判断堆叠顺序、修复小型 follow-up、推动 merge
- 不允许：直接关闭 task、直接关闭 issue、手工修改共享真源 JSON
- 若 flow 还没有 PR 事实，这不是 `/vibe-integrate` 的阶段，应回到 `/vibe-commit`
- 本 skill 是 `vibe-commit -> vibe-done` 之间的强制中间阶段；只要 PR 已创建，就不能跳过它直接宣告收口

## Workflow

### Step 1: 建立整合上下文

优先读取：

```bash
vibe flow show --json
vibe flow status --json
```

必要时再看：

```bash
vibe flow list
```

结合 `.agent/context/task.md`，先确认：

- 当前要处理哪些 PR
- 哪些 PR 是独立的，哪些是 stacked
- 哪些 flow 已经进入 `open + had_pr`

若 handoff 与当前真源或现场不一致，必须在退出前修正，不能把旧 handoff 继续传给下一个环节。

### Step 2: PR Review 状态审核

**重要：此步骤的行为取决于当前 flow 是否已经有 PR。**

#### 情况 A：已有 PR（`pr_ref` 非空）

必须执行 PR review 检查，不可跳过：

```bash
vibe flow review [pr_number]
```

这是查看线上 review comments / review threads / review evidence 的标准 shell 入口。默认先用它读取评论与阻塞项，不要绕开它自行拼接 `gh pr view` 输出做主判断。

`vibe flow review` 会通过 GraphQL 拉取所有行级 review thread，包含：
- 文件路径 + 行号
- Reviewer 身份
- 是否已 resolved / outdated
- 评论内容与链接

同时要确认至少存在一份 `review evidence`，可接受来源为三选一：
- Copilot 在线 review
- Codex 在线 review / comment
- `vibe flow review --local` 结果回贴到 PR comment

若三者都没有，本阶段的默认结论必须是：

- `blocked on review evidence`
- 不得把“CI 已绿”误报成“可 done”

**等待在线 Review 完成后再继续：**

- 不可在 Codex / Copilot 的 review 尚未出现在 PR 上时就断言"无阻塞"
- 若 review decision 是 `PENDING` 且没有 review threads，说明 reviewer 尚未完成，**必须等待或告知用户让其确认**
- 默认按异步场景处理：若用户当前不在线或没有急迫性，可先等待 10 分钟，再重新运行一次 `vibe flow review [pr]` 检查是否已有新的在线 review evidence
- 若等待一段时间后仍没有 Codex 在线 comment / review thread，默认由 agent 自动在 PR 中补一条 `@codex` comment 触发评论，再继续停留在 `/vibe-integrate`
- 若 review decision 是 `CHANGES_REQUESTED`，必须先处理 follow-up，不可直接提 merge
- 若再次等待后仍没有任何线上 review，不要把“作者自己看过”当成 review evidence；应优先使用 `vibe flow review --local` 或 browser/subagent 生成外部审查结果，再把结果回贴到 PR comment

可使用 `browser_subagent` 直接查看 PR 页面，或触发 agent 通过 review thread 给出回应：

```
# 调用 subagent 审查 PR review comments 并生成反馈
browser_subagent: 打开 PR 页面，输出所有 unresolved review thread
```

推荐 fallback 顺序：

1. `vibe flow review [pr]` 读取线上 comments / threads / evidence
2. 若用户不在线或当前没有急迫性，等待 10 分钟后再运行一次 `vibe flow review [pr]`
3. 若仍没有 Codex 在线 review，由 agent 自动在 PR 中补一条 `@codex` comment
4. 再等待 10 分钟后，重新运行一次 `vibe flow review [pr]`
5. 若仍无任何线上 review，则运行 `vibe flow review --local` 或使用 browser/subagent 产出外部 review evidence
6. 将外部 review 结果回贴到 PR comment 后，再继续判断 merge readiness

#### 情况 B：尚无 PR（`pr_ref` 为空）

**跳过此步骤**。此阶段是 pre-PR 本地审查，不需要等待在线 review。可直接进入 Step 3。

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
vibe flow review <pr>
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

完成当前 skill 后，必须更新 `.agent/context/task.md`，至少写入一段最新 handoff：

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
```

## Restrictions

- 不得把 Codex / Copilot 的 review 线程一律当噪声忽略
- 不得在未验证 CI 的情况下声称"可合并"
- 不得在 review 尚未完成（无 review threads、decision 为 PENDING）的情况下声称"无阻塞"
- 不得跳过 stack 顺序
- 不得直接关闭 task 或 issue
- 若 PR 尚未达到合并条件，必须停在整合阶段并说明阻塞项
