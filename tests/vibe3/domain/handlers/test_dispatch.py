"""Tests for async dispatch intent handlers."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events import (
    ExecutorDispatchIntent,
    PlannerDispatchIntent,
    ReviewerDispatchIntent,
)
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest


def _make_mock_request(
    role: str,
    issue_number: int,
    **overrides: object,
) -> ExecutionRequest:
    """Create minimal ExecutionRequest for testing."""
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
    @patch("vibe3.roles.plan.build_plan_request")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_planner_dispatch_delegates_to_role_builder(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_planner_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = None
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        expected_request = _make_mock_request("planner", 42)
        mock_build_request.return_value = expected_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-planner-issue-42",
            log_path="/tmp/test.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_planner_dispatch_intent(
            PlannerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
            )
        )

        mock_build_request.assert_called_once()
        call_kwargs = mock_build_request.call_args
        assert call_kwargs[0][0] is config
        assert call_kwargs[0][1].number == 42
        assert call_kwargs[1].get("branch") == "task/issue-42"

        mock_coordinator.dispatch_execution.assert_called_once()
        request = mock_coordinator.dispatch_execution.call_args[0][0]
        assert request.role == "planner"
        assert request.target_id == 42

    @patch("vibe3.services.error_helpers.record_error")
    @patch("vibe3.roles.plan.build_plan_request")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_planner_dispatch_failure_records_event_tick_id(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        mock_record_error: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_planner_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = None
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_build_request.return_value = _make_mock_request("planner", 42)

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Worktree unavailable: permission denied",
            reason_code="worktree_unavailable",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_planner_dispatch_intent(
            PlannerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
                tick_id=17,
            )
        )

        mock_record_error.assert_called_once()
        assert mock_record_error.call_args.kwargs["tick_id"] == 17
        assert mock_record_error.call_args.kwargs["error_code"] == "E_DISPATCH_FAILURE"

    @patch("vibe3.services.error_helpers.record_error")
    @patch("vibe3.roles.plan.build_plan_request")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_planner_dispatch_launch_failed_no_duplicate_error(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        mock_record_error: MagicMock,
    ) -> None:
        """Verify launch_failed does NOT trigger duplicate error recording."""
        from vibe3.domain.handlers.dispatch import handle_planner_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = None
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_build_request.return_value = _make_mock_request("planner", 42)

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Failed to start session",
            reason_code="launch_failed",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_planner_dispatch_intent(
            PlannerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
                tick_id=17,
            )
        )

        # Should NOT call record_error for launch_failed
        mock_record_error.assert_not_called()

    @patch("vibe3.services.error_helpers.has_recent_specific_error")
    @patch("vibe3.services.error_helpers.record_error")
    @patch("vibe3.roles.plan.build_plan_request")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_launch_failed_skipped(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        mock_record_error: MagicMock,
        mock_has_recent_error: MagicMock,
    ) -> None:
        """Verify launch_failed does not trigger error recording when prior error.

        exists.
        """
        from vibe3.domain.handlers.dispatch import handle_planner_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = None
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_build_request.return_value = _make_mock_request("planner", 42)

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Failed to start session",
            reason_code="launch_failed",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        # Mock has_recent_specific_error to return True (prior error exists)
        mock_has_recent_error.return_value = True

        handle_planner_dispatch_intent(
            PlannerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
                tick_id=17,
            )
        )

        # Should NOT call record_error when prior error exists
        mock_record_error.assert_not_called()
        mock_has_recent_error.assert_called_once()


class TestExecutorDispatchHandler:

    @patch("vibe3.roles.run.build_run_request")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_executor_dispatch_reads_flow_state(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"plan_ref": "plan.md"}
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        expected_request = _make_mock_request("executor", 42)
        mock_build_request.return_value = expected_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-executor-issue-42",
            log_path="/tmp/test.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_executor_dispatch_intent(
            ExecutorDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="in-progress",
            )
        )

        mock_store.get_flow_state.assert_called_with("task/issue-42")

        mock_build_request.assert_called_once()
        call_kwargs = mock_build_request.call_args
        assert call_kwargs[1].get("branch") == "task/issue-42"
        assert call_kwargs[1].get("plan_ref") == "plan.md"
        assert call_kwargs[1].get("commit_mode") is False

        mock_coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.roles.run.build_run_request")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_executor_dispatch_publish_path_from_merge_ready(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        """commit_mode=True when trigger_state == 'merge-ready'."""
        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"plan_ref": "plan.md"}
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        expected_request = _make_mock_request("executor", 42)
        mock_build_request.return_value = expected_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-executor-issue-42",
            log_path="/tmp/test.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_executor_dispatch_intent(
            ExecutorDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="merge-ready",
            )
        )

        call_kwargs = mock_build_request.call_args
        assert call_kwargs[1].get("commit_mode") is True


class TestReviewerDispatchHandler:

    @patch("vibe3.roles.review.build_review_request")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_reviewer_dispatch_reads_flow_state(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_reviewer_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"report_ref": "report.md"}
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        expected_request = _make_mock_request("reviewer", 42)
        mock_build_request.return_value = expected_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True,
            tmux_session="vibe3-reviewer-issue-42",
            log_path="/tmp/test.log",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        handle_reviewer_dispatch_intent(
            ReviewerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="review",
            )
        )

        mock_store.get_flow_state.assert_called_with("task/issue-42")

        mock_build_request.assert_called_once()
        call_kwargs = mock_build_request.call_args
        assert call_kwargs[1].get("branch") == "task/issue-42"
        assert call_kwargs[1].get("report_ref") == "report.md"

        mock_coordinator.dispatch_execution.assert_called_once()
