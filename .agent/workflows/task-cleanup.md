---
description: Cleanup local environment after task completion
---

# Task Cleanup Protocol

## 1. Prerequisites (前置准备)
- [ ] Task status confirmed: PR merged or Issue closed.
- [ ] Context: Identify the worktree and branch to remove.

## 2. Validation (验证状态)
Ensure the work is safely persisted on the remote main branch.

```bash
# Check if the branch is merged into main
git fetch origin
git branch -r --merged origin/main | grep <branch-name>
```

## 3. Execution (执行清理)

### 3.1 Remove Worktree & Branch
Use the `wtrm` utility which handles both worktree pruning and branch deletion.

```bash
# Usage: wtrm <worktree-directory-name>
# Example: wtrm wt-claude-feature-x
wtrm <worktree-dir>
```

> **Note**: If `wtrm` is not available, use manual steps:
> ```bash
> git worktree remove <path> --force
> git branch -d <branch>
> ```

### 3.2 Verify Cleanup
```bash
git worktree list
git branch
```
