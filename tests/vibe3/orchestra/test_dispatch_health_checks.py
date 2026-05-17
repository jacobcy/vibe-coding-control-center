"""Tests for pre-dispatch health checks.

After unification, _health_check_before_dispatch delegates to
CheckService.verify_branch(). These tests verify the coordinator's
interpretation of CheckService results (fail-open, skip dispatch,
terminal state detection) rather than re-testing CheckService internals.
"""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.check_service import CheckResult


class TestPreDispatchHealthChecks:
    """Test health checks before dispatching issues."""

    def test_health_check_detects_closed_issue(self) -> None:
        """Health check should return False for consistency failures."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10
        config.repo = "owner/repo"
        config.supervisor_handoff = MagicMock()
        config.supervisor_handoff.issue_label = "supervisor"
        capacity = MagicMock()
        github = MagicMock()
        store = MagicMock()
        store.db_path = ":memory:"
        flow_manager = MagicMock()

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
        )

        issue = IssueInfo(
            number=42,
            title="Test issue",
            state=IssueState.BLOCKED,
            labels=["state/blocked"],
            github_state="CLOSED",
        )

        # Mock _flow_context to return a branch
        coordinator._flow_context = MagicMock(return_value=("task/issue-42", None))

        # Mock flow state as active (not terminal)
        store.get_flow_state.return_value = {
            "branch": "task/issue-42",
            "flow_status": "active",
        }

        # Mock CheckService to return invalid result (non-transient)
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.CheckService"
        ) as mock_check_service:
            mock_service = mock_check_service.return_value
            mock_service.verify_branch.return_value = CheckResult(
                is_valid=False,
                issues=["Branch 'task/issue-42' no longer exists locally"],
                branch="task/issue-42",
            )
            result = coordinator._health_check_before_dispatch(issue)

        # Assert - genuine consistency failure should skip dispatch
        assert (
            result is False
        ), "Health check should return False for consistency failures"

    def test_health_check_passes_for_open_issue(self) -> None:
        """Health check should return True for healthy active flows."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10
        config.repo = "owner/repo"
        config.supervisor_handoff = MagicMock()
        config.supervisor_handoff.issue_label = "supervisor"
        capacity = MagicMock()
        github = MagicMock()
        store = MagicMock()
        store.db_path = ":memory:"
        flow_manager = MagicMock()

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
        )

        issue = IssueInfo(
            number=43,
            title="Open issue",
            state=IssueState.READY,
            labels=["state/ready"],
            github_state="OPEN",
        )

        # Mock _flow_context to return a branch
        coordinator._flow_context = MagicMock(return_value=("task/issue-43", None))

        # Mock flow state as active
        store.get_flow_state.return_value = {
            "branch": "task/issue-43",
            "flow_status": "active",
        }

        # Mock CheckService to return valid result
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.CheckService"
        ) as mock_check_service:
            mock_service = mock_check_service.return_value
            mock_service.verify_branch.return_value = CheckResult(
                is_valid=True,
                issues=[],
                branch="task/issue-43",
            )
            result = coordinator._health_check_before_dispatch(issue)

        # Assert
        assert result is True, "Health check should pass for healthy active flow"

    def test_health_check_closes_issue_with_merged_pr(self) -> None:
        """Health check should return False if flow is done (PR merged)."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10
        config.repo = "owner/repo"
        config.supervisor_handoff = MagicMock()
        config.supervisor_handoff.issue_label = "supervisor"
        capacity = MagicMock()
        github = MagicMock()
        store = MagicMock()
        store.db_path = ":memory:"
        flow_manager = MagicMock()

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
        )

        issue = IssueInfo(
            number=44,
            title="Issue with merged PR",
            state=IssueState.IN_PROGRESS,
            labels=["state/in-progress"],
            github_state="OPEN",
        )

        # Mock _flow_context to return a branch
        coordinator._flow_context = MagicMock(return_value=("task/issue-44", None))

        # Mock flow state as done (CheckService marked it done for merged PR)
        store.get_flow_state.return_value = {
            "branch": "task/issue-44",
            "flow_status": "done",
        }

        # Mock CheckService to return valid (CheckService handles PR check
        # internally and marks flow as done, then returns valid)
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.CheckService"
        ) as mock_check_service:
            mock_service = mock_check_service.return_value
            mock_service.verify_branch.return_value = CheckResult(
                is_valid=True,
                issues=[],
                branch="task/issue-44",
            )
            result = coordinator._health_check_before_dispatch(issue)

        # Assert - flow is done, should skip dispatch
        assert result is False, "Health check should fail for done flow"

    def test_health_check_passes_for_open_pr(self) -> None:
        """Health check should pass for issue with open PR (still active)."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10
        config.repo = "owner/repo"
        config.supervisor_handoff = MagicMock()
        config.supervisor_handoff.issue_label = "supervisor"
        capacity = MagicMock()
        github = MagicMock()
        store = MagicMock()
        store.db_path = ":memory:"
        flow_manager = MagicMock()

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
        )

        issue = IssueInfo(
            number=45,
            title="Issue with open PR",
            state=IssueState.REVIEW,
            labels=["state/review"],
            github_state="OPEN",
        )

        # Mock _flow_context to return a branch
        coordinator._flow_context = MagicMock(return_value=("task/issue-45", None))

        # Mock flow state as active
        store.get_flow_state.return_value = {
            "branch": "task/issue-45",
            "flow_status": "active",
        }

        # Mock CheckService to return valid (open PR is not a failure)
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.CheckService"
        ) as mock_check_service:
            mock_service = mock_check_service.return_value
            mock_service.verify_branch.return_value = CheckResult(
                is_valid=True,
                issues=[],
                branch="task/issue-45",
            )
            result = coordinator._health_check_before_dispatch(issue)

        # Assert
        assert result is True, "Health check should pass for active flow with open PR"

    def test_health_check_handles_network_error(self) -> None:
        """Health check should fail open on network errors."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10
        config.repo = "owner/repo"
        config.supervisor_handoff = MagicMock()
        config.supervisor_handoff.issue_label = "supervisor"
        capacity = MagicMock()
        github = MagicMock()
        store = MagicMock()
        store.db_path = ":memory:"
        flow_manager = MagicMock()

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
        )

        issue = IssueInfo(
            number=46,
            title="Network error test",
            state=IssueState.READY,
            labels=["state/ready"],
            github_state="OPEN",
        )

        # Mock _flow_context to return a branch
        coordinator._flow_context = MagicMock(return_value=("task/issue-46", None))

        # Mock flow state as active
        store.get_flow_state.return_value = {
            "branch": "task/issue-46",
            "flow_status": "active",
        }

        # Mock CheckService to return invalid with transient error
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.CheckService"
        ) as mock_check_service:
            mock_service = mock_check_service.return_value
            mock_service.verify_branch.return_value = CheckResult(
                is_valid=False,
                issues=["Cannot verify task issue #46: network/auth error"],
                branch="task/issue-46",
            )
            result = coordinator._health_check_before_dispatch(issue)

        # Assert - should fail open on transient errors
        assert result is True, "Health check should fail open on network errors"
