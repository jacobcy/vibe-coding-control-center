"""Tests for classify_task_issues_for_rendering open_issue_numbers computation."""

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.task.status import classify_task_issues_for_rendering


def _make_config() -> MagicMock:
    """Create a minimal mock OrchestraConfig."""
    config = MagicMock()
    config.supervisor_handoff.issue_label = "supervisor"
    return config


def _issue(
    number: int,
    state: str | IssueState | None,
    labels: list[str] | None = None,
    blocked_reason: str | None = None,
) -> dict:
    """Build a minimal issue dict for testing.

    Args:
        number: Issue number
        state: Issue state (string, IssueState enum, or None)
        labels: Issue labels
        blocked_reason: Blocked reason text

    Returns:
        Issue dict with state as IssueState enum (matching real data structure)
    """
    # Convert string state to IssueState enum (matching real data structure)
    if isinstance(state, str):
        state_enum = IssueState(state)
    else:
        state_enum = state

    issue = {
        "number": number,
        "state": state_enum,  # Use IssueState enum, not string
        "title": f"Issue #{number}",
        "labels": labels or [],
        "assignee": None,
    }
    if blocked_reason is not None:
        issue["blocked_reason"] = blocked_reason
    return issue


def test_open_issue_numbers_excludes_done():
    """DONE issues must not appear in open_issue_numbers."""
    issues = [
        _issue(1, IssueState.IN_PROGRESS.value),
        _issue(2, IssueState.DONE.value),
        _issue(3, IssueState.BLOCKED.value),
    ]
    result = classify_task_issues_for_rendering(issues, _make_config())
    assert result["open_issue_numbers"] == {1, 3}


def test_open_issue_numbers_includes_all_non_done_states():
    """All non-DONE states must be included in open_issue_numbers."""
    states = [
        IssueState.READY,
        IssueState.CLAIMED,
        IssueState.IN_PROGRESS,
        IssueState.BLOCKED,
        IssueState.HANDOFF,
        IssueState.REVIEW,
        IssueState.MERGE_READY,
    ]
    issues = [_issue(i, state.value) for i, state in enumerate(states, start=10)]
    result = classify_task_issues_for_rendering(issues, _make_config())
    assert result["open_issue_numbers"] == {10, 11, 12, 13, 14, 15, 16}


def test_open_issue_numbers_empty_when_no_issues():
    """Empty input produces an empty set."""
    result = classify_task_issues_for_rendering([], _make_config())
    assert result["open_issue_numbers"] == set()


def test_open_issue_numbers_all_done():
    """When every issue is DONE, the set is empty."""
    issues = [
        _issue(1, IssueState.DONE.value),
        _issue(2, IssueState.DONE.value),
    ]
    result = classify_task_issues_for_rendering(issues, _make_config())
    assert result["open_issue_numbers"] == set()


def test_open_issue_numbers_includes_missing_state():
    """Issues with None state (missing state) should be included as open."""
    issues = [
        _issue(1, None),
        _issue(2, IssueState.DONE.value),
    ]
    result = classify_task_issues_for_rendering(issues, _make_config())
    assert result["open_issue_numbers"] == {1}


def test_blocked_issues_not_in_other_bucket():
    """BLOCKED issues must not appear in bucketed_items['other']."""
    issues = [
        _issue(1, IssueState.BLOCKED.value, labels=[]),
        _issue(2, IssueState.IN_PROGRESS.value, labels=[]),
    ]
    result = classify_task_issues_for_rendering(issues, _make_config())
    # BLOCKED issues should not be in the 'other' bucket
    other_items = result["bucketed_items"].get("other", [])
    other_numbers = {item["number"] for item in other_items}
    assert 1 not in other_numbers, "BLOCKED issue #1 should not be in 'other' bucket"
    # Non-blocked issue should be processed normally
    assert 2 in result["open_issue_numbers"]


def test_blocked_items_contains_blocked_issues():
    """BLOCKED issues must appear in blocked_items."""
    issues = [
        _issue(1, IssueState.BLOCKED.value, labels=[]),
        _issue(2, IssueState.IN_PROGRESS.value, labels=[]),
    ]
    result = classify_task_issues_for_rendering(issues, _make_config())
    blocked_numbers = {item["number"] for item in result["blocked_items"]}
    assert 1 in blocked_numbers, "BLOCKED issue #1 should be in blocked_items"
    assert (
        2 not in blocked_numbers
    ), "Non-blocked issue #2 should not be in blocked_items"


def test_blocked_items_includes_blocked_reason_field():
    """BLOCKED issues must include blocked_reason field in API response.

    This test verifies that blocked_reason flows through the entire pipeline:
    1. Issue with blocked_reason in input
    2. classify_task_issues_for_rendering extracts BLOCKED issues
    3. _issue_to_dict formats the issue with blocked_reason field
    """
    from vibe3.services.task.status import _issue_to_dict

    # Create BLOCKED issues with/without blocked_reason
    issues = [
        _issue(
            1, IssueState.BLOCKED.value, labels=[], blocked_reason="Waiting for #42"
        ),
        _issue(2, IssueState.BLOCKED.value, labels=[]),  # No blocked_reason field
    ]

    # Step 1: classify_task_issues_for_rendering extracts BLOCKED issues
    result = classify_task_issues_for_rendering(issues, _make_config())
    blocked_items = result["blocked_items"]
    assert len(blocked_items) == 2, "Both BLOCKED issues should be extracted"

    # Step 2: _issue_to_dict formats issues with blocked_reason field
    issue_1_dict = _issue_to_dict(blocked_items[0])
    assert (
        issue_1_dict.get("blocked_reason") == "Waiting for #42"
    ), "blocked_reason should be preserved in formatted dict"

    issue_2_dict = _issue_to_dict(blocked_items[1])
    assert (
        "blocked_reason" in issue_2_dict
    ), "blocked_reason field should exist even if None"
    assert issue_2_dict.get("blocked_reason") is None, "blocked_reason should be None"
