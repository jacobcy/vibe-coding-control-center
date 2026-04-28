"""Unit tests for StatusQueryService utility functions."""

from vibe3.models.orchestration import IssueState
from vibe3.services.status_query_service import (
    is_auto_task_branch,
    is_canonical_task_branch,
    issue_priority,
)


class TestIssuePriority:
    """Tests for issue priority sorting."""

    def test_in_progress_has_highest_priority(self) -> None:
        """IN_PROGRESS should sort before all other states."""
        assert issue_priority(IssueState.IN_PROGRESS) < issue_priority(IssueState.READY)
        assert issue_priority(IssueState.IN_PROGRESS) < issue_priority(
            IssueState.BLOCKED
        )

    def test_ready_before_blocked(self) -> None:
        """READY should sort before BLOCKED."""
        assert issue_priority(IssueState.READY) < issue_priority(IssueState.BLOCKED)

    def test_blocked_has_lower_priority(self) -> None:
        """BLOCKED should have lower priority than IN_PROGRESS and READY."""
        assert issue_priority(IssueState.BLOCKED) > issue_priority(IssueState.READY)
        assert issue_priority(IssueState.BLOCKED) > issue_priority(
            IssueState.IN_PROGRESS
        )


class TestBranchClassification:
    """Tests for branch name classification helpers."""

    def test_is_auto_task_branch_recognizes_pattern(self) -> None:
        """Should recognize task/issue-N pattern."""
        assert is_auto_task_branch("task/issue-278") is True
        assert is_auto_task_branch("task/issue-320") is True
        assert is_auto_task_branch("dev/feature") is False
        assert is_auto_task_branch("main") is False

    def test_is_canonical_task_branch_matches_issue_number(self) -> None:
        """Should match when branch exactly matches task/issue-N."""
        assert is_canonical_task_branch("task/issue-278", 278) is True
        assert is_canonical_task_branch("task/issue-278", 320) is False
        assert is_canonical_task_branch("dev/issue-278", 278) is False
        assert is_canonical_task_branch("task/issue-278", None) is False
