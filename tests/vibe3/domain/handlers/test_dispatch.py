"""Tests for async dispatch intent handlers.

Verifies that dispatch handlers delegate to role request builders
and ExecutionCoordinator without hand-crafting CLI commands.
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events import (
    ExecutorDispatched,
    PlannerDispatched,
    ReviewerDispatched,
)
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest


def _make_mock_request(
    role: str,
    issue_number: int,
    **overrides: object,
) -> ExecutionRequest:
    """Create a minimal ExecutionRequest for testing."""
    defaults = {
        "role": role,
        "target_branch": f"task/issue-{issue_number}",
        "target_id": issue_number,
        "execution_name": f"vibe3-{role}-issue-{issue_number}",
        "repo_path": "/tmp/repo",
    }
    defaults.update(overrides)
    return ExecutionRequest(**defaults)  # type: ignore[arg-type]


class TestPlannerDispatchHandler:
    """Planner dispatch should delegate to build_plan_request + coordinator."""

    @patch("vibe3.domain.handlers.dispatch.build_plan_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.SQLiteClient")
    @patch("vibe3.domain.handlers.dispatch.GitHubClient")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_planner_dispatch_delegates_to_role_builder(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_planner_dispatched

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.from_settings.return_value = config

        # Mock GitHub issue loading
        mock_github_cls.return_value.view_issue.return_value = {
            "title": "Test issue",
            "labels": [],
        }

        # Mock request builder
        expected_request = _make_mock_request("planner", 42)
        mock_build_request.return_value = expected_request

        # Mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-planner-issue-42",
            log_path="/tmp/test.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_planner_dispatched(
            PlannerDispatched(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
            )
        )

        # Verify request builder was called with config, issue, and branch
        mock_build_request.assert_called_once()
        call_kwargs = mock_build_request.call_args
        assert call_kwargs[0][0] is config  # first positional = config
        assert call_kwargs[0][1].number == 42  # second positional = issue
        assert call_kwargs[1].get("branch") == "task/issue-42"

        # Verify coordinator dispatched the request
        mock_coordinator.dispatch_execution.assert_called_once()
        request = mock_coordinator.dispatch_execution.call_args[0][0]
        assert request.role == "planner"
        assert request.target_id == 42


class TestExecutorDispatchHandler:
    """Executor dispatch should delegate to build_run_request + coordinator."""

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.SQLiteClient")
    @patch("vibe3.domain.handlers.dispatch.GitHubClient")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_executor_dispatch_passes_plan_ref(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_executor_dispatched

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.from_settings.return_value = config

        mock_github_cls.return_value.view_issue.return_value = {
            "title": "Test issue",
            "labels": [],
        }

        expected_request = _make_mock_request("executor", 42)
        mock_build_request.return_value = expected_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-executor-issue-42",
            log_path="/tmp/test.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_executor_dispatched(
            ExecutorDispatched(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="in-progress",
                plan_ref="plan.md",
            )
        )

        # Verify request builder was called with plan_ref
        mock_build_request.assert_called_once()
        call_kwargs = mock_build_request.call_args
        assert call_kwargs[1].get("branch") == "task/issue-42"
        assert call_kwargs[1].get("plan_ref") == "plan.md"

        mock_coordinator.dispatch_execution.assert_called_once()


class TestReviewerDispatchHandler:
    """Reviewer dispatch should delegate to build_review_request + coordinator."""

    @patch("vibe3.domain.handlers.dispatch.build_review_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.SQLiteClient")
    @patch("vibe3.domain.handlers.dispatch.GitHubClient")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_reviewer_dispatch_passes_report_ref(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_reviewer_dispatched

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.from_settings.return_value = config

        mock_github_cls.return_value.view_issue.return_value = {
            "title": "Test issue",
            "labels": [],
        }

        expected_request = _make_mock_request("reviewer", 42)
        mock_build_request.return_value = expected_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-reviewer-issue-42",
            log_path="/tmp/test.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_reviewer_dispatched(
            ReviewerDispatched(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="review",
                report_ref="report.md",
            )
        )

        # Verify request builder was called with report_ref
        mock_build_request.assert_called_once()
        call_kwargs = mock_build_request.call_args
        assert call_kwargs[1].get("branch") == "task/issue-42"
        assert call_kwargs[1].get("report_ref") == "report.md"

        mock_coordinator.dispatch_execution.assert_called_once()


class TestDispatchNotLaunched:
    """When coordinator does not launch, handler should log warning without error."""

    @patch("vibe3.domain.handlers.dispatch.build_plan_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.SQLiteClient")
    @patch("vibe3.domain.handlers.dispatch.GitHubClient")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_dispatch_not_launched_logs_warning(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_planner_dispatched

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.from_settings.return_value = config

        mock_github_cls.return_value.view_issue.return_value = {
            "title": "Test issue",
            "labels": [],
        }

        mock_build_request.return_value = _make_mock_request("planner", 42)

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False,
            reason="capacity exceeded",
            reason_code="capacity",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        # Should not raise
        handle_planner_dispatched(
            PlannerDispatched(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()
