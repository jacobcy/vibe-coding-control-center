---
description: Quickly switch to a new task within an existing worktree
---

# Rotate Task Workflow

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check current branch and worktree.
- [ ] Rules loaded: `git-rules.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/git-rules.md

## 3. Execution (执行)
Switch to a new task while preserving uncommitted work.
> [!IMPORTANT]
> This workflow destroys the old branch history after stashing changes. Ensure you really want to "rotate" the context.

### 3.1 Validation & Trigger
Command: `vibe flow rotate <new-task-name>`

### 3.2 Process Steps
1.  **Save State**: `git stash push -m "Rotate to <new-task>"`
2.  **Reset**:
    - Fetch `origin/main`.
    - `git checkout -b <new-task> origin/main`.
3.  **Cleanup**: `git branch -D <OLD_BRANCH>`.
4.  **Restore**: `git stash pop`.

## 4. Verification (验证)
- [ ] Verify new branch is active.
- [ ] Verify stashed changes are applied.
```bash
git status
git branch --show-current
```

