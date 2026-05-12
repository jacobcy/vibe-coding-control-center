# Fix Directive: PR Merge Check Dead Code

## Blocking Issue
**Finding 1**: PR merge check uses `flow.get("pr_number")` which always returns `None` in production, making the check ineffective.

## Root Cause
The `flow_state` table schema (defined in `sqlite_schema.py:15-44`) does not have a `pr_number` column. It only has `pr_ref` (TEXT, PR URL). Code comment at `flow_read_mixin.py:60` explicitly states: `"pr_number not cached in flow_state yet"`.

## Required Fix

### File: `src/vibe3/orchestra/global_dispatch_coordinator.py`
**Lines 169-171**: Replace:

```python
flow = self._flow_manager.get_flow_for_issue(issue.number)
if flow:
    pr_number = flow.get("pr_number")
```

With:

```python
pr_number = self._flow_manager.get_pr_for_issue(issue.number)
if pr_number:
```

**Why this works**: `FlowManager.get_pr_for_issue()` (line 290-294) has a fallback that calls `self._github.get_pr_for_issue()` via GitHub API when `flow.get("pr_number")` returns None.

### Tests to Update

**File**: `tests/vibe3/orchestra/test_dispatch_health_checks.py`

Update all test methods that mock `flow_manager.get_flow_for_issue.return_value` to instead mock `flow_manager.get_pr_for_issue.return_value`:

- `test_health_check_closes_issue_with_merged_pr`: Mock `get_pr_for_issue` to return PR number
- `test_pr_merged_auto_closes_issue_returns_false`: Mock `get_pr_for_issue` to return PR number
- `test_health_check_passes_for_open_pr`: Mock `get_pr_for_issue` to return PR number
- `test_pr_open_returns_true`: Mock `get_pr_for_issue` to return PR number

## Verification Requirements

1. All existing tests must pass (including the 8 health check tests)
2. Manually verify: `flow.get("pr_number")` is no longer used in the health check method
3. Run: `uv run pytest tests/vibe3/orchestra/test_dispatch_health_checks.py -v`

## Reference
- Audit report: `docs/reports/issue-791-audit-report.md`
- Related dead code patterns (out of scope, noted for future): `flow_dispatch.py:292`, `flow_orchestrator_service.py:76`, `qualify_gate.py:150-151`
