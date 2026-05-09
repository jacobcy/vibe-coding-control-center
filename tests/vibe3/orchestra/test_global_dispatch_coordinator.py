"""Tests for GlobalDispatchCoordinator."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

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
    issue.assignees = ["manager-bot"]  # Default assignee for dispatch tests
    issue.priority = priority  # Add priority attribute
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

    # Mock _poll_issues_by_state to return ready_issues for the appropriate state
    if ready_issues:
        # Map role to state
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

        # Mock _flow_context to provide branches for non-manager roles
        if with_branches and role != "manager":

            def mock_flow_context(issue_number: int) -> tuple[str, dict | None]:
                return (f"task/issue-{issue_number}", None)

            coordinator._flow_context = mock_flow_context

    return coordinator


def make_service(role: str, ready_issues: list) -> MagicMock:
    """DEPRECATED: Use make_coordinator instead."""
    service = MagicMock()
    service.service_name = f"mock-{role}"
    role_map = {
        "manager": ("manager", "manager", "ready"),
        "handoff-manager": ("manager", "manager", "handoff"),
        "planner": ("plan", "planner", "claimed"),
        "plan": ("plan", "planner", "claimed"),
        "executor": ("run", "executor", "in-progress"),
        "run": ("run", "executor", "in-progress"),
        "reviewer": ("review", "reviewer", "review"),
        "review": ("review", "reviewer", "review"),
    }
    trigger_name, registry_role, trigger_state = role_map.get(
        role, ("manager", role, "ready")
    )
    service.role_def.trigger_name = trigger_name
    service.role_def.registry_role = registry_role
    service.role_def.trigger_state = IssueState(trigger_state)
    service.collect_ready_issues = AsyncMock(return_value=ready_issues)
    service._emit_dispatch_intent = MagicMock()
    # Configure manager_usernames to match test assignees
    service.config.manager_usernames = ["manager-bot"]
    service.config.supervisor_handoff.issue_label = "supervisor"
    service.config.repo = "owner/repo"
    service._github = MagicMock()
    return service


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
    # Mock _run_command to avoid tmux check and use capacity status directly
    capacity._run_command = MagicMock(
        side_effect=Exception("tmux not available in tests")
    )
    capacity._backend = None
    return capacity


def install_issue_loader(
    coordinator: GlobalDispatchCoordinator,
    states: dict[int, IssueState | None],
) -> None:
    coordinator._load_issue = lambda issue_number: (  # type: ignore[method-assign]
        None
        if states.get(issue_number) is None
        else make_issue_info(issue_number, states[issue_number])
    )


class TestGlobalDispatchCoordinator:
    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(self) -> None:
        issues = [make_issue(1), make_issue(2)]
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", issues, capacity=capacity, with_branches=True
        )

        # Mock _collect_frozen_queue to return controlled queue
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

        # Mock _emit_dispatch_intent to track calls
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
        coordinator._load_issue = lambda issue_number: make_issue_info(  # type: ignore[method-assign]
            issue_number,
            IssueState.HANDOFF,
            labels=["supervisor", IssueState.HANDOFF.to_label()],
            assignees=["manager-bot"],
        )

        # Track dispatch calls
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
        coordinator._load_issue = lambda issue_number: make_issue_info(  # type: ignore[method-assign]
            issue_number,
            IssueState.READY,
            assignees=[],
        )

        # Track dispatch calls
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
        coordinator._load_issue = lambda issue_number: make_issue_info(  # type: ignore[method-assign]
            issue_number,
            IssueState.HANDOFF,
            assignees=[],  # No assignee -> should be removed
        )

        # Track dispatch calls
        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        # Unassigned issue should be removed, not dispatched
        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(self) -> None:
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", issues, capacity=capacity, with_branches=True
        )

        # Mock _collect_frozen_queue to return controlled queue
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

        # Track dispatch calls
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

        # Mock _collect_frozen_queue to return controlled queue
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

        # Track dispatch calls
        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()
        await coordinator.coordinate()

        # Only 2 calls (no duplicate dispatch)
        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_emit_failure_handled_gracefully(self) -> None:
        issue1 = make_issue(1)
        issue2 = make_issue(2)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", [issue1, issue2], capacity=capacity, with_branches=True
        )

        # Mock _collect_frozen_queue
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

        # Mock _emit_dispatch_intent to fail on first call
        emit_calls = []
        call_count = [0]

        def emit_with_failure(role, issue):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("emit failed")
            emit_calls.append((role, issue))

        coordinator._emit_dispatch_intent = emit_with_failure

        await coordinator.coordinate()

        # Both calls should be made (second succeeds)
        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_collect_failure_does_not_affect_other_roles(self) -> None:
        """Test that polling failure for one state doesn't prevent others."""
        issue_planner = make_issue(10)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [issue_planner], capacity=capacity, with_branches=True
        )

        # Mock _poll_issues_by_state to fail for READY state but succeed for CLAIMED
        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.READY:
                raise RuntimeError("API error")
            elif state == IssueState.CLAIMED:
                return [make_issue_info(10, IssueState.CLAIMED)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        install_issue_loader(coordinator, {10: IssueState.CLAIMED})

        # Track dispatch calls
        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        # Planner issue should still be dispatched
        assert len(emit_calls) == 1

    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(self) -> None:
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        # Mock _collect_frozen_queue to return empty queue
        async def mock_collect() -> list[QueueEntry]:
            return []

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(coordinator, {})

        # Track dispatch calls
        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0

    @pytest.mark.asyncio
    async def test_collect_order_prefers_higher_state_roles_first(self) -> None:
        """Test that issues are collected in priority order."""
        _ = make_issue(1)  # manager
        _ = make_issue(2)  # planner
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        # Mock _poll_issues_by_state to return different issues for different states
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

        # Track dispatch calls
        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        # Both issues should be dispatched (CLAIMED first due to priority order)
        assert len(emit_calls) == 2
        # First dispatched should be CLAIMED (planner issue #2)
        assert emit_calls[0][1].number == 2

    @pytest.mark.asyncio
    async def test_capacity_limit_stops_dispatch(self) -> None:
        """Test that capacity limit stops dispatch after limit reached."""
        _ = make_issue(304)  # review
        _ = make_issue(303)  # planner
        _ = make_issue(372)  # manager
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        # Mock _poll_issues_by_state to return issues in different states
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

        # Track dispatch calls
        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()

        # Only 2 issues should be dispatched (capacity limit)
        assert len(emit_calls) == 2
        # REVIEW and CLAIMED should be dispatched (priority order), READY should not
        dispatched_numbers = [call[1].number for call in emit_calls]
        assert 304 in dispatched_numbers
        assert 303 in dispatched_numbers
        assert 372 not in dispatched_numbers

    @pytest.mark.asyncio
    async def test_state_change_requeues_issue_to_front(self) -> None:
        """Test that issue with state change gets promoted to front of queue."""
        _ = make_issue(1)  # first manager
        _ = make_issue(2)  # second manager
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        # Mock _poll_issues_by_state to return two READY issues initially
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

        # Track dispatch calls
        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()
        # First issue should be dispatched
        assert len(emit_calls) == 1
        assert emit_calls[0][1].number == 1

        # Issue #1 state changes to CLAIMED
        states[1] = IssueState.CLAIMED

        # Mock _poll_issues_by_state to return CLAIMED issue now
        async def mock_poll_claimed(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.CLAIMED:
                return [make_issue_info(1, IssueState.CLAIMED)]
            return []

        coordinator._poll_issues_by_state = mock_poll_claimed

        await coordinator.coordinate()

        # Issue #1 should be dispatched again as planner (CLAIMED state)
        assert len(emit_calls) == 2
        assert emit_calls[1][1].number == 1

    @pytest.mark.asyncio
    async def test_terminal_state_removes_issue_from_queue(self) -> None:
        """Test that BLOCKED issues are removed from queue."""
        manager_issue = make_issue(1)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator("manager", [manager_issue], capacity=capacity)

        # Mock _poll_issues_by_state to return READY issue initially
        async def mock_poll(state: IssueState) -> list[IssueInfo]:
            if state == IssueState.READY:
                return [make_issue_info(1, IssueState.READY)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        states = {1: IssueState.READY}
        install_issue_loader(coordinator, states)

        # Track dispatch calls
        emit_calls = []
        coordinator._emit_dispatch_intent = lambda role, issue: emit_calls.append(
            (role, issue)
        )

        await coordinator.coordinate()
        # Issue should be dispatched once
        assert len(emit_calls) == 1

        # Issue becomes BLOCKED
        states[1] = IssueState.BLOCKED
        # Mock _load_issue to return BLOCKED issue
        coordinator._load_issue = lambda issue_number: make_issue_info(  # type: ignore[method-assign]
            issue_number,
            IssueState.BLOCKED,
        )

        await coordinator.coordinate()
        await coordinator.coordinate()

        # No additional dispatches (BLOCKED issue removed from queue)
        assert len(emit_calls) == 1

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

        # Mock _collect_frozen_queue to return controlled queue
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

        # Mock _collect_frozen_queue to return controlled queue
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
