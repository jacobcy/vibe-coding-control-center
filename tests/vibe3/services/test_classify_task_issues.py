"""Tests for classify_task_issues_for_rendering open_issue_numbers computation."""

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.task.status import classify_task_issues_for_rendering


def _make_config() -> MagicMock:
    """Create a minimal mock OrchestraConfig."""
    config = MagicMock()
    config.supervisor_handoff.issue_label = "supervisor"
    return config


def _issue(number: int, state: str | None, labels: list[str] | None = None) -> dict:
    """Build a minimal issue dict for testing."""
    return {
        "number": number,
        "state": state,
        "title": f"Issue #{number}",
        "labels": labels or [],
        "assignee": None,
    }


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
