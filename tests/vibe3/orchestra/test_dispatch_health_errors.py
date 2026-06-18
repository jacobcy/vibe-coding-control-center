"""Error resilience dispatch health check scenarios.

Tests for network errors, transient failures, genuine failures,
and block_flow exceptions.
"""

from unittest.mock import MagicMock

from tests.vibe3.orchestra.helpers.dispatch_health import (
    make_check_result,
    make_health_coordinator,
    make_issue,
)
from vibe3.models.orchestration import IssueState


class TestPreDispatchHealthErrors:
    """Error handling and fail-open health check scenarios."""

    def test_health_check_handles_network_error(self) -> None:
        """Health check should fail open on network errors."""
        coord, _ = make_health_coordinator(
            store_flow_state={"branch": "task/issue-46", "flow_status": "active"},
            check_result=make_check_result(
                is_valid=False,
                issues=["Cannot verify task issue #46: network/auth error"],
                branch="task/issue-46",
            ),
        )

        issue = make_issue(46, state=IssueState.READY)
        result = coord._check_dispatch_health(issue)

        assert result is True, "Health check should fail open on network errors"

    def test_health_check_blocks_on_genuine_failure(self) -> None:
        """Health check genuine failure should call FlowService.block_flow."""
        coord, mocks = make_health_coordinator(
            flow_context_branch="task/issue-993",
            store_flow_state={"branch": "task/issue-993", "flow_status": "active"},
            check_result=make_check_result(
                is_valid=False,
                issues=[
                    "plan_ref cannot be verified: "
                    "no worktree for branch 'task/issue-993'"
                ],
                branch="task/issue-993",
            ),
        )
        # Add git client dependency for genuine failure path
        coord._flow_manager.git = MagicMock()

        issue = make_issue(993, state=IssueState.IN_PROGRESS)
        result = coord._check_dispatch_health(issue)

        mocks["flow_blocker"].block_flow.assert_called_once()
        call_args = mocks["flow_blocker"].block_flow.call_args
        assert call_args[1]["branch"] == "task/issue-993"
        assert "Health check failed" in call_args[1]["reason"]
        assert call_args[1]["actor"] == "orchestra:dispatcher"
        assert result is False, "Health check should return False for genuine failure"

    def test_health_check_transient_error_does_not_block(self) -> None:
        """Transient errors should fail open without calling block_flow."""
        coord, mocks = make_health_coordinator(
            store_flow_state={"branch": "task/issue-46", "flow_status": "active"},
            check_result=make_check_result(
                is_valid=False,
                issues=["Cannot verify task issue #46: network/auth error"],
                branch="task/issue-46",
            ),
        )

        issue = make_issue(46, state=IssueState.READY)
        result = coord._check_dispatch_health(issue)

        mocks["flow_blocker"].block_flow.assert_not_called()
        assert result is True, "Health check should fail open on transient errors"

    def test_health_check_handles_block_flow_failure(self) -> None:
        """When block_flow raises, health check should log and return False."""
        coord, mocks = make_health_coordinator(
            store_flow_state={"branch": "task/issue-994", "flow_status": "active"},
            check_result=make_check_result(
                is_valid=False,
                issues=["Branch no longer exists locally"],
                branch="task/issue-994",
            ),
        )
        mocks["flow_blocker"].block_flow.side_effect = RuntimeError(
            "DB connection lost"
        )

        issue = make_issue(994, state=IssueState.IN_PROGRESS)
        result = coord._check_dispatch_health(issue)

        mocks["flow_blocker"].block_flow.assert_called_once()
        assert result is False, "Should return False when block_flow fails"
