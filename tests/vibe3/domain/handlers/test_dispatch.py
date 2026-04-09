"""Tests for async dispatch intent handlers."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events import (
    ExecutorDispatched,
    PlannerDispatched,
    ReviewerDispatched,
)
from vibe3.execution.contracts import ExecutionLaunchResult


class TestPlannerDispatchHandler:
    """Planner dispatch should invoke ExecutionCoordinator."""

    @patch("vibe3.domain.handlers.dispatch.ManagerExecutor")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_planner_async_launch(
        self,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_planner_dispatched

        mock_config_cls.from_settings.return_value = MagicMock(dry_run=False)
        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True, tmux_session="vibe3-plan-42", log_path="/tmp/test.async.log"
        )
        mock_coordinator_cls.return_value = mock_coordinator

        mock_manager = MagicMock()
        mock_manager.flow_manager.get_flow_for_issue.return_value = None
        mock_manager._resolve_manager_cwd.return_value = ("/tmp/wt", None)
        mock_manager_cls.return_value = mock_manager

        handle_planner_dispatched(
            PlannerDispatched(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()
        request = mock_coordinator.dispatch_execution.call_args[0][0]
        assert request.role == "planner"
        assert request.target_branch == "task/issue-42"
        assert request.target_id == 42
        assert request.execution_name == "vibe3-planner-issue-42"
        assert "plan" in request.cmd
        assert request.cwd == "/tmp/wt"
        assert request.actor == "orchestra:planner"
        assert request.mode == "async"
        assert request.refs["issue_number"] == "42"


class TestExecutorDispatchHandler:
    """Executor dispatch should invoke ExecutionCoordinator."""

    @patch("vibe3.domain.handlers.dispatch.ManagerExecutor")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_executor_async_launch(
        self,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_executor_dispatched

        mock_config_cls.from_settings.return_value = MagicMock(dry_run=False)
        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-executor-42",
            log_path="/tmp/test.async.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        mock_manager = MagicMock()
        mock_manager.flow_manager.get_flow_for_issue.return_value = None
        mock_manager._resolve_manager_cwd.return_value = ("/tmp/wt", None)
        mock_manager_cls.return_value = mock_manager

        handle_executor_dispatched(
            ExecutorDispatched(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="in-progress",
                plan_ref="plan.md",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()
        request = mock_coordinator.dispatch_execution.call_args[0][0]
        assert request.role == "executor"
        assert request.target_branch == "task/issue-42"
        assert request.target_id == 42
        assert request.execution_name == "vibe3-executor-issue-42"
        assert "run" in request.cmd
        assert request.cwd == "/tmp/wt"
        assert request.actor == "orchestra:executor"
        assert request.mode == "async"
        assert request.refs["issue_number"] == "42"
        assert request.refs["plan_ref"] == "plan.md"


class TestReviewerDispatchHandler:
    """Reviewer dispatch should invoke ExecutionCoordinator."""

    @patch("vibe3.domain.handlers.dispatch.ManagerExecutor")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_reviewer_async_launch(
        self,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_reviewer_dispatched

        mock_config_cls.from_settings.return_value = MagicMock(dry_run=False)
        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-reviewer-42",
            log_path="/tmp/test.async.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        mock_manager = MagicMock()
        mock_manager.flow_manager.get_flow_for_issue.return_value = None
        mock_manager._resolve_manager_cwd.return_value = ("/tmp/wt", None)
        mock_manager_cls.return_value = mock_manager

        handle_reviewer_dispatched(
            ReviewerDispatched(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="review",
                report_ref="report.md",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()
        request = mock_coordinator.dispatch_execution.call_args[0][0]
        assert request.role == "reviewer"
        assert request.target_branch == "task/issue-42"
        assert request.target_id == 42
        assert request.execution_name == "vibe3-reviewer-issue-42"
        assert "review" in request.cmd
        assert request.cwd == "/tmp/wt"
        assert request.actor == "orchestra:reviewer"
        assert request.mode == "async"
        assert request.refs["issue_number"] == "42"
        assert request.refs["report_ref"] == "report.md"
