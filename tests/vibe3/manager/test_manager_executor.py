"""Tests for ManagerExecutor with SessionRegistryService capacity integration."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig
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
    executor._last_error_category = None
    executor._circuit_breaker = None
    executor._registry = registry

    mock_backend = MagicMock()
    executor._backend = mock_backend

    executor._flow_manager = MagicMock()
    executor.result_handler = MagicMock()
    executor.worktree_manager = MagicMock()
    executor.command_builder = MagicMock()

    # status_service fallback: should NOT be called when registry is present
    executor.status_service = MagicMock()
    executor.status_service.get_active_manager_session_count.return_value = 0

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
        # registry was consulted, not status_service
        registry.count_live_worker_sessions.assert_called()
        executor.status_service.get_active_manager_session_count.assert_not_called()

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

    def test_manager_dispatch_fallback_to_status_service_when_no_registry(
        self,
    ) -> None:
        """When no registry is provided, capacity check falls back to status_service."""
        config = OrchestraConfig(max_concurrent_flows=2)
        executor = ManagerExecutor.__new__(ManagerExecutor)
        executor.config = config
        executor.dry_run = False
        executor._queued_issues = set()
        executor._last_error_category = None
        executor._circuit_breaker = None
        executor._registry = None  # no registry

        mock_backend = MagicMock()
        executor._backend = mock_backend
        executor._flow_manager = MagicMock()
        executor.result_handler = MagicMock()
        executor.worktree_manager = MagicMock()
        executor.command_builder = MagicMock()

        executor.status_service = MagicMock()
        executor.status_service.get_active_manager_session_count.return_value = 2

        issue = make_issue(55)
        result = executor.dispatch_manager(issue)

        assert result is False
        executor.status_service.get_active_manager_session_count.assert_called()
        mock_backend.start_async_command.assert_not_called()
