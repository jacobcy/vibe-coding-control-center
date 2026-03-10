---
name: vibe-integrate
description: Use when the user wants to assess, unblock, and merge one or more PRs, especially stacked PRs, based on CI state, review state, merge order, and post-PR handoff readiness.
---

# /vibe-integrate - PR 整合编排

`/vibe-integrate` 负责把 PR 从“已发出”推进到“可合并并已合并”。它处理的是 `open + had_pr` 的 flow，而不是新的开发 flow。

先读这些真源：

- `docs/standards/git-workflow-standard.md`
- `docs/standards/worktree-lifecycle-standard.md`
- `docs/standards/command-standard.md`
- `docs/standards/handoff-governance-standard.md`
- `.agent/context/task.md`

## 核心边界

- 允许：检查 CI、检查 review threads、判断堆叠顺序、修复小型 follow-up、推动 merge
- 不允许：直接关闭 task、直接关闭 issue、手工修改共享真源 JSON
- 若 flow 还没有 PR 事实，这不是 `/vibe-integrate` 的阶段，应回到 `/vibe-commit`

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

### Step 2: 审核合并条件

对每个候选 PR，至少检查：

- CI 是否通过
- 是否还有阻塞性的 unresolved review threads
- merge base / stack 顺序是否正确
- 当前分支是否还需要 review follow-up patch

常用证据入口：

```bash
gh pr view <pr>
gh pr checks <pr>
gh api graphql ...
```

### Step 3: 处理阻塞项

若发现 CI 或 review 阻塞：

- 在对应分支上修复阻塞问题
- 运行受影响的本地验证命令
- 推送并重新检查远端 CI / review 状态

限制：

- 只修当前 PR 的 follow-up
- 不得借机把下一个目标混进同一个 PR
- 不得直接改 `.git/vibe/*.json`

### Step 4: 按顺序合并

只有同时满足以下条件，才允许 merge：

- CI 通过
- 阻塞性 review 已处理完成
- 堆叠上游已先合并
- 当前 PR 已达到可合并状态

遇到 stacked PR 时，必须按依赖顺序推进，不得跳序合并。

### Step 5: 写入 handoff

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
- next: <交给 vibe-done 的收口动作，或剩余待整合 PR>
```

## Restrictions

- 不得把 Copilot / review 线程一律当噪声忽略
- 不得在未验证 CI 的情况下声称“可合并”
- 不得跳过 stack 顺序
- 不得直接关闭 task 或 issue
- 若 PR 尚未达到合并条件，必须停在整合阶段并说明阻塞项
