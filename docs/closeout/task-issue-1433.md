# PR Creation Instructions for Issue #1433

## Context
- Issue: #1433
- Branch: task/issue-1433
- Commit: e690f39d
- State: merge-ready

## PR Details

**Title**: feat(check): clean physical resources when closed PR has no task issue link

**Body**:
## Summary
- Add physical resource cleanup when `vibe3 check` detects a closed PR for a flow without a linked task issue
- Modify `_reset_issue_after_pr_closed` to return tuple with cleanup warnings
- Reuse `FlowCleanupService.cleanup_flow_scene()` for consistent cleanup behavior

## Changes
- `src/vibe3/services/check_service.py`: Add cleanup invocation in no-task-issue-link path
- `tests/vibe3/services/test_check_pr_status.py`: New test for cleanup behavior
- `tests/vibe3/services/test_check_service_verify_branch.py`: Update mock return value

## Test plan
- [x] All 31 tests pass
- [x] mypy clean
- [x] ruff clean
- [x] New test `test_closed_pr_no_task_issue_cleans_physical_resources` verifies cleanup call

Closes #1433

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## Executor Instructions
1. Create PR using the title and body above
2. After PR creation, update flow state to record `pr_ref`
3. Do NOT push directly — PR creation will handle the push
