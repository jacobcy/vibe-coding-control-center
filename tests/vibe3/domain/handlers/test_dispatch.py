"""Tests for async dispatch intent handlers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.domain.events import (
    ExecutorDispatched,
    PlannerDispatched,
    ReviewerDispatched,
)


def _make_handle(tmux_session: str = "vibe3-test-session") -> MagicMock:
    handle = MagicMock()
    handle.tmux_session = tmux_session
    handle.log_path = Path("/tmp/test.async.log")
    return handle


class TestPlannerDispatchHandler:
    """Planner dispatch should only mark started after async launch."""

    @patch("vibe3.domain.handlers.dispatch.ManagerExecutor")
    @patch("vibe3.domain.handlers.dispatch.CodeagentBackend")
    @patch("vibe3.domain.handlers.dispatch.ExecutionLifecycleService")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_planner_async_launch_does_not_record_completed(
        self,
        mock_config_cls: MagicMock,
        mock_lifecycle_cls: MagicMock,
        mock_backend_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_planner_dispatched

        mock_config_cls.from_settings.return_value = MagicMock(dry_run=False)
        mock_lifecycle = MagicMock()
        mock_lifecycle_cls.return_value = mock_lifecycle
        mock_backend = MagicMock()
        mock_backend.start_async_command.return_value = _make_handle("vibe3-plan-42")
        mock_backend_cls.return_value = mock_backend
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

        mock_lifecycle.record_started.assert_called_once_with(
            role="planner",
            target="task/issue-42",
            actor="orchestra:planner",
            refs={
                "issue_number": "42",
                "tmux_session": "vibe3-plan-42",
                "log_path": "/tmp/test.async.log",
            },
        )
        mock_lifecycle.record_completed.assert_not_called()


class TestExecutorDispatchHandler:
    """Executor dispatch should only mark started after async launch."""

    @patch("vibe3.domain.handlers.dispatch.ManagerExecutor")
    @patch("vibe3.domain.handlers.dispatch.CodeagentBackend")
    @patch("vibe3.domain.handlers.dispatch.ExecutionLifecycleService")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_executor_async_launch_does_not_record_completed(
        self,
        mock_config_cls: MagicMock,
        mock_lifecycle_cls: MagicMock,
        mock_backend_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_executor_dispatched

        mock_config_cls.from_settings.return_value = MagicMock(dry_run=False)
        mock_lifecycle = MagicMock()
        mock_lifecycle_cls.return_value = mock_lifecycle
        mock_backend = MagicMock()
        mock_backend.start_async_command.return_value = _make_handle(
            "vibe3-executor-42"
        )
        mock_backend_cls.return_value = mock_backend
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

        mock_lifecycle.record_started.assert_called_once_with(
            role="executor",
            target="task/issue-42",
            actor="orchestra:executor",
            refs={
                "issue_number": "42",
                "tmux_session": "vibe3-executor-42",
                "log_path": "/tmp/test.async.log",
                "plan_ref": "plan.md",
            },
        )
        mock_lifecycle.record_completed.assert_not_called()


class TestReviewerDispatchHandler:
    """Reviewer dispatch should only mark started after async launch."""

    @patch("vibe3.domain.handlers.dispatch.ManagerExecutor")
    @patch("vibe3.domain.handlers.dispatch.CodeagentBackend")
    @patch("vibe3.domain.handlers.dispatch.ExecutionLifecycleService")
    @patch("vibe3.domain.handlers.dispatch.OrchestraConfig")
    def test_reviewer_async_launch_does_not_record_completed(
        self,
        mock_config_cls: MagicMock,
        mock_lifecycle_cls: MagicMock,
        mock_backend_cls: MagicMock,
        mock_manager_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_reviewer_dispatched

        mock_config_cls.from_settings.return_value = MagicMock(dry_run=False)
        mock_lifecycle = MagicMock()
        mock_lifecycle_cls.return_value = mock_lifecycle
        mock_backend = MagicMock()
        mock_backend.start_async_command.return_value = _make_handle(
            "vibe3-reviewer-42"
        )
        mock_backend_cls.return_value = mock_backend
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

        mock_lifecycle.record_started.assert_called_once_with(
            role="reviewer",
            target="task/issue-42",
            actor="orchestra:reviewer",
            refs={
                "issue_number": "42",
                "tmux_session": "vibe3-reviewer-42",
                "log_path": "/tmp/test.async.log",
                "report_ref": "report.md",
            },
        )
        mock_lifecycle.record_completed.assert_not_called()
