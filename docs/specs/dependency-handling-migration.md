# Migration Guide: Dependency Handling Mechanism

## Overview

This migration adds automatic dependency handling with `waiting` flow status and auto wake-up.

**Migration Type**: Code-only change, **no database migration required**.

## Changes

### New Features

1. **`waiting` flow status**: Flows with unsatisfied dependencies are now marked `waiting` instead of `blocked`
   - `waiting`: Waiting for external dependencies (can auto-recover)
   - `blocked`: Internal execution error (requires manual intervention)

2. **Automatic wake-up**: When a dependency completes (PR created), all waiting flows depending on it are automatically woken up

3. **Smart branch creation**: When a flow is woken up from dependency waiting, its worktree is created from the dependency's PR branch instead of `origin/main`
   - Ensures dependent code always builds on the latest dependency code
   - Avoids merge conflicts when dependency hasn't been merged yet
   - Fallback to `origin/main` automatically if PR branch fetch fails

### Database Changes

**No schema changes**:
- Uses existing `flow_state` table (extends `flow_status` enum with new value)
- Uses existing `flow_issue_links` table (already stores dependency relationships with `issue_role = 'dependency'`)
- Uses existing `flow_events` table for auditing

### Backward Compatibility

- ✅ **Full backward compatibility**: Existing flows are completely unaffected
- ✅ Only flows with explicit dependency relationships get the new behavior
- ✅ Existing `blocked` meaning unchanged: still means internal error requiring manual intervention
- ✅ All existing tests pass unchanged

## How to Use

### Declaring Dependencies

To declare that flow A depends on issue B:

```sql
-- In SQLite handoff.db
INSERT INTO flow_issue_links (branch, issue_number, issue_role)
VALUES ('task/issue-A', A, 'task');
INSERT INTO flow_issue_links (branch, issue_number, issue_role)
VALUES ('task/issue-A', B, 'dependency');
```

Or use the CLI binding when creating the flow:

```
vibe3 flow bind --dependency B <issue-A>
```

### Expected Flow

1. Issue B is a dependency of issue A
2. Orchestra dispatcher collects ready issues:
   - B has no dependencies → B marked `active`, gets processed
   - A depends on B → B not done yet → A marked `waiting`
3. B completes, PR created → `DependencySatisfied` event triggered
4. Dependency wake-up handler finds A waiting on B:
   - Checks all dependencies of A
   - If all satisfied → wake up A: `waiting` → `active`
5. When manager creates worktree for A:
   - Finds `dependency_wake_up` event with `source_pr` = PR of B
   - Fetches B's PR branch
   - Creates A's worktree from B's PR branch

## Migration Steps for Existing Installations

1. **Pull latest code**:
   ```bash
   git pull origin main
   ```

2. **No further action required**:
   - Database schema unchanged
   - Configuration unchanged
   - Existing flows continue to work as before

3. **Start using dependency handling**:
   - Declare dependencies on new flows
   - The mechanism automatically applies

## Troubleshooting

### PR branch fetch fails

- Automatic fallback to `origin/main` happens
- Event `dependency_branch_fallback` is recorded in flow history
- No action required unless you specifically need to start from the PR branch

### Flow stays waiting after dependency PR created

- Check: Are **all** dependencies satisfied?
- Check: Does the issue have `state/done` or `state/merged` label? Or is the issue closed?
- Check flow events: `vibe3 flow timeline <branch>` to see what dependencies are recorded

### Worktree creation fails after wake-up

- Check GitHub permissions: Can the current machine fetch the PR branch?
- Check if the PR branch was deleted: If deleted, fallback to `origin/main` happens automatically

## Contact

If you encounter issues with the migration, please file an issue on GitHub with:
- Flow branch name
- Relevant output from `vibe3 flow show <branch>`
- Relevant output from `vibe3 flow timeline <branch>`
