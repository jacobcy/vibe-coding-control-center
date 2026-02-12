---
description: Sync current branch changes to all other worktree branches and push
---

Synchronize the current branch's latest changes to all other git worktree branches, resolve conflicts intelligently, and push.

### 1. Pre-flight Check
Verify the current branch is clean and identify all worktree branches.
```bash
echo "=== Current Branch ==="
git branch --show-current

echo -e "\n=== Working Tree Status ==="
git status -s

echo -e "\n=== All Worktrees ==="
git worktree list

echo -e "\n=== Recent Commits (source) ==="
git log --oneline -5
```
- **STOP** if there are uncommitted changes. Ask the user whether to commit or stash first.

### 2. Analyze Divergence
For each target worktree branch, show how far it has diverged from the current branch.
```bash
SOURCE_BRANCH=$(git branch --show-current)
echo "Source branch: $SOURCE_BRANCH"
echo ""

git worktree list --porcelain | grep '^branch' | sed 's|branch refs/heads/||' | while read branch; do
  if [ "$branch" != "$SOURCE_BRANCH" ]; then
    BEHIND=$(git rev-list --count "$branch".."$SOURCE_BRANCH" 2>/dev/null || echo "?")
    AHEAD=$(git rev-list --count "$SOURCE_BRANCH".."$branch" 2>/dev/null || echo "?")
    echo "[$branch] behind: $BEHIND, ahead: $AHEAD"
  fi
done
```
- Review the divergence summary.
- If a branch is already up-to-date (behind=0), skip it in subsequent steps.
- **Ask the user** which branches to sync (default: all that are behind).

### 3. Merge into Each Target Branch
For each target branch that needs syncing, perform the merge **inside its worktree directory**.
Repeat the following for each target branch:

```bash
# Example for one branch — agent should loop over all selected targets
TARGET_WORKTREE_DIR="<path from git worktree list>"
TARGET_BRANCH="<branch name>"
SOURCE_BRANCH=$(git branch --show-current)

echo "=== Syncing $SOURCE_BRANCH → $TARGET_BRANCH ==="
echo "Worktree: $TARGET_WORKTREE_DIR"

cd "$TARGET_WORKTREE_DIR"
git merge "$SOURCE_BRANCH" --no-edit
```

- **If merge succeeds**: report success, move to next branch.
- **If merge conflicts**:
  1. Run `git diff --name-only --diff-filter=U` to list conflicted files.
  2. For each conflicted file, view the conflict markers and **analyze the intent** of both sides.
  3. Resolve the conflict intelligently:
     - If the conflict is trivial (e.g. import ordering, whitespace), resolve automatically.
     - If the conflict involves logic changes, **show both versions to the user** and ask which to keep or how to combine.
  4. After resolving, `git add <resolved-files>` and `git merge --continue`.

### 4. Verify Each Branch
After merging, run a quick sanity check in each target worktree.
```bash
cd "$TARGET_WORKTREE_DIR"
echo "=== Verifying $TARGET_BRANCH ==="
git log --oneline -3
git status -s
# Run tests if available
if [ -f "scripts/test-all.sh" ]; then
  ./scripts/test-all.sh || echo "⚠️  Tests failed on $TARGET_BRANCH"
fi
```
- If verification fails, **ask the user** before proceeding.

### 5. Push All Synced Branches
Push all successfully synced branches to origin.
```bash
# For each synced branch, push from its worktree
cd "$TARGET_WORKTREE_DIR"
git push origin "$TARGET_BRANCH"
```

### 6. Summary Report
Return to the source worktree and print a final summary.
```bash
echo "=== Sync Complete ==="
git worktree list
echo ""
echo "Branches synced and pushed:"
# List each branch and its status (success/skipped/failed)
```
- Report which branches were synced, which were skipped, and any that had issues.
