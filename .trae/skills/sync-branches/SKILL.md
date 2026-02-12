---
name: "sync-branches"
description: "Syncs current branch changes to all other worktree branches. Invoke when user asks to 'sync branches' or uses the '/sync-branches' command."
---

# Sync Branches Workflow

This skill executes the branch synchronization workflow defined in `.agent/workflows/sync-branches.md`. It propagates changes from the current branch to all other active worktrees, handling conflict resolution and pushing updates.

## Workflow Steps

### 1. Pre-flight Check
1. Verify the current branch is clean (`git status -s` should be empty).
   - If not clean, **STOP** and ask user to commit or stash.
2. Identify the current source branch (`git branch --show-current`).
3. List all available worktrees (`git worktree list`).

### 2. Analyze Divergence
Check which worktree branches are behind the source branch.
```bash
SOURCE_BRANCH=$(git branch --show-current)
git worktree list --porcelain | grep '^branch' | sed 's|branch refs/heads/||' | while read branch; do
  if [ "$branch" != "$SOURCE_BRANCH" ]; then
    BEHIND=$(git rev-list --count "$branch".."$SOURCE_BRANCH" 2>/dev/null || echo "?")
    if [ "$BEHIND" != "0" ] && [ "$BEHIND" != "?" ]; then
       echo "TARGET_BRANCH: $branch (Behind by $BEHIND commits)"
    fi
  fi
done
```
- **Action**: Present the list of branches that need syncing to the user.
- **Action**: Ask for confirmation to proceed with syncing these branches.

### 3. Execution (For Each Target Branch)
For every confirmed target branch:

1. **Switch Context**: `cd` into the target worktree directory.
2. **Merge**: Run `git merge "$SOURCE_BRANCH" --no-edit`.
   - **Success**: Log success.
   - **Conflict**: 
     - Identify files: `git diff --name-only --diff-filter=U`
     - **Action**: Pause and ask user for help resolving conflicts, or use available tools to resolve if trivial.
     - Once resolved: `git add .` and `git merge --continue`.
3. **Verify**:
   - Run `scripts/test-all.sh` (if available) or `git status`.
   - If verification fails, **STOP** and ask user.
4. **Push**:
   - `git push origin "$TARGET_BRANCH"`

### 4. Final Report
Return to the original source directory and print a summary table of:
- Synced Branches (Success)
- Skipped Branches (Up-to-date)
- Failed Branches (Error details)

## Usage
Invoke this skill by saying "sync branches" or typing `/sync-branches`.
The Agent will act as the executor, running the shell commands and managing the interactive flow.
