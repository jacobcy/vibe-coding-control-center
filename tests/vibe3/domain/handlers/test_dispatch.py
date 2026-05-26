"""Tests for async dispatch intent handlers.

Verifies that dispatch handlers delegate to role request builders
and ExecutionCoordinator without hand-crafting CLI commands.
"""

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

        # Mock issue loading
        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        # Mock get_store context manager
        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = None
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

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

        handle_planner_dispatch_intent(
            PlannerDispatchIntent(
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

        # Mock flow_state with plan_ref (normal implementation path)
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

        # Event no longer carries plan_ref; handler reads from flow_state
        handle_executor_dispatch_intent(
            ExecutorDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="in-progress",
            )
        )

        # Verify handler read flow_state
        mock_store.get_flow_state.assert_called_with("task/issue-42")

        # Verify request builder was called with plan_ref from flow_state
        # and commit_mode=False (trigger_state is in-progress, not merge-ready)
        mock_build_request.assert_called_once()
        call_kwargs = mock_build_request.call_args
        assert call_kwargs[1].get("branch") == "task/issue-42"
        assert call_kwargs[1].get("plan_ref") == "plan.md"
        assert call_kwargs[1].get("commit_mode") is False

        mock_coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
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
        mock_store.get_flow_state.return_value = {
            "plan_ref": "plan.md",
        }
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

        # merge-ready trigger_state drives commit_mode
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
    """Reviewer dispatch should delegate to build_review_request + coordinator."""

    @patch("vibe3.domain.handlers.dispatch.build_review_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
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

        # Mock flow_state with report_ref
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

        # Event no longer carries report_ref; handler reads from flow_state
        handle_reviewer_dispatch_intent(
            ReviewerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="review",
            )
        )

        # Verify handler read flow_state
        mock_store.get_flow_state.assert_called_with("task/issue-42")

        # Verify request builder was called with report_ref from flow_state
        mock_build_request.assert_called_once()
        call_kwargs = mock_build_request.call_args
        assert call_kwargs[1].get("branch") == "task/issue-42"
        assert call_kwargs[1].get("report_ref") == "report.md"

        mock_coordinator.dispatch_execution.assert_called_once()


class TestDispatchNotLaunched:
    """When coordinator does not launch, handler should log warning without error."""

    @patch("vibe3.domain.handlers.dispatch.build_plan_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_dispatch_not_launched_logs_warning(
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

        # Mock get_store
        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = None
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_build_request.return_value = _make_mock_request("planner", 42)

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False,
            reason="capacity exceeded",
            reason_code="capacity",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        # Should not raise
        handle_planner_dispatch_intent(
            PlannerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()


class TestExecutorScopeValidation:
    """Executor dispatch should block when plan references .claude/.codex paths."""

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_blocks_on_claude_paths(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        tmp_path: object,
    ) -> None:
        """Plan with .claude/ files should block flow and not dispatch."""
        from pathlib import Path

        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        # Create temporary plan file with .claude/ path
        plan_file = Path(str(tmp_path)) / "plan.md"
        plan_file.write_text("""## Plan Summary
Test plan

## Steps
1. Modify agent
   - Files: .claude/agents/foo.md
   - Effort: S
   - Dependencies: none
""")

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"plan_ref": str(plan_file)}
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        with patch(
            "vibe3.domain.handlers.dispatch.FlowService"
        ) as mock_flow_service_cls:
            mock_flow_service = MagicMock()
            mock_flow_service_cls.return_value = mock_flow_service

            handle_executor_dispatch_intent(
                ExecutorDispatchIntent(
                    issue_number=42,
                    branch="task/issue-42",
                    trigger_state="in-progress",
                )
            )

            # Verify FlowService.block_flow was called
            mock_flow_service.block_flow.assert_called_once()
            call_args = mock_flow_service.block_flow.call_args
            assert call_args[0][0] == "task/issue-42"
            assert ".claude/agents/foo.md" in call_args[1]["reason"]
            assert call_args[1]["actor"] == "orchestra:scope-gate"

        # Verify dispatch was NOT attempted
        mock_build_request.assert_not_called()
        mock_coordinator.dispatch_execution.assert_not_called()

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_blocks_on_codex_paths(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        tmp_path: object,
    ) -> None:
        """Plan with .codex/ files should block flow and not dispatch."""
        from pathlib import Path

        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        plan_file = Path(str(tmp_path)) / "plan.md"
        plan_file.write_text("""## Plan Summary
Test plan

## Steps
1. Modify codex
   - Files: .codex/agents/bar.toml
   - Effort: S
   - Dependencies: none
""")

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"plan_ref": str(plan_file)}
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        with patch(
            "vibe3.domain.handlers.dispatch.FlowService"
        ) as mock_flow_service_cls:
            mock_flow_service = MagicMock()
            mock_flow_service_cls.return_value = mock_flow_service

            handle_executor_dispatch_intent(
                ExecutorDispatchIntent(
                    issue_number=42,
                    branch="task/issue-42",
                    trigger_state="in-progress",
                )
            )

            mock_flow_service.block_flow.assert_called_once()
            call_args = mock_flow_service.block_flow.call_args
            assert ".codex/agents/bar.toml" in call_args[1]["reason"]

        mock_build_request.assert_not_called()
        mock_coordinator.dispatch_execution.assert_not_called()

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_blocks_on_multiple_blocked_paths(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        tmp_path: object,
    ) -> None:
        """Plan with both .claude/ and .codex/ paths should list all in reason."""
        from pathlib import Path

        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        plan_file = Path(str(tmp_path)) / "plan.md"
        plan_file.write_text("""## Plan Summary
Test plan

## Steps
1. Modify agent
   - Files: .claude/agents/foo.md, .codex/agents/bar.toml
   - Effort: S
   - Dependencies: none
""")

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"plan_ref": str(plan_file)}
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        with patch(
            "vibe3.domain.handlers.dispatch.FlowService"
        ) as mock_flow_service_cls:
            mock_flow_service = MagicMock()
            mock_flow_service_cls.return_value = mock_flow_service

            handle_executor_dispatch_intent(
                ExecutorDispatchIntent(
                    issue_number=42,
                    branch="task/issue-42",
                    trigger_state="in-progress",
                )
            )

            mock_flow_service.block_flow.assert_called_once()
            call_args = mock_flow_service.block_flow.call_args
            reason = call_args[1]["reason"]
            assert ".claude/agents/foo.md" in reason
            assert ".codex/agents/bar.toml" in reason

        mock_build_request.assert_not_called()
        mock_coordinator.dispatch_execution.assert_not_called()

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_passes_on_normal_paths(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        tmp_path: object,
    ) -> None:
        """Plan with normal files should proceed with dispatch."""
        from pathlib import Path

        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        plan_file = Path(str(tmp_path)) / "plan.md"
        plan_file.write_text("""## Plan Summary
Test plan

## Steps
1. Modify code
   - Files: src/foo.py, tests/bar.py
   - Effort: S
   - Dependencies: none
""")

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"plan_ref": str(plan_file)}
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

        # Verify dispatch proceeded normally
        mock_build_request.assert_called_once()
        mock_coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_passes_when_plan_ref_none(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        """No plan_ref should proceed with dispatch (graceful degradation)."""
        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {}  # No plan_ref
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

        # Verify dispatch proceeded normally
        mock_build_request.assert_called_once()
        mock_coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_passes_when_plan_file_unreadable(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        """Nonexistent plan file should proceed with dispatch (graceful degradation)."""
        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {
            "plan_ref": "nonexistent.md"
        }  # File doesn't exist
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

        # Verify dispatch proceeded normally
        mock_build_request.assert_called_once()
        mock_coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_blocks_on_bracketed_file_list(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        tmp_path: object,
    ) -> None:
        """Plan with bracketed file list should still detect .claude/ path."""
        from pathlib import Path

        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        plan_file = Path(str(tmp_path)) / "plan.md"
        plan_file.write_text("""## Plan Summary
Test plan

## Steps
1. Modify agent
   - Files: [.claude/rules/custom.md, src/foo.py]
   - Effort: S
   - Dependencies: none
""")

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"plan_ref": str(plan_file)}
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        with patch(
            "vibe3.domain.handlers.dispatch.FlowService"
        ) as mock_flow_service_cls:
            mock_flow_service = MagicMock()
            mock_flow_service_cls.return_value = mock_flow_service

            handle_executor_dispatch_intent(
                ExecutorDispatchIntent(
                    issue_number=42,
                    branch="task/issue-42",
                    trigger_state="in-progress",
                )
            )

            # Should block on .claude/ path, but not src/foo.py
            mock_flow_service.block_flow.assert_called_once()
            call_args = mock_flow_service.block_flow.call_args
            reason = call_args[1]["reason"]
            assert ".claude/rules/custom.md" in reason
            assert "src/foo.py" not in reason

        mock_build_request.assert_not_called()
        mock_coordinator.dispatch_execution.assert_not_called()

    @patch("vibe3.domain.handlers.dispatch.build_run_request")
    @patch("vibe3.domain.handlers.dispatch.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_no_block_on_files_none(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
        tmp_path: object,
    ) -> None:
        """Plan with 'Files: none' should proceed with dispatch."""
        from pathlib import Path

        from vibe3.domain.handlers.dispatch import handle_executor_dispatch_intent

        plan_file = Path(str(tmp_path)) / "plan.md"
        plan_file.write_text("""## Plan Summary
Test plan

## Steps
1. Research only
   - Files: none
   - Effort: S
   - Dependencies: none
""")

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {"plan_ref": str(plan_file)}
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

        # Verify dispatch proceeded normally
        mock_build_request.assert_called_once()
        mock_coordinator.dispatch_execution.assert_called_once()
