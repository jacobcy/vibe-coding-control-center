"""Tests for ManagerExecutor with SessionRegistryService capacity integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.session_registry import SessionRegistryService


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.READY,
        labels=["state/ready"],
    )


def _build_executor_with_registry(
    registry: SessionRegistryService,
    max_concurrent_flows: int = 3,
) -> tuple[ManagerExecutor, MagicMock]:
    """Build a ManagerExecutor with a mocked registry and backend.

    Returns (executor, mock_backend).
    """
    config = OrchestraConfig(
        dry_run=False,
        max_concurrent_flows=max_concurrent_flows,
    )
    executor = ManagerExecutor.__new__(ManagerExecutor)
    executor.config = config
    executor.dry_run = False
    executor._queued_issues = set()
    executor._active_dispatch_locks = set()
    executor._last_error_category = None
    executor._circuit_breaker = None
    executor._registry = registry
    executor.repo_path = Path("/tmp/repo")

    mock_backend = MagicMock()
    executor._backend = mock_backend

    executor._flow_manager = MagicMock()
    executor.result_handler = MagicMock()
    executor.worktree_manager = MagicMock()
    executor.worktree_manager.align_auto_scene_to_base = MagicMock(return_value=True)
    executor.command_builder = MagicMock()

    return executor, mock_backend


class TestManagerExecutorRegistryCapacity:
    """Capacity checks via SessionRegistryService."""

    def test_manager_dispatch_uses_live_worker_capacity_not_active_flows(
        self,
    ) -> None:
        """When registry has max live worker sessions, dispatch is refused."""
        registry = MagicMock(spec=SessionRegistryService)
        registry.count_live_worker_sessions.return_value = 3  # == max_concurrent_flows

        executor, mock_backend = _build_executor_with_registry(
            registry, max_concurrent_flows=3
        )
        issue = make_issue(42)

        result = executor.dispatch_manager(issue)

        assert result is False
        mock_backend.start_async_command.assert_not_called()
        registry.count_live_worker_sessions.assert_called()

    def test_manager_dispatch_proceeds_when_registry_has_capacity(
        self,
    ) -> None:
        """When registry has free capacity, dispatch proceeds to flow creation."""
        registry = MagicMock(spec=SessionRegistryService)
        registry.count_live_worker_sessions.return_value = 1  # < max=3

        executor, mock_backend = _build_executor_with_registry(
            registry, max_concurrent_flows=3
        )
        issue = make_issue(42)

        # Flow creation will raise (we only care about capacity gate passing)
        executor._flow_manager.create_flow_for_issue.side_effect = RuntimeError(
            "flow error"
        )

        result = executor.dispatch_manager(issue)

        # capacity gate passed; flow creation failed -> False, but not from capacity
        assert result is False
        registry.count_live_worker_sessions.assert_called()
        # issue NOT queued (capacity was available, failed for a different reason)
        assert 42 not in executor._queued_issues

    def test_manager_dispatch_queues_issue_when_registry_full(self) -> None:
        """Refused dispatch due to registry capacity adds issue to queued_issues."""
        registry = MagicMock(spec=SessionRegistryService)
        registry.count_live_worker_sessions.return_value = 2  # == max=2

        executor, mock_backend = _build_executor_with_registry(
            registry, max_concurrent_flows=2
        )
        issue = make_issue(99)

        result = executor.dispatch_manager(issue)

        assert result is False
        assert 99 in executor._queued_issues


class TestManagerExecutorSessionExceptionHandling:
    """Session registry exception handling during dispatch."""

    def test_dispatch_marks_session_failed_on_tmux_failure(self) -> None:
        """When tmux launch fails, reserved session is marked as failed."""
        registry = MagicMock(spec=SessionRegistryService)
        registry.count_live_worker_sessions.return_value = 0
        registry.reserve.return_value = 123  # session_id

        executor, mock_backend = _build_executor_with_registry(registry)
        issue = make_issue(42)

        # Mock flow and worktree setup
        executor._flow_manager.create_flow_for_issue.return_value = {
            "branch": "task/issue-42"
        }
        executor._resolve_manager_cwd = MagicMock(return_value=("/tmp/worktree", False))

        # Simulate tmux launch failure
        mock_backend.start_async_command.side_effect = RuntimeError("tmux failed")

        result = executor.dispatch_manager(issue)

        assert result is False
        # Verify session was marked failed after tmux launch failure
        registry.mark_failed.assert_called_once_with(123)

    def test_dispatch_succeeds_even_when_mark_started_fails(self) -> None:
        """When mark_started fails (db error), dispatch still succeeds."""
        registry = MagicMock(spec=SessionRegistryService)
        registry.count_live_worker_sessions.return_value = 0
        registry.reserve.return_value = 456  # session_id
        # Simulate database error in mark_started
        registry.mark_started.side_effect = RuntimeError("db connection lost")

        executor, mock_backend = _build_executor_with_registry(registry)
        issue = make_issue(42)

        # Mock successful tmux launch
        from vibe3.agents.backends.codeagent import AsyncExecutionHandle

        mock_handle = MagicMock(spec=AsyncExecutionHandle)
        mock_handle.tmux_session = "vibe3-manager-issue-42"
        mock_handle.log_path = Path("/tmp/log.txt")
        mock_backend.start_async_command.return_value = mock_handle

        # Mock flow and worktree setup
        executor._flow_manager.create_flow_for_issue.return_value = {
            "branch": "task/issue-42"
        }
        executor._flow_manager.store = MagicMock()
        executor._resolve_manager_cwd = MagicMock(return_value=("/tmp/worktree", False))

        result = executor.dispatch_manager(issue)

        # Dispatch succeeds despite mark_started failure
        assert result is True
        # mark_started was called but failed
        registry.mark_started.assert_called_once()
        # Session cleanup will happen via reconcile later
