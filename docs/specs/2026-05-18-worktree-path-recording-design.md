# Fix worktree_path Recording for Auto Task Branches

**Issue**: #1028
**Date**: 2026-05-18
**Status**: Approved

## Problem

`WorktreeLifecycle.find_or_create_worktree_for_branch()` only calls `record_worktree_path()` in Step 4 (create new worktree). When an existing worktree is found via Step 3, worktree_path is never recorded to flow_state.

This causes 7+ active flows to have NULL worktree_path, leading to:
- Health check failures (cannot verify plan_ref/report_ref)
- Handoff resolution failures (cannot find artifacts in worktree)
- Worktree loss incidents (e.g., #1017 plan_ref written to main worktree)

## Constraint

Only `task/issue-*` branches (orchestra-managed auto tasks) should have worktree_path recorded. `dev/issue-*` branches (human-collaborative) and other manual branches do not need or want this tracking.

This is enforced via `is_auto_task_branch()` from `status_query_service.py`.

## Design

### Approach: Simple Patch (Option A)

Add `is_auto_task_branch()` guard to both Step 3 and Step 4 in `find_or_create_worktree_for_branch()`.

**File**: `src/vibe3/environment/worktree_lifecycle.py`

**Step 3 patch**: Find existing worktree — record for task branches only

```python
existing = find_worktree_for_branch(repo_path, flow_branch)
if existing:
    if validate_issue_number and not self.validate_worktree_branch_for_issue(
        existing, issue_number, flow_branch
    ):
        logger.bind(...).error("Existing worktree branch name does not match issue number")
        return None
    if check_recorded_path and is_auto_task_branch(flow_branch):
        self.record_worktree_path(flow_branch, str(existing))
    return WorktreeContext(...)
```

**Step 4 patch**: Create new worktree — same guard for consistency

```python
try:
    ctx = acquire_issue_worktree_func(issue_number, flow_branch)
    if check_recorded_path and is_auto_task_branch(flow_branch):
        self.record_worktree_path(flow_branch, str(ctx.path))
    return ctx
except Exception as exc:
    ...
```

**Import**: Add `from vibe3.services.status_query_service import is_auto_task_branch`

### Error Handling

`record_worktree_path()` already wraps its logic in try-except with warning log on failure. No additional error handling needed.

### Data Migration: Backfill Command

Add `vibe3 internal backfill-worktree-paths` command to backfill existing active flows.

Logic:
1. List all git worktrees
2. Filter to `task/issue-*` branches
3. For each, check flow_state: if active and worktree_path is NULL, update it

### Testing

Unit tests:
- `test_record_worktree_path_for_auto_task_branch` — Step 3 records for task/ branches
- `test_no_record_for_dev_branch` — Step 3 does NOT record for dev/ branches
- `test_step4_record_for_task_branch` — Step 4 records for task/ branches

## Impact

- Fixes 7+ active flows with NULL worktree_path
- Enables reliable health check artifact verification
- Enables reliable handoff artifact resolution
- No impact on dev/issue-* or manual branches
