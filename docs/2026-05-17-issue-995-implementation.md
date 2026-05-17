# Issue #995 Flow Conflict Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix vibe3 flow show branch selection bug by implementing automatic conflict resolution with Fail Fast behavior

**Architecture:** Single-file modification in issue_branch_resolver.py, adding two helper functions and refactoring main resolver to use get_flows_by_issue() for precision + conflict detection

**Tech Stack:** Python 3.12+, pytest, UserError exceptions, SQLiteClient

---

## File Structure

**Modified:**
- `src/vibe3/utils/issue_branch_resolver.py` (~100 lines total)
  - Add `_format_flow_details()` helper (15 lines)
  - Add `_resolve_best_flow_from_candidates()` decision logic (40 lines)
  - Refactor `resolve_issue_branch_input()` main flow (45 lines)

**Created:**
- `tests/vibe3/test_utils/__init__.py` (empty file for test discovery)
- `tests/vibe3/test_utils/test_issue_branch_resolver.py` (120 lines, 6 test scenarios)

---

## Task 1: Setup Test Infrastructure

**Files:**
- Create: `tests/vibe3/test_utils/__init__.py`
- Create: `tests/vibe3/test_utils/test_issue_branch_resolver.py`

- [ ] **Step 1: Create test directory structure**

```bash
mkdir -p tests/vibe3/test_utils
touch tests/vibe3/test_utils/__init__.py
```

- [ ] **Step 2: Create test file with imports and fixtures**

```python
"""Tests for issue_branch_resolver conflict detection."""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Any

from vibe3.utils.issue_branch_resolver import (
    resolve_issue_branch_input,
    _format_flow_details,
    _resolve_best_flow_from_candidates,
)
from vibe3.exceptions import UserError


@pytest.fixture
def mock_flow_service() -> Mock:
    """Create mock FlowService with store."""
    service = Mock()
    service.store = Mock()
    service.get_flow_state = Mock()
    return service


@pytest.fixture
def mock_store(mock_flow_service: Mock) -> Mock:
    """Get store from mock_flow_service."""
    return mock_flow_service.store
```

- [ ] **Step 3: Verify test file created**

Run: `ls -la tests/vibe3/test_utils/`
Expected: `__init__.py` and `test_issue_branch_resolver.py` exist

- [ ] **Step 4: Commit test infrastructure**

```bash
git add tests/vibe3/test_utils/
git commit -m "test: setup test infrastructure for issue_branch_resolver"
```

---

## Task 2: Test Single Non-Aborted Flow Auto-Selection

**Files:**
- Modify: `tests/vibe3/test_utils/test_issue_branch_resolver.py:30`

**Scenario**: Single active flow → Auto-select without error

- [ ] **Step 1: Write test for single non-aborted flow**

```python
def test_single_non_aborted_flow_auto_select(mock_flow_service: Mock, mock_store: Mock):
    """Test auto-selection when only one non-aborted flow exists."""
    # Arrange: Single active flow with issue binding
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        }
    ]

    # Act: Resolve issue number
    result = resolve_issue_branch_input("976", mock_flow_service)

    # Assert: Returns correct branch
    assert result == "dev/issue-976"
    mock_store.get_flows_by_issue.assert_called_once_with(976, role="task")
```

- [ ] **Step 2: Run test to verify it fails (RED)**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_single_non_aborted_flow_auto_select -v`
Expected: FAIL with "cannot import name '_format_flow_details'" or "_resolve_best_flow_from_candidates"

- [ ] **Step 3: Add placeholder helper functions (minimal implementation)**

Modify: `src/vibe3/utils/issue_branch_resolver.py`

Add imports at top:
```python
from typing import Any
from vibe3.exceptions import UserError
```

Add placeholder functions after imports:
```python
def _format_flow_details(flow: dict[str, Any]) -> str:
    """Format single flow details - placeholder."""
    return "placeholder"


def _resolve_best_flow_from_candidates(
    candidates: list[dict[str, Any]],
    issue_number: int,
    flow_service: object,
) -> str:
    """Select best flow - placeholder."""
    return "placeholder"
```

- [ ] **Step 4: Run test to verify it still fails**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_single_non_aborted_flow_auto_select -v`
Expected: FAIL with assertion error "result != 'dev/issue-976'"

- [ ] **Step 5: Implement `_format_flow_details()` helper**

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

- [ ] **Step 6: Implement `_resolve_best_flow_from_candidates()` decision logic**

```python
def _resolve_best_flow_from_candidates(
    candidates: list[dict[str, Any]],
    issue_number: int,
    flow_service: object,
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

- [ ] **Step 7: Refactor `resolve_issue_branch_input()` main function**

Replace existing function (lines 16-40):

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

- [ ] **Step 8: Run test to verify it passes (GREEN)**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_single_non_aborted_flow_auto_select -v`
Expected: PASS with "1 passed"

- [ ] **Step 9: Commit first implementation**

```bash
git add src/vibe3/utils/issue_branch_resolver.py tests/vibe3/test_utils/test_issue_branch_resolver.py
git commit -m "feat: add flow conflict detection with single flow auto-selection"
```

---

## Task 3: Test Multiple Non-Aborted with One Active Auto-Selection

**Files:**
- Modify: `tests/vibe3/test_utils/test_issue_branch_resolver.py:32`

**Scenario**: One aborted + one active → Auto-select active

- [ ] **Step 1: Write test for multiple non-aborted flows**

```python
def test_multiple_non_aborted_one_active_auto_select(mock_flow_service: Mock, mock_store: Mock):
    """Test auto-selection when one aborted and one active flow exist."""
    # Arrange: One aborted, one active
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "task/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        }
    ]

    # Act: Resolve issue number
    result = resolve_issue_branch_input("976", mock_flow_service)

    # Assert: Returns active branch
    assert result == "dev/issue-976"
    mock_store.get_flows_by_issue.assert_called_once_with(976, role="task")
```

- [ ] **Step 2: Run test to verify it passes (existing logic handles this)**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_multiple_non_aborted_one_active_auto_select -v`
Expected: PASS with "1 passed"

- [ ] **Step 3: Commit test addition**

```bash
git add tests/vibe3/test_utils/test_issue_branch_resolver.py
git commit -m "test: add test for multiple non-aborted flows with one active"
```

---

## Task 4: Test Multiple Active Flows Conflict Error

**Files:**
- Modify: `tests/vibe3/test_utils/test_issue_branch_resolver.py:62`

**Scenario**: Multiple active flows → Raise UserError with conflict message

- [ ] **Step 1: Write test for multiple active flows conflict**

```python
def test_multiple_active_flows_conflict_error(mock_flow_service: Mock, mock_store: Mock):
    """Test UserError raised when multiple active flows exist."""
    # Arrange: Two active flows (conflict)
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        },
        {
            "branch": "dev/issue-976-copy",
            "flow_status": "active",
            "pr_ref": None,
        }
    ]

    # Act & Assert: Raises UserError
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    # Verify error message format
    error_msg = str(exc_info.value)
    assert "Multiple active flows detected for issue #976" in error_msg
    assert "dev/issue-976 (status: active, pr: #990)" in error_msg
    assert "dev/issue-976-copy (status: active, pr: none)" in error_msg
    assert "Use 'vibe3 flow abort <branch>'" in error_msg
```

- [ ] **Step 2: Run test to verify it passes (existing logic handles this)**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_multiple_active_flows_conflict_error -v`
Expected: PASS with "1 passed"

- [ ] **Step 3: Commit test addition**

```bash
git add tests/vibe3/test_utils/test_issue_branch_resolver.py
git commit -m "test: add test for multiple active flows conflict error"
```

---

## Task 5: Test All Aborted Flows Error

**Files:**
- Modify: `tests/vibe3/test_utils/test_issue_branch_resolver.py:92`

**Scenario**: All flows aborted → Raise UserError with restore guidance

- [ ] **Step 1: Write test for all aborted flows**

```python
def test_all_aborted_flows_error(mock_flow_service: Mock, mock_store: Mock):
    """Test UserError raised when all flows are aborted."""
    # Arrange: All aborted
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "task/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        }
    ]

    # Act & Assert: Raises UserError
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    # Verify error message format
    error_msg = str(exc_info.value)
    assert "All flows for issue #976 are aborted" in error_msg
    assert "task/issue-976 (status: aborted, pr: none)" in error_msg
    assert "Use 'vibe3 flow restore <branch>'" in error_msg
```

- [ ] **Step 2: Run test to verify it passes (existing logic handles this)**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_all_aborted_flows_error -v`
Expected: PASS with "1 passed"

- [ ] **Step 3: Commit test addition**

```bash
git add tests/vibe3/test_utils/test_issue_branch_resolver.py
git commit -m "test: add test for all aborted flows error"
```

---

## Task 6: Test No Binding with Candidates Error

**Files:**
- Modify: `tests/vibe3/test_utils/test_issue_branch_resolver.py:117`

**Scenario**: No binding but unbound candidates exist → Raise UserError with bind guidance

- [ ] **Step 1: Write test for no binding with candidates**

```python
def test_no_binding_with_candidates_error(mock_flow_service: Mock, mock_store: Mock):
    """Test UserError when flows exist but without issue binding."""
    # Arrange: No binding, but unbound candidate exists
    mock_store.get_flows_by_issue.return_value = []  # No binding
    mock_flow_service.get_flow_state.return_value = {
        "branch": "dev/issue-976",
        "flow_status": "active",
        "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
    }

    # Act & Assert: Raises UserError
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    # Verify error message format
    error_msg = str(exc_info.value)
    assert "Found flow(s) for issue #976 candidates but without task binding" in error_msg
    assert "dev/issue-976 (status: active, pr: #990)" in error_msg
    assert "Use 'vibe3 flow bind 976 --role task'" in error_msg

    # Verify candidate iteration was called
    mock_flow_service.get_flow_state.assert_called()
```

- [ ] **Step 2: Run test to verify it passes (existing logic handles this)**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_no_binding_with_candidates_error -v`
Expected: PASS with "1 passed"

- [ ] **Step 3: Commit test addition**

```bash
git add tests/vibe3/test_utils/test_issue_branch_resolver.py
git commit -m "test: add test for no binding with candidates error"
```

---

## Task 7: Test No Flows At All Error

**Files:**
- Modify: `tests/vibe3/test_utils/test_issue_branch_resolver.py:147`

**Scenario**: No flows at all → Raise UserError with vibe-new guidance

- [ ] **Step 1: Write test for no flows at all**

```python
def test_no_flows_at_all_error(mock_flow_service: Mock, mock_store: Mock):
    """Test UserError when no flows exist for issue."""
    # Arrange: No flows at all
    mock_store.get_flows_by_issue.return_value = []  # No binding
    mock_flow_service.get_flow_state.return_value = None  # No unbound candidates

    # Act & Assert: Raises UserError
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    # Verify error message format
    error_msg = str(exc_info.value)
    assert "No flow found for issue #976" in error_msg
    assert "Use '/vibe-new issue 976'" in error_msg
```

- [ ] **Step 2: Run test to verify it passes (existing logic handles this)**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_no_flows_at_all_error -v`
Expected: PASS with "1 passed"

- [ ] **Step 3: Commit test addition**

```bash
git add tests/vibe3/test_utils/test_issue_branch_resolver.py
git commit -m "test: add test for no flows at all error"
```

---

## Task 8: Test Helper Function `_format_flow_details()`

**Files:**
- Modify: `tests/vibe3/test_utils/test_issue_branch_resolver.py:170`

**Scenario**: Verify helper formats flow details correctly

- [ ] **Step 1: Write test for _format_flow_details with PR**

```python
def test_format_flow_details_with_pr():
    """Test _format_flow_details formats flow with PR correctly."""
    flow = {
        "branch": "dev/issue-976",
        "flow_status": "active",
        "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
    }

    result = _format_flow_details(flow)

    assert result == "dev/issue-976 (status: active, pr: #990)"
```

- [ ] **Step 2: Write test for _format_flow_details without PR**

```python
def test_format_flow_details_without_pr():
    """Test _format_flow_details formats flow without PR correctly."""
    flow = {
        "branch": "task/issue-976",
        "flow_status": "aborted",
        "pr_ref": None,
    }

    result = _format_flow_details(flow)

    assert result == "task/issue-976 (status: aborted, pr: none)"
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py::test_format_flow_details_with_pr tests/vibe3/test_utils/test_issue_branch_resolver.py::test_format_flow_details_without_pr -v`
Expected: PASS with "2 passed"

- [ ] **Step 4: Commit helper tests**

```bash
git add tests/vibe3/test_utils/test_issue_branch_resolver.py
git commit -m "test: add tests for _format_flow_details helper"
```

---

## Task 9: Run Full Test Suite

**Files:**
- Test: `tests/vibe3/test_utils/test_issue_branch_resolver.py`

- [ ] **Step 1: Run all tests in test file**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py -v`
Expected: All 8 tests PASS

- [ ] **Step 2: Run with coverage report**

Run: `uv run pytest tests/vibe3/test_utils/test_issue_branch_resolver.py --cov=vibe3.utils.issue_branch_resolver --cov-report=term-missing`
Expected: Coverage > 90% for issue_branch_resolver.py

- [ ] **Step 3: Check for any mypy type errors**

Run: `uv run mypy src/vibe3/utils/issue_branch_resolver.py --strict`
Expected: No errors

- [ ] **Step 4: Run pre-commit checks**

Run: `pre-commit run --files src/vibe3/utils/issue_branch_resolver.py tests/vibe3/test_utils/test_issue_branch_resolver.py`
Expected: All checks pass

---

## Task 10: Manual Validation with Real Issue #976

**Files:**
- Test: Issue #976 scenario from original bug report

- [ ] **Step 1: Verify fix resolves original issue #976 scenario**

Query database to confirm setup:
```bash
sqlite3 "$(git rev-parse --git-common-dir)/vibe3/handoff.db" "SELECT branch, flow_slug FROM flow_state WHERE branch LIKE '%976%'"
```
Expected: Shows both `task/issue-976` and `dev/issue-976` flows

Check binding:
```bash
sqlite3 "$(git rev-parse --git-common-dir)/vibe3/handoff.db" "SELECT branch, issue_number, issue_role FROM flow_issue_links WHERE issue_number = 976"
```
Expected: Shows binding for `dev/issue-976` only

- [ ] **Step 2: Test vibe3 flow show 976 resolves to correct branch**

Run: `vibe3 flow show 976`
Expected: Returns `dev/issue-976` (with binding), not `task/issue-976`

- [ ] **Step 3: Test vibe3 task show 976 resolves correctly**

Run: `vibe3 task show 976`
Expected: Uses `dev/issue-976` flow

- [ ] **Step 4: Document validation results**

Add comment to Issue #995 with test results:
```
✅ Fix validated with issue #976 scenario:
- Database has both task/issue-976 and dev/issue-976 flows
- Only dev/issue-976 has issue binding
- vibe3 flow show 976 correctly returns dev/issue-976
- vibe3 task show 976 uses correct flow
```

---

## Task 11: Final Commit and Documentation

**Files:**
- None (summary commit)

- [ ] **Step 1: Create final implementation summary commit**

```bash
git add -A
git commit -m "feat(issue-995): complete flow conflict detection implementation

Implement automatic flow selection with conflict detection:

- Auto-select single non-aborted flow
- Raise UserError for multiple active flows conflicts
- Smart warnings for unbound or aborted flows
- 6 test scenarios covering all edge cases

Fixes #995"
```

- [ ] **Step 2: Push to remote branch**

```bash
git push origin dev/issue-995
```

- [ ] **Step 3: Update Issue #995 status**

Comment on issue with completion summary and test results.

---

## Self-Review Checklist

**Completed after plan writing:**

✅ **Spec coverage check**: All 6 test scenarios from spec matrix are implemented
✅ **Placeholder scan**: No TBD, TODO, or incomplete steps
✅ **Type consistency**: All functions use consistent signatures from spec
✅ **Test coverage**: Each scenario has dedicated test with clear assertions
✅ **TDD flow**: Each task follows RED-GREEN-REFACTOR pattern
✅ **Error messages**: All error scenarios have actionable guidance per spec

---

## Execution Handoff

Plan complete and saved to `docs/2026-05-17-issue-995-implementation.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
