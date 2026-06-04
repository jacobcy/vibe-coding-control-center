"""Shared fixtures and helpers for GlobalDispatchCoordinator tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    GlobalDispatchCoordinator,
)
from vibe3.orchestra.queue_operations import select_ready_issues_from_collected_issues
from vibe3.orchestra.queue_persistence_service import QueuePersistenceService


@pytest.fixture
def make_issue() -> callable:
    """Factory for creating IssueInfo objects.

    NOTE: This fixture returns IssueInfo objects (not MagicMock) to avoid
    type comparison errors in sorting operations like sort_ready_issues().
    MagicMock objects don't support <= comparisons with int values.
    """

    def _make_issue(number: int, priority: int = 5) -> IssueInfo:
        return IssueInfo(
            number=number,
            title=f"Issue {number}",
            state=IssueState.READY,
            labels=[f"priority/{priority}", IssueState.READY.to_label()],
            milestone=None,
            assignees=["manager-bot"],
        )

    return _make_issue


@pytest.fixture
def make_issue_info() -> callable:
    """Factory for creating IssueInfo objects."""

    def _make_issue_info(
        number: int,
        state: IssueState,
        *,
        assignees: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> IssueInfo:
        return IssueInfo(
            number=number,
            title=f"Issue {number}",
            state=state,
            labels=labels if labels is not None else [state.to_label()],
            assignees=assignees if assignees is not None else ["manager-bot"],
        )

    return _make_issue_info


@pytest.fixture
def make_coordinator() -> callable:
    """Factory for creating GlobalDispatchCoordinator with mocked dependencies."""

    def _make_coordinator(
        role: str = "manager",
        config: OrchestraConfig | None = None,
        capacity: MagicMock | None = None,
        with_branches: bool = False,
        mock_health_check: bool = False,
    ) -> GlobalDispatchCoordinator:
        if config is None:
            config = OrchestraConfig(repo="owner/repo")
            config.manager_usernames = ["manager-bot"]
            config.supervisor_handoff.issue_label = "supervisor"

        if capacity is None:
            capacity = MagicMock()
            capacity.config.max_concurrent_flows = 10
            capacity.get_capacity_status = MagicMock(
                return_value={
                    "remaining": 10,
                    "active_count": 0,
                    "max_capacity": 10,
                }
            )
            capacity._backend = None

        github = MagicMock()

        store = MagicMock()
        store.db_path = ":memory:"
        store.get_flow_state = MagicMock(return_value=None)
        store.get_flows_by_issue = MagicMock(return_value=[])

        flow_manager = MagicMock()
        flow_manager.get_flow_for_issue = MagicMock(return_value=None)
        flow_manager.git.branch_exists = MagicMock(return_value=True)

        health_check_service = MagicMock()

        def mock_issue_loader(issue_number: int):
            return None

        def mock_flow_context_resolver(issue_number: int):
            return (f"task/issue-{issue_number}", None)

        queue_persistence = QueuePersistenceService(
            store=store,
            config=config,
            github=github,
            registry=None,
            supervisor_label=config.supervisor_handoff.issue_label,
            load_issue=mock_issue_loader,
        )

        coordinator = GlobalDispatchCoordinator(
            config=config,
            capacity=capacity,
            github=github,
            store=store,
            flow_manager=flow_manager,
            registry=None,
            health_check_service=health_check_service,
            queue_persistence=queue_persistence,
            issue_loader=mock_issue_loader,
            flow_context_resolver=mock_flow_context_resolver,
            queue_selector=select_ready_issues_from_collected_issues,
        )

        # Mock health check to bypass CheckService for queue operation tests
        if mock_health_check:
            coordinator._health_check_service.check_issue_health = MagicMock(
                return_value=True
            )

        if with_branches and role != "manager":

            def mock_flow_context(issue_number: int) -> tuple[str, dict | None]:
                return (f"task/issue-{issue_number}", None)

            coordinator._flow_context = mock_flow_context

        return coordinator

    return _make_coordinator


@pytest.fixture
def make_capacity() -> callable:
    """Factory for creating mock capacity service."""

    def _make_capacity(remaining: int = 1) -> MagicMock:
        capacity = MagicMock()
        capacity.config.max_concurrent_flows = max(remaining, 1)
        capacity.get_capacity_status = MagicMock(
            return_value={
                "remaining": remaining,
                "active_count": 0,
                "max_capacity": max(remaining, 1),
            }
        )
        capacity._run_command = MagicMock(
            side_effect=Exception("tmux not available in tests")
        )
        capacity._backend = None
        return capacity

    return _make_capacity


@pytest.fixture
def install_issue_loader() -> callable:
    """Factory for installing mock issue loader."""

    def _install_issue_loader(
        coordinator: GlobalDispatchCoordinator,
        states: dict[int, IssueState | None],
    ) -> None:
        def loader(issue_number: int):
            if states.get(issue_number) is None:
                return None
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=states[issue_number],
                labels=[states[issue_number].to_label()],
                assignees=["manager-bot"],
            )

        coordinator._load_issue = loader
        if hasattr(coordinator._queue_persistence, "load_issue"):
            coordinator._queue_persistence.load_issue = loader

    return _install_issue_loader
