---
name: vibe-done
description: Use when the current human-collaboration flow has reached terminal PR state and the user wants to do final closeout. Confirm PR outcome, close owned issues, record terminal handoff, and stop using this branch. Do not use for code changes or abandoned work.
---

# /vibe-done - 终态收口

PR 合并后的收口流程：关闭 issue → 清理 branch → 回主分支。

## 核心原则

- **只做收口**：不修业务代码，不做 review follow-up
- **PR 先决**：必须 PR 已 merged 或明确终态
- **最小操作**：只关 issue、清理 branch、写 handoff

## 前提条件

- PR 已 merged（或明确进入 closed/aborted 终态）
- 若 PR 未终态 → 回 `/vibe-integrate`

## Workflow

### Step 1: 确认 PR 终态

```bash
gh pr view <pr-number> --json state,mergedAt
```

- 若未合并或非终态 → 停止，返回 `/vibe-integrate`
- 若已合并或终态 → 继续

### Step 2: 关闭 issue

只关闭当前 flow 负责的主 issue：

```bash
gh issue close <primary-issue-number>
```

不关闭关联 issue（它们由各自 flow 负责）。

### Step 3: 清理 branch（可选）

询问用户是否需要删除 branch：

```bash
# 删除本地 branch
git branch -d <branch-name>

# 删除远程 branch（如需要）
git push origin --delete <branch-name>
```

**不删除 worktree**：worktree 是核心资源，生命周期由用户控制。

### Step 4: 回到主分支

```bash
git checkout main
git pull origin main
```

### Step 5: 记录 handoff

```bash
vibe3 handoff append "vibe-done: flow closed" --actor vibe-done --kind milestone
```

格式示例：

```markdown
## Flow Closure

- flow: <flow-name>
- status: completed
- pr: <pr-link>
- issues_closed: <issue-links>
- completed_at: <ISO-8601>
```

## 停止点

完成后输出：

- ✅ issue 已关闭
- ✅ branch 已清理（如选择删除）
- ✅ 已回到 main
- ✅ handoff 已记录

## Restrictions

- 不得修改业务代码
- 不得删除 worktree
- 不得在 PR 合并前收口
- 不得关闭非当前 flow 负责的 issue
