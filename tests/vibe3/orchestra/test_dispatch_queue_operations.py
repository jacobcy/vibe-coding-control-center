"""Tests for GlobalDispatchCoordinator queue operations."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    GlobalDispatchCoordinator,
    QueueEntry,
)


def make_issue(number: int, priority: int = 5) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.labels = [f"priority/{priority}"]
    issue.milestone = None
    issue.assignees = ["manager-bot"]
    issue.priority = priority
    return issue


def make_issue_info(
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


def make_coordinator(
    role: str = "manager",
    ready_issues: list | None = None,
    config: OrchestraConfig | None = None,
    capacity: MagicMock | None = None,
    with_branches: bool = False,
) -> GlobalDispatchCoordinator:
    """Create a GlobalDispatchCoordinator with mocked dependencies."""
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

    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=capacity,
        github=github,
        store=store,
        flow_manager=flow_manager,
        registry=None,
    )

    if ready_issues:
        role_map = {
            "manager": IssueState.READY,
            "handoff-manager": IssueState.HANDOFF,
            "planner": IssueState.CLAIMED,
            "plan": IssueState.CLAIMED,
            "executor": IssueState.IN_PROGRESS,
            "run": IssueState.IN_PROGRESS,
            "reviewer": IssueState.REVIEW,
            "review": IssueState.REVIEW,
        }
        target_state = role_map.get(role, IssueState.READY)

        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == target_state:
                issues_info = [
                    IssueInfo(
                        number=issue.number,
                        title=f"Issue {issue.number}",
                        state=target_state,
                        labels=[target_state.to_label(), f"priority/{issue.priority}"],
                        assignees=["manager-bot"],
                    )
                    for issue in ready_issues
                ]
                return issues_info
            return []

        coordinator._poll_issues_by_state = mock_poll

        if with_branches and role != "manager":

            def mock_flow_context(issue_number: int) -> tuple[str, dict | None]:
                return (f"task/issue-{issue_number}", None)

            coordinator._flow_context = mock_flow_context

    return coordinator


def make_capacity(remaining: int = 1) -> MagicMock:
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


def install_issue_loader(
    coordinator: GlobalDispatchCoordinator,
    states: dict[int, IssueState | None],
) -> None:
    coordinator._load_issue = lambda issue_number: (
        None
        if states.get(issue_number) is None
        else make_issue_info(issue_number, states[issue_number])
    )


class TestQueueOperations:
    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(self) -> None:
        issues = [make_issue(1), make_issue(2)]
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", issues, capacity=capacity, with_branches=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="claimed"),
                QueueEntry(issue_number=2, collected_state="claimed"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_supervisor_issue_removed_from_existing_frozen_queue(self) -> None:
        issue = make_issue(467)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator("handoff-manager", [issue], capacity=capacity)
        coordinator._frozen_queue = [
            QueueEntry(issue_number=467, collected_state="handoff", waiting_state=None)
        ]
        coordinator._load_issue = lambda issue_number: make_issue_info(
            issue_number,
            IssueState.HANDOFF,
            labels=["supervisor", IssueState.HANDOFF.to_label()],
            assignees=["manager-bot"],
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_ready_issue_no_manager_assignee_removed_from_frozen_queue(
        self,
    ) -> None:
        issue = make_issue(468)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator("manager", [issue], capacity=capacity)
        coordinator._frozen_queue = [
            QueueEntry(issue_number=468, collected_state="ready", waiting_state=None)
        ]
        coordinator._load_issue = lambda issue_number: make_issue_info(
            issue_number,
            IssueState.READY,
            assignees=[],
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_unassigned_handoff_issue_removed_from_frozen_queue(
        self,
    ) -> None:
        """Unassigned issues are now removed from queue at all stages (fix for #305)."""
        issue = make_issue(469)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator("handoff-manager", [issue], capacity=capacity)
        coordinator._frozen_queue = [
            QueueEntry(issue_number=469, collected_state="handoff", waiting_state=None)
        ]
        coordinator._load_issue = lambda issue_number: make_issue_info(
            issue_number,
            IssueState.HANDOFF,
            assignees=[],
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(self) -> None:
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", issues, capacity=capacity, with_branches=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="claimed"),
                QueueEntry(issue_number=2, collected_state="claimed"),
                QueueEntry(issue_number=3, collected_state="claimed"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
                3: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_frozen_queue_prevents_duplicate_dispatch_without_state_change(
        self,
    ) -> None:
        issues = [make_issue(1), make_issue(2)]
        capacity = make_capacity(remaining=3)

        coordinator = make_coordinator(
            "planner", issues, capacity=capacity, with_branches=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="claimed"),
                QueueEntry(issue_number=2, collected_state="claimed"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()
        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_emit_failure_handled_gracefully(self) -> None:
        issue1 = make_issue(1)
        issue2 = make_issue(2)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", [issue1, issue2], capacity=capacity, with_branches=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="claimed"),
                QueueEntry(issue_number=2, collected_state="claimed"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        call_count = [0]

        def emit_with_failure(role, issue):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("emit failed")
            emit_calls.append((role, issue))

        coordinator._emit_dispatch_intent = emit_with_failure

        await coordinator.coordinate()

        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_collect_failure_does_not_affect_other_roles(self) -> None:
        """Test that polling failure for one state doesn't prevent others."""
        issue_planner = make_issue(10)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [issue_planner], capacity=capacity, with_branches=True
        )

        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.READY:
                raise RuntimeError("API error")
            elif state == IssueState.CLAIMED:
                return [make_issue_info(10, IssueState.CLAIMED)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        install_issue_loader(coordinator, {10: IssueState.CLAIMED})

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 1

    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(self) -> None:
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return []

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(coordinator, {})

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0
