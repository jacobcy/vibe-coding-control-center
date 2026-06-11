"""Tests for pre-dispatch health checks.

After unification, _check_dispatch_health delegates to
CheckService.verify_branch(). These tests verify the coordinator's
interpretation of CheckService results (fail-open, skip dispatch,
terminal state detection) rather than re-testing CheckService internals.
"""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.check.service import CheckResult

if TYPE_CHECKING:
    pass


def _make_mock_coordinator_dependencies():
    """Create mock dependencies for GlobalDispatchCoordinator construction."""
    flow_blocker = MagicMock()
    queue_persistence = MagicMock()
    queue_persistence.frozen_queue = None
    issue_loader = MagicMock(return_value=None)
    flow_context_resolver = MagicMock(return_value=("task/issue-42", None))
    queue_selector = MagicMock(return_value=[])
    check_service = MagicMock()
    return {
        "flow_blocker": flow_blocker,
        "queue_persistence": queue_persistence,
        "issue_loader": issue_loader,
        "flow_context_resolver": flow_context_resolver,
        "queue_selector": queue_selector,
        "check_service": check_service,
    }


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

        # Create mock dependencies
        mock_deps = _make_mock_coordinator_dependencies()
        mock_flow_blocker = mock_deps["flow_blocker"]

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            **mock_deps,
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
        mock_check_service = MagicMock()
        mock_check_service.verify_branch.return_value = CheckResult(
            is_valid=False,
            issues=["Branch 'task/issue-42' no longer exists locally"],
            branch="task/issue-42",
        )
        coordinator._check_service = mock_check_service

        result = coordinator._check_dispatch_health(issue)

        # Assert - genuine consistency failure should skip dispatch
        assert (
            result is False
        ), "Health check should return False for consistency failures"

        # Assert - block_flow should be called with correct parameters
        mock_flow_blocker.block_flow.assert_called_once()
        call_args = mock_flow_blocker.block_flow.call_args
        assert call_args[1]["branch"] == "task/issue-42"
        assert "Health check failed" in call_args[1]["reason"]
        assert call_args[1]["actor"] == "orchestra:dispatcher"

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

        # Create mock dependencies
        mock_deps = _make_mock_coordinator_dependencies()

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            **mock_deps,
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
        mock_check_service = MagicMock()
        mock_check_service.verify_branch.return_value = CheckResult(
            is_valid=True,
            issues=[],
            branch="task/issue-43",
        )
        coordinator._check_service = mock_check_service
        result = coordinator._check_dispatch_health(issue)

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
            **_make_mock_coordinator_dependencies(),
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
        mock_check_service = MagicMock()
        mock_check_service.verify_branch.return_value = CheckResult(
            is_valid=True,
            issues=[],
            branch="task/issue-44",
        )
        coordinator._check_service = mock_check_service
        result = coordinator._check_dispatch_health(issue)

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
            **_make_mock_coordinator_dependencies(),
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
        mock_check_service = MagicMock()
        mock_check_service.verify_branch.return_value = CheckResult(
            is_valid=True,
            issues=[],
            branch="task/issue-45",
        )
        coordinator._check_service = mock_check_service
        result = coordinator._check_dispatch_health(issue)

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
            **_make_mock_coordinator_dependencies(),
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
        mock_check_service = MagicMock()
        mock_check_service.verify_branch.return_value = CheckResult(
            is_valid=False,
            issues=["Cannot verify task issue #46: network/auth error"],
            branch="task/issue-46",
        )
        coordinator._check_service = mock_check_service
        result = coordinator._check_dispatch_health(issue)

        # Assert - should fail open on transient errors
        assert result is True, "Health check should fail open on network errors"

    def test_health_check_blocks_on_genuine_failure(self) -> None:
        """Health check genuine failure should call FlowService.block_flow."""
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
        git_client = MagicMock()
        flow_manager.git = git_client

        # Create mock dependencies
        mock_deps = _make_mock_coordinator_dependencies()
        mock_flow_blocker = mock_deps["flow_blocker"]

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            **mock_deps,
        )

        issue = IssueInfo(
            number=993,
            title="Missing worktree issue",
            state=IssueState.IN_PROGRESS,
            labels=["state/in-progress"],
            github_state="OPEN",
        )

        # Mock _flow_context to return a branch
        coordinator._flow_context = MagicMock(return_value=("task/issue-993", None))

        # Mock flow state as active
        store.get_flow_state.return_value = {
            "branch": "task/issue-993",
            "flow_status": "active",
        }

        # Mock CheckService to return invalid with genuine error (no worktree)
        mock_check_service = MagicMock()
        mock_check_service.verify_branch.return_value = CheckResult(
            is_valid=False,
            issues=[
                "plan_ref cannot be verified: "
                "no worktree for branch 'task/issue-993'"
            ],
            branch="task/issue-993",
        )
        coordinator._check_service = mock_check_service

        result = coordinator._check_dispatch_health(issue)

        # Assert - block_flow should be called with correct parameters
        mock_flow_blocker.block_flow.assert_called_once()
        call_args = mock_flow_blocker.block_flow.call_args
        assert call_args[1]["branch"] == "task/issue-993"
        assert "Health check failed" in call_args[1]["reason"]
        assert call_args[1]["actor"] == "orchestra:dispatcher"

        # Assert - should return False (skip dispatch)
        assert result is False, "Health check should return False for genuine failure"

    def test_health_check_transient_error_does_not_block(self) -> None:
        """Transient errors should fail open without calling block_flow."""
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

        # Create mock dependencies
        mock_deps = _make_mock_coordinator_dependencies()
        mock_flow_blocker = mock_deps["flow_blocker"]

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            **mock_deps,
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
        mock_check_service = MagicMock()
        mock_check_service.verify_branch.return_value = CheckResult(
            is_valid=False,
            issues=["Cannot verify task issue #46: network/auth error"],
            branch="task/issue-46",
        )
        coordinator._check_service = mock_check_service

        result = coordinator._check_dispatch_health(issue)

        # Assert - block_flow should NOT be called for transient errors
        mock_flow_blocker.block_flow.assert_not_called()

        # Assert - should fail open
        assert result is True, "Health check should fail open on transient errors"

    def test_health_check_skips_block_for_terminal_states(self) -> None:
        """When flow is in terminal state (aborted/done/stale/review),
        health check should skip dispatch without calling block_flow."""
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

        # Create mock dependencies
        mock_deps = _make_mock_coordinator_dependencies()
        mock_flow_blocker = mock_deps["flow_blocker"]

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            **mock_deps,
        )

        issue = IssueInfo(
            number=1629,
            title="Aborted issue",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            github_state="CLOSED",
        )

        # Mock _flow_context to return a branch
        coordinator._flow_context = MagicMock(return_value=("task/issue-1629", None))

        # Mock flow state as aborted (terminal)
        store.get_flow_state.return_value = {
            "branch": "task/issue-1629",
            "flow_status": "aborted",
        }

        # Mock CheckService to return invalid (would normally block)
        mock_check_service = MagicMock()
        mock_check_service.verify_branch.return_value = CheckResult(
            is_valid=False,
            issues=["Task issue #1629 is CLOSED (no open PR found)"],
            branch="task/issue-1629",
        )
        coordinator._check_service = mock_check_service

        result = coordinator._check_dispatch_health(issue)

        # Assert - should skip dispatch for terminal state
        assert result is False, "Health check should return False for terminal states"

        # Assert - block_flow should NOT be called for terminal states
        mock_flow_blocker.block_flow.assert_not_called()
