# Issue #995 Resolution Design: Flow Conflict Detection

**Date**: 2026-05-17
**Issue**: #995 - bug: vibe3 flow show <issue-number> 返回无绑定的 task 分支而非有绑定的 dev 分支
**Status**: Draft for review

---

## Problem Statement

When multiple flows exist for the same issue number (e.g., `task/issue-976` and `dev/issue-976`), `vibe3 flow show 976` returns the wrong branch:

- **Current behavior**: Returns first candidate that has a flow_state (usually `task/issue-976`)
- **Issue**: Does not check which branch has the actual issue binding
- **Impact**: Commands like `flow show`, `pr show`, `task show` may query wrong flows

**Root cause** in `resolve_issue_branch_input()` (line 34-36):
```python
for candidate in iter_issue_branch_candidates(issue_number):
    if get_flow_state(candidate):  # Only checks existence
        return candidate           # Returns without binding check
```

---

## Solution Overview

Implement **automatic conflict resolution** with **Fail Fast** when conflicts cannot be auto-resolved:

1. **Priority-based selection**: Auto-select non-aborted flows when possible
2. **Conflict detection**: Raise `UserError` when multiple active flows exist
3. **Smart warnings**: Provide actionable guidance for unbound or aborted flows

**User interaction flow**:
- Single non-aborted flow → Auto-select (no user action)
- Multiple active flows → Show conflict + abort guidance
- All aborted flows → Show status + restore guidance
- No binding → Show candidates + bind guidance

---

## Core Algorithm

### Decision Priority (from highest to lowest)

1. **Non-aborted flows**: If only one flow has `status != "aborted"`, auto-select
2. **Active flows conflict**: If multiple flows have `status == "active"`, raise `UserError`
3. **All aborted**: If all candidates are aborted, raise `UserError` with restore guidance
4. **No binding**: Check unbound candidates, raise `UserError` with bind guidance

### Pseudocode

```
Input: issue_number (e.g., 976)

Step 1: Query flows with issue binding
  candidates = store.get_flows_by_issue(issue_number, role="task")

Step 2: If candidates exist
  non_aborted = filter(candidates, status != "aborted")

  if len(non_aborted) == 1:
    return non_aborted[0].branch  # Auto-select

  active = filter(candidates, status == "active")

  if len(active) > 1:
    raise UserError("Multiple active flows detected...")

  if not non_aborted:
    raise UserError("All flows are aborted...")

Step 3: If no binding, check unbound candidates
  for candidate in iter_issue_branch_candidates(issue_number):
    if get_flow_state(candidate):
      unbound_candidates.append(candidate)

  if unbound_candidates:
    raise UserError("Found flows without task binding...")

Step 4: No flows at all
  raise UserError("No flow found...")
```

---

## Implementation Details

### File: `src/vibe3/utils/issue_branch_resolver.py`

#### New Functions

**1. `_resolve_best_flow_from_candidates()`**

```python
def _resolve_best_flow_from_candidates(
    candidates: list[dict[str, Any]],
    issue_number: int,
    flow_service: FlowService,
) -> str:
    """Select best flow or raise UserError for conflicts.

    Args:
        candidates: List of flow dicts from get_flows_by_issue()
        issue_number: Issue number being resolved
        flow_service: FlowService instance for status queries

    Returns:
        Selected branch name

    Raises:
        UserError: When multiple active flows conflict or all aborted
    """
    # Priority 1: Non-aborted flows
    non_aborted = [f for f in candidates if f["flow_status"] != "aborted"]

    if len(non_aborted) == 1:
        # Auto-select the only non-aborted flow
        return non_aborted[0]["branch"]

    # Priority 2: Check for multiple active flows (conflict)
    active = [f for f in candidates if f["flow_status"] == "active"]

    if len(active) > 1:
        # Conflict: multiple active flows
        details = "\n  - ".join(_format_flow_details(f) for f in active)
        raise UserError(
            f"Multiple active flows detected for issue #{issue_number}:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow abort <branch>' to resolve the conflict."
        )

    # Priority 3: All flows are aborted
    if not non_aborted and candidates:
        details = "\n  - ".join(_format_flow_details(f) for f in candidates)
        raise UserError(
            f"All flows for issue #{issue_number} are aborted:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow restore <branch>' to reactivate a flow."
        )

    # Fallback: Should not reach here if candidates is non-empty
    return candidates[0]["branch"]
```

**2. `_format_flow_details()`**

```python
def _format_flow_details(flow: dict[str, Any]) -> str:
    """Format single flow details: branch (status: X, pr: Y).

    Args:
        flow: Flow state dict from database

    Returns:
        Human-readable string like "dev/issue-976 (status: active, pr: #990)"
    """
    branch = flow.get("branch", "unknown")
    status = flow.get("flow_status", "unknown")

    # PR info: check pr_ref or derive from pr_number
    pr_ref = flow.get("pr_ref")
    if pr_ref:
        # Extract PR number from URL (e.g., "https://github.com/.../pull/990")
        pr_number = pr_ref.split("/")[-1]
        pr_info = f"pr: #{pr_number}"
    else:
        pr_info = "pr: none"

    return f"{branch} (status: {status}, {pr_info})"
```

#### Modified Function: `resolve_issue_branch_input()`

```python
def resolve_issue_branch_input(branch: str | None, flow_service: object) -> str | None:
    """Resolve numeric issue input with conflict detection.

    Changes from original:
    - Uses get_flows_by_issue() for bound flows first
    - Conflict detection for multiple active flows
    - Smart warnings for unbound or aborted candidates

    Args:
        branch: User input (branch name or issue number)
        flow_service: FlowService instance

    Returns:
        Resolved branch name

    Raises:
        UserError: When conflicts or missing flows detected
    """
    # Step 1: Check input type
    if branch is None or not branch.strip().isdigit():
        return branch

    issue_number = int(branch.strip())
    store = getattr(flow_service, "store")

    # Step 2: Query flows with issue binding
    candidates = store.get_flows_by_issue(issue_number, role="task")

    if candidates:
        # Step 3: Resolve with conflict detection
        return _resolve_best_flow_from_candidates(candidates, issue_number, flow_service)

    # Step 4: Check unbound candidates (smart warning)
    unbound_candidates = []
    for candidate in iter_issue_branch_candidates(issue_number):
        state = flow_service.get_flow_state(candidate)
        if state:
            unbound_candidates.append(state)

    if unbound_candidates:
        # Smart warning: has candidates but no binding
        details = "\n  - ".join(_format_flow_details(f) for f in unbound_candidates)
        raise UserError(
            f"Found flow(s) for issue #{issue_number} candidates but without task binding:\n"
            f"  - {details}\n\n"
            f"Use 'vibe3 flow bind {issue_number} --role task' to link the issue."
        )

    # Step 5: No flows at all
    raise UserError(
        f"No flow found for issue #{issue_number}. "
        f"Use '/vibe-new issue {issue_number}' to create a flow."
    )
```

---

## Integration Impact

### Calling Sites (No Changes Required)

Existing callers already handle `UserError`:

1. `commands/flow_status.py:84` - Already has exception handling
2. `commands/handoff_read.py:115, 172` - Already has exception handling
3. `utils/branch_arg.py:34` - Already has exception handling
4. `services/task_show_service.py:115` - Already has exception handling

**API stability**: Function signature unchanged, only internal logic enhanced.

### Performance Impact

**Query pattern changes**:
- **Old**:最多 2 次 `get_flow_state()` (遍历候选)
- **New**:
  - 有绑定: 1 次 `get_flows_by_issue()` (精准定位)
  - 无绑定: 1 次 `get_flows_by_issue()` + 最多 2 次 `get_flow_state()` (候选检查)

**Impact assessment**:
- ✅ Better performance for bound flows (one query vs. two)
- ⚠️ Slightly slower for unbound flows (needs candidate check)

---

## Error Handling Strategy

### Exception Type

Use existing `UserError` (recoverable user input errors):

```python
from vibe3.exceptions import UserError
```

All conflict scenarios raise `UserError` because:
- User can resolve via commands (`flow abort`, `flow restore`, `flow bind`)
- No system-level intervention required

### Error Messages Design

Each scenario provides **actionable guidance**:

1. **Multiple active flows**:
   ```
   Multiple active flows detected for issue #976:
     - dev/issue-976 (status: active, pr: #990)
     - dev/issue-976-copy (status: active, pr: none)

   Use 'vibe3 flow abort <branch>' to resolve the conflict.
   ```

2. **All aborted flows**:
   ```
   All flows for issue #976 are aborted:
     - task/issue-976 (status: aborted, pr: none)

   Use 'vibe3 flow restore <branch>' to reactivate a flow.
   ```

3. **No binding**:
   ```
   Found flow(s) for issue #976 candidates but without task binding:
     - dev/issue-976 (status: active, pr: #990)

   Use 'vibe3 flow bind 976 --role task' to link the issue.
   ```

4. **No flows**:
   ```
   No flow found for issue #976. Use '/vibe-new issue 976' to create a flow.
   ```

---

## Testing Strategy

### Test File

`tests/vibe3/test_utils/test_issue_branch_resolver.py`

### Test Scenarios Matrix

| Scenario | Candidates | Expected Result |
|----------|-----------|-----------------|
| Single non-aborted | `[dev/976 (active)]` | Return `dev/976` |
| Multiple non-aborted, 1 active | `[task/976 (aborted), dev/976 (active)]` | Return `dev/976` (auto-select) |
| Multiple active (conflict) | `[dev/976 (active), dev/976-copy (active)]` | Raise `UserError` |
| All aborted | `[task/976 (aborted)]` | Raise `UserError` |
| No binding, has candidates | `[]` (but unbound `dev/976` exists) | Raise `UserError` (smart warning) |
| No flows at all | `[]` | Raise `UserError` |

### Mock Dependencies

```python
# Mock store.get_flows_by_issue()
mock_store.get_flows_by_issue.return_value = [
    {"branch": "dev/issue-976", "flow_status": "active", "pr_ref": "..."},
]

# Mock flow_service.get_flow_state()
mock_flow_service.get_flow_state.return_value = {
    "branch": "dev/issue-976",
    "flow_status": "active",
}
```

---

## Compliance Checklist

- ✅ **Fail Fast**: Conflicts detected immediately, no silent fallbacks
- ✅ **User-friendly errors**: Each scenario provides actionable guidance
- ✅ **Minimal changes**: Only one file modified, no API changes
- ✅ **Reuse existing methods**: Uses `get_flows_by_issue()` for precision
- ✅ **Test coverage**: 6 test scenarios covering all edge cases

---

## Open Questions (Resolved)

1. **Q: Branch selection priority?**
   A: Non-aborted → Active → Aborted → Fallback (resolved in design discussion)

2. **Q: Conflict display format?**
   A: Show status + PR info (option C, simpler than commit count)

3. **Q: User interaction flow?**
   A: Auto-select when clear, raise error when ambiguous (option C)

4. **Q: Unbound candidates handling?**
   A: Smart warning with bind guidance (option C)

---

## Implementation Plan Outline

Phase 1: Core implementation
  - Add `_format_flow_details()` helper
  - Add `_resolve_best_flow_from_candidates()` decision logic
  - Modify `resolve_issue_branch_input()` main flow

Phase 2: Testing
  - Create test file
  - Implement 6 test scenarios
  - Verify error messages format

Phase 3: Validation
  - Run test suite
  - Manual testing with issue #976 scenario
  - Check CLI output formatting

---

**Next step**: User reviews this spec before proceeding to implementation plan.
