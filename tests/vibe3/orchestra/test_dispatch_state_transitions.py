"""Tests for GlobalDispatchCoordinator state transitions and priority handling."""

from __future__ import annotations

import re
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


class TestStateTransitions:
    @pytest.mark.asyncio
    async def test_collect_order_prefers_higher_state_roles_first(self) -> None:
        """Test that issues are collected in priority order."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.READY:
                return [make_issue_info(1, IssueState.READY)]
            elif state == IssueState.CLAIMED:
                return [make_issue_info(2, IssueState.CLAIMED)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        install_issue_loader(
            coordinator,
            {
                1: IssueState.READY,
                2: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2
        assert emit_calls[0][1].number == 2

    @pytest.mark.asyncio
    async def test_capacity_limit_stops_dispatch(self) -> None:
        """Test that capacity limit stops dispatch after limit reached."""
        _ = make_issue(304)
        _ = make_issue(303)
        _ = make_issue(372)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.REVIEW:
                return [make_issue_info(304, IssueState.REVIEW)]
            elif state == IssueState.CLAIMED:
                return [make_issue_info(303, IssueState.CLAIMED)]
            elif state == IssueState.READY:
                return [make_issue_info(372, IssueState.READY)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        install_issue_loader(
            coordinator,
            {
                304: IssueState.REVIEW,
                303: IssueState.CLAIMED,
                372: IssueState.READY,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2
        dispatched_numbers = [call[1].number for call in emit_calls]
        assert 304 in dispatched_numbers
        assert 303 in dispatched_numbers
        assert 372 not in dispatched_numbers

    @pytest.mark.asyncio
    async def test_state_change_requeues_issue_to_front(self) -> None:
        """Test that issue with state change gets promoted to front of queue."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.READY:
                return [
                    make_issue_info(1, IssueState.READY),
                    make_issue_info(2, IssueState.READY),
                ]
            return []

        coordinator._poll_issues_by_state = mock_poll

        states = {
            1: IssueState.READY,
            2: IssueState.READY,
        }
        install_issue_loader(coordinator, states)

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()
        assert len(emit_calls) == 1
        assert emit_calls[0][1].number == 1

        states[1] = IssueState.CLAIMED

        async def mock_poll_claimed(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.CLAIMED:
                return [make_issue_info(1, IssueState.CLAIMED)]
            return []

        coordinator._poll_issues_by_state = mock_poll_claimed

        await coordinator.coordinate()

        assert len(emit_calls) == 2
        assert emit_calls[1][1].number == 1

    @pytest.mark.asyncio
    async def test_terminal_state_removes_issue_from_queue(self) -> None:
        """Test that BLOCKED issues are removed from queue."""
        manager_issue = make_issue(1)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator("manager", [manager_issue], capacity=capacity)

        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.READY:
                return [make_issue_info(1, IssueState.READY)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        states = {1: IssueState.READY}
        install_issue_loader(coordinator, states)

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()
        assert len(emit_calls) == 1

        states[1] = IssueState.BLOCKED
        coordinator._load_issue = lambda issue_number: make_issue_info(
            issue_number,
            IssueState.BLOCKED,
        )

        await coordinator.coordinate()
        await coordinator.coordinate()

        assert len(emit_calls) == 1


class TestLoggingBehavior:
    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_instead_of_dispatch_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        planner_issue = make_issue(303)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [planner_issue], capacity=capacity, with_branches=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [QueueEntry(issue_number=303, collected_state="claimed")]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(coordinator, {303: IssueState.CLAIMED})

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            _ = level
            events.append(message)

        monkeypatch.setattr(
            "vibe3.orchestra.global_dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        await coordinator.coordinate()

        normalized_events = [
            re.sub(r"\x1b\[[0-9;]*m", "", message) for message in events
        ]

        assert any(
            "dispatch-intent #303 (planner)" in message for message in normalized_events
        )
        assert not any(
            "dispatched #303 (planner)" in message for message in normalized_events
        )

    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_before_emit_side_effect(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        planner_issue = make_issue(467)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [planner_issue], capacity=capacity, with_branches=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [QueueEntry(issue_number=467, collected_state="claimed")]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(coordinator, {467: IssueState.CLAIMED})

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            _ = level
            events.append(message)

        monkeypatch.setattr(
            "vibe3.orchestra.global_dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        def emit_side_effect(role, issue) -> None:
            capture_event(
                "dispatcher",
                "planner launch failed for #467: Failed to resolve permanent worktree",
            )

        coordinator._emit_dispatch_intent = emit_side_effect

        await coordinator.coordinate()

        normalized_events = [
            re.sub(r"\x1b\[[0-9;]*m", "", message) for message in events
        ]

        assert normalized_events[0] == (
            "GlobalDispatchCoordinator: dispatch-intent #467 (planner)"
        )
        assert normalized_events[1] == (
            "planner launch failed for #467: Failed to resolve permanent worktree"
        )
