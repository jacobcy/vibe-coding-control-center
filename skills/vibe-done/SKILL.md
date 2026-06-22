---
name: vibe-done
description: Use when the current human-collaboration flow has reached terminal PR state and the user wants to do final closeout. Confirm PR outcome, close owned issues, check for follow-up needs, delete resources, and switch back to main. Do not use for code changes or abandoned work.
---

# /vibe-done - 终态收口

PR 合并后的完整收口流程。

## Related Skills

- **vibe-closeout**: Automated cleanup triggered by Manager signal (for Orchestra automation)
- **vibe-integrate**: PR merge workflow before final closeout

Use `vibe-done` for **human-initiated** manual cleanup after PR merge.
Use `vibe-closeout` only when Manager has written handoff indicate with cleanup instructions.

## 核心原则

- **只做收口**：不修业务代码，不做 review follow-up
- **PR 先决**：必须 PR 已 merged 或明确终态
- **完整清理**：关 issue → 删 branch → 删 worktree → 回 main

## Workflow

### Step 1: 确认 PR 终态

```bash
gh pr view <pr-number> --json state,mergedAt
```

- 若未合并或非终态 → 停止，返回 `/vibe-integrate`
- 若已合并 → 继续

### Step 2: 检查 issue 状态

检查当前 flow 负责的 issue 是否已关闭：

```bash
gh issue view <issue-number> --json state
```

- 若已关闭 → 记录状态
- 若未关闭 → 继续后续关闭操作

### Step 3: 检查 follow-up needs

判断是否需要创建 follow-up issue：

检查点：
- PR review 中是否有未完全解决的系统性问题
- 是否有明确标记的 future work
- 是否有遗留的技术债需要新 issue 追踪

若需要 follow-up：
```bash
gh issue create --title "Follow-up: <主题>" --body "来源: #<原 issue>, PR #<pr-number>"
```

### Step 4: 关闭 issue（如未关闭）

只关闭当前 flow 负责的主 issue：

```bash
gh issue close <issue-number> --comment "已完成 in PR #<pr-number>"
```

不关闭关联 issue（由各自 flow 负责）。

### Step 5: 删除 branch

删除本地和远程 branch：

```bash
# 删除本地 branch
git branch -D <branch-name>

# 删除远程 branch
git push origin --delete <branch-name>
```

### Step 6: 删除 worktree

删除当前 worktree（资源清理）：

```bash
# 先确认不在要删除的 worktree 中
pwd

# 删除 worktree
git worktree remove <worktree-path>
```

### Step 7: 切换回 main 并拉取

```bash
git checkout main
git pull origin main
```

### Step 8: 留痕（Trace）

根据当前环境记录终态：

**判断环境**：
```bash
# 检测是否有 flow 环境
vibe3 flow show
```

**留痕规则**：
- **有 flow 环境**（正常情况）：使用 handoff 记录关闭决策
  ```bash
  vibe3 handoff append "vibe-done: flow closed" --actor vibe-done --kind milestone
  ```

- **无 flow 但有 issue**：在 issue 中记录关闭决策
  ```bash
  gh issue comment <issue-number> --body "## Flow Closed

  **PR**: #<pr-number> (merged)
  **Issues Closed**: <issue-links>
  **Follow-up**: <issue-link or none>
  **Resources Cleaned**: branch + worktree
  **Completed At**: <ISO-8601>
  "
  ```

- **都没有**：无需留痕

**留痕内容应包含**：
- Flow 名称（如有）
- PR 编号和状态（merged）
- 已关闭的 issue 列表
- Follow-up issue（如有）
- 资源清理状态（branch + worktree）
- 完成时间

## 停止点

完成后输出：

- ✅ PR 已合并
- ✅ issue 已关闭（或已确认关闭）
- ✅ follow-up issue 已创建（如需要）
- ✅ branch 已删除（本地 + 远程）
- ✅ worktree 已删除
- ✅ 已切换到 main
- ✅ handoff 已记录

## Restrictions

- 不得修改业务代码
- 不得在 PR 合并前收口
- 不得关闭非当前 flow 负责的 issue
- 必须删除 worktree（完整清理）
- 必须切换回 main 并拉取最新代码
