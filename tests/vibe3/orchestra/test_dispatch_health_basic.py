"""Core dispatch health check scenarios: basic pass/fail.

Tests for open/closed issues, done flows, and open PRs.
"""

from tests.vibe3.orchestra.helpers.dispatch_health import (
    make_check_result,
    make_health_coordinator,
    make_issue,
)
from vibe3.models.orchestration import IssueState


class TestPreDispatchHealthBasic:
    """Basic pass/fail health check scenarios."""

    def test_health_check_detects_closed_issue(self) -> None:
        """Health check should return False for consistency failures."""
        coord, mocks = make_health_coordinator(
            store_flow_state={"branch": "task/issue-42", "flow_status": "active"},
            check_result=make_check_result(
                is_valid=False,
                issues=["Branch 'task/issue-42' no longer exists locally"],
            ),
        )

        issue = make_issue(42, state=IssueState.BLOCKED, github_state="CLOSED")
        result = coord._check_dispatch_health(issue)

        assert (
            result is False
        ), "Health check should return False for consistency failures"
        mocks["flow_blocker"].block_flow.assert_called_once()
        call_args = mocks["flow_blocker"].block_flow.call_args
        assert call_args[1]["branch"] == "task/issue-42"
        assert "Health check failed" in call_args[1]["reason"]
        assert call_args[1]["actor"] == "orchestra:dispatcher"

    def test_health_check_passes_for_open_issue(self) -> None:
        """Health check should return True for healthy active flows."""
        coord, _ = make_health_coordinator(
            store_flow_state={"branch": "task/issue-43", "flow_status": "active"},
            check_result=make_check_result(branch="task/issue-43"),
        )

        issue = make_issue(43, state=IssueState.READY)
        result = coord._check_dispatch_health(issue)

        assert result is True, "Health check should pass for healthy active flow"

    def test_health_check_closes_issue_with_merged_pr(self) -> None:
        """Health check should return False if flow is done (PR merged)."""
        coord, mocks = make_health_coordinator(
            store_flow_state={"branch": "task/issue-44", "flow_status": "done"},
            check_result=make_check_result(branch="task/issue-44"),
        )

        issue = make_issue(44, state=IssueState.IN_PROGRESS)
        result = coord._check_dispatch_health(issue)

        assert result is False, "Health check should fail for done flow"

    def test_health_check_passes_for_open_pr(self) -> None:
        """Health check should pass for issue with open PR (still active)."""
        coord, _ = make_health_coordinator(
            store_flow_state={"branch": "task/issue-45", "flow_status": "active"},
            check_result=make_check_result(branch="task/issue-45"),
        )

        issue = make_issue(45, state=IssueState.REVIEW)
        result = coord._check_dispatch_health(issue)

        assert result is True, "Health check should pass for active flow with open PR"
