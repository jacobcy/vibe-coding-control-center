---
description: Sync current branch changes to all other worktree branches and push
---

# Sync Worktree Branches

## 1. Prerequisites (前置准备)
- [ ] Context gathered: Check worktree status.
- [ ] Rules loaded: `git-rules.md`.

## 2. Standards Check (规范检查)
**CRITICAL**: 执行前请复核以下规则：
// turbo
cat .agent/rules/git-rules.md

## 3. Execution (执行)
Synchronize the current branch's latest changes to all other git worktree branches, resolve conflicts intelligently, and push.
> [!IMPORTANT]
> This command will attempt to merge changes. Watch for conflict markers in other worktrees if auto-merge fails.

// turbo
```bash
if [ -f ".agent/lib/git-ops.sh" ]; then
    source .agent/lib/git-ops.sh
    sync_all
else
    echo "Error: .agent/lib/git-ops.sh not found."
    exit 1
fi
```

## 4. Verification (验证)
- [ ] Verify worktree status.
```bash
git worktree list
# git status (optional, manual check in other worktrees)
```

