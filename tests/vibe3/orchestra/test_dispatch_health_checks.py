"""Tests for pre-dispatch health checks."""

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueInfo, IssueState


class TestPreDispatchHealthChecks:
    """Test health checks before dispatching issues."""

    def test_health_check_detects_closed_issue(self) -> None:
        """Health check should return False for closed issues."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10  # Must be int for ThreadPoolExecutor
        config.repo = "owner/repo"  # Add repo to config
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

        # Mock issue with GitHub state CLOSED
        issue = IssueInfo(
            number=42,
            title="Test issue",
            state=IssueState.BLOCKED,
            labels=["state/blocked"],
            github_state="CLOSED",  # NEW FIELD
        )

        # Mock GitHub client to return closed issue
        github.view_issue.return_value = {
            "number": 42,
            "state": "CLOSED",
            "title": "Test issue",
        }

        # Execute
        result = coordinator._health_check_before_dispatch(issue)

        # Assert
        assert result is False, "Health check should return False for closed issue"
        github.view_issue.assert_called_once_with(42, repo="owner/repo")

    def test_health_check_passes_for_open_issue(self) -> None:
        """Health check should return True for open issues without merged PR."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10  # Must be int for ThreadPoolExecutor
        config.repo = "owner/repo"  # Add repo to config
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

        # Mock no PR exists
        flow_manager.get_flow_for_issue.return_value = None

        # Execute
        result = coordinator._health_check_before_dispatch(issue)

        # Assert
        assert result is True, "Health check should pass for open issue without PR"

    def test_health_check_closes_issue_with_merged_pr(self) -> None:
        """Health check should close issue and return False if PR is merged."""
        from vibe3.models.pr import PRResponse, PRState
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10  # Must be int for ThreadPoolExecutor
        config.repo = "owner/repo"  # Add repo to config
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

        # Mock flow with PR number
        flow_manager.get_flow_for_issue.return_value = {
            "issue_number": 44,
            "pr_number": 123,
        }

        # Mock merged PR
        github.get_pr.return_value = PRResponse(
            number=123,
            title="Test PR",
            body="",
            state=PRState.MERGED,
            head_branch="task/issue-44",
            base_branch="main",
            url="https://github.com/test/test/pull/123",
            draft=False,
            is_ready=True,
            ci_passed=True,
        )

        # Execute
        result = coordinator._health_check_before_dispatch(issue)

        # Assert
        assert result is False, "Health check should fail for issue with merged PR"
        github.close_issue_if_open.assert_called_once_with(
            44,
            closing_comment="PR #123 已合并，系统自动关闭此 issue。",
            repo="owner/repo",
        )

    def test_health_check_passes_for_open_pr(self) -> None:
        """Health check should pass for issue with open PR."""
        from vibe3.models.pr import PRResponse, PRState
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup
        config = MagicMock()
        config.max_concurrent_flows = 10  # Must be int for ThreadPoolExecutor
        config.repo = "owner/repo"  # Add repo to config
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

        # Mock flow with PR number
        flow_manager.get_flow_for_issue.return_value = {
            "issue_number": 45,
            "pr_number": 124,
        }

        # Mock open PR
        github.get_pr.return_value = PRResponse(
            number=124,
            title="Test PR",
            body="",
            state=PRState.OPEN,
            head_branch="task/issue-45",
            base_branch="main",
            url="https://github.com/test/test/pull/124",
            draft=False,
            is_ready=True,
            ci_passed=False,
        )

        # Execute
        result = coordinator._health_check_before_dispatch(issue)

        # Assert
        assert result is True, "Health check should pass for issue with open PR"
        github.close_issue.assert_not_called()
