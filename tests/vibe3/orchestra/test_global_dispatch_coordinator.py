"""Tests for GlobalDispatchCoordinator."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    MAX_RETRY_COUNT,
    GlobalDispatchCoordinator,
    QueueEntry,
)


def make_issue(number: int, priority: int = 5) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.labels = [f"priority/{priority}"]
    issue.milestone = None
    issue.assignees = ["manager-bot"]  # Default assignee for dispatch tests
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


def make_service(role: str, ready_issues: list) -> MagicMock:
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
    @pytest.fixture(autouse=True)
    def mock_subprocess_run(self):
        """Mock subprocess.run to avoid tmux dependency in tests."""
        with patch("subprocess.run") as mock_run:
            # Make subprocess.run raise an exception to use capacity.get_capacity_status
            mock_run.side_effect = Exception("tmux not available in tests")
            yield mock_run

    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(self) -> None:
        issues = [make_issue(1), make_issue(2)]
        service = make_service("planner", issues)
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        await coordinator.coordinate()

        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_supervisor_issue_removed_from_existing_frozen_queue(self) -> None:
        issue = make_issue(467)
        service = make_service("handoff-manager", [issue])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        coordinator._frozen_queue = [
            QueueEntry(issue_number=467, collected_state="claimed", waiting_state=None)
        ]
        coordinator._load_issue = lambda issue_number: IssueInfo(  # type: ignore[method-assign]
            number=issue_number,
            title=f"Issue {issue_number}",
            state=IssueState.HANDOFF,
            labels=["supervisor", IssueState.HANDOFF.to_label()],
            assignees=[],
        )

        await coordinator.coordinate()

        service._emit_dispatch_intent.assert_not_called()
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_ready_issue_no_manager_assignee_removed_from_frozen_queue(
        self,
    ) -> None:
        issue = make_issue(468)
        service = make_service("manager", [issue])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        coordinator._frozen_queue = [
            QueueEntry(issue_number=468, collected_state="ready", waiting_state=None)
        ]
        coordinator._load_issue = lambda issue_number: make_issue_info(  # type: ignore[method-assign]
            issue_number,
            IssueState.READY,
            assignees=[],
        )

        await coordinator.coordinate()

        service._emit_dispatch_intent.assert_not_called()
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_unassigned_handoff_issue_removed_from_frozen_queue(
        self,
    ) -> None:
        """Unassigned issues are now removed from queue at all stages (fix for #305)."""
        issue = make_issue(469)
        service = make_service("handoff-manager", [issue])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        coordinator._frozen_queue = [
            QueueEntry(issue_number=469, collected_state="handoff", waiting_state=None)
        ]
        coordinator._load_issue = lambda issue_number: make_issue_info(  # type: ignore[method-assign]
            issue_number,
            IssueState.HANDOFF,
            assignees=[],  # No assignee -> should be removed
        )

        await coordinator.coordinate()

        # Unassigned issue should be removed, not dispatched
        service._emit_dispatch_intent.assert_not_called()
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(self) -> None:
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        service = make_service("planner", issues)
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
                3: IssueState.CLAIMED,
            },
        )

        await coordinator.coordinate()

        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_frozen_queue_prevents_duplicate_dispatch_without_state_change(
        self,
    ) -> None:
        issues = [make_issue(1), make_issue(2)]
        service = make_service("planner", issues)
        capacity = make_capacity(remaining=3)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        await coordinator.coordinate()
        await coordinator.coordinate()

        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_emit_failure_handled_gracefully(self) -> None:
        issue1 = make_issue(1)
        issue2 = make_issue(2)
        service = make_service("planner", [issue1, issue2])
        service._emit_dispatch_intent.side_effect = [
            RuntimeError("emit failed"),
            None,
        ]
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        await coordinator.coordinate()

        assert service._emit_dispatch_intent.call_count == 2

    @pytest.mark.asyncio
    async def test_collect_failure_does_not_affect_other_roles(self) -> None:
        issue_planner = make_issue(10)
        bad_service = make_service("manager", [])
        bad_service.collect_ready_issues = AsyncMock(side_effect=RuntimeError("API"))
        good_service = make_service("planner", [issue_planner])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [bad_service, good_service])
        install_issue_loader(coordinator, {10: IssueState.CLAIMED})

        await coordinator.coordinate()

        good_service._emit_dispatch_intent.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(self) -> None:
        service = make_service("planner", [])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [service])
        install_issue_loader(coordinator, {})

        await coordinator.coordinate()

        service._emit_dispatch_intent.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_order_prefers_higher_state_roles_first(self) -> None:
        manager_issue = make_issue(1)
        planner_issue = make_issue(2)
        manager_svc = make_service("manager", [manager_issue])
        planner_svc = make_service("planner", [planner_issue])
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc, planner_svc])
        install_issue_loader(
            coordinator,
            {
                1: IssueState.READY,
                2: IssueState.CLAIMED,
            },
        )

        await coordinator.coordinate()

        planner_svc._emit_dispatch_intent.assert_called_once()
        manager_svc._emit_dispatch_intent.assert_called_once()

    @pytest.mark.asyncio
    async def test_capacity_limit_stops_dispatch(self) -> None:
        review_issue = make_issue(304)
        planner_issue = make_issue(303)
        manager_issue = make_issue(372)
        review_svc = make_service("review", [review_issue])
        planner_svc = make_service("plan", [planner_issue])
        manager_svc = make_service("manager", [manager_issue])
        capacity = make_capacity(remaining=2)

        coordinator = GlobalDispatchCoordinator(
            capacity, [manager_svc, planner_svc, review_svc]
        )
        install_issue_loader(
            coordinator,
            {
                304: IssueState.REVIEW,
                303: IssueState.CLAIMED,
                372: IssueState.READY,
            },
        )

        await coordinator.coordinate()

        review_dispatched = review_svc._emit_dispatch_intent.call_args.args[0]
        planner_dispatched = planner_svc._emit_dispatch_intent.call_args.args[0]
        assert review_dispatched.number == 304
        assert planner_dispatched.number == 303
        manager_svc._emit_dispatch_intent.assert_not_called()

    @pytest.mark.asyncio
    async def test_state_change_requeues_issue_to_front(self) -> None:
        first_manager_issue = make_issue(1)
        second_manager_issue = make_issue(2)
        manager_svc = make_service(
            "manager", [first_manager_issue, second_manager_issue]
        )
        planner_svc = make_service("planner", [])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc, planner_svc])
        states = {
            1: IssueState.READY,
            2: IssueState.READY,
        }
        install_issue_loader(coordinator, states)

        await coordinator.coordinate()
        first_dispatched = manager_svc._emit_dispatch_intent.call_args.args[0]
        assert first_dispatched.number == 1

        states[1] = IssueState.CLAIMED
        await coordinator.coordinate()

        assert planner_svc._emit_dispatch_intent.call_count == 1
        promoted_issue = planner_svc._emit_dispatch_intent.call_args.args[0]
        assert promoted_issue.number == 1

    @pytest.mark.asyncio
    async def test_terminal_state_removes_issue_from_queue(self) -> None:
        manager_issue = make_issue(1)
        manager_svc = make_service("manager", [manager_issue])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [manager_svc])
        states = {1: IssueState.READY}
        install_issue_loader(coordinator, states)

        await coordinator.coordinate()
        states[1] = IssueState.BLOCKED
        await coordinator.coordinate()
        await coordinator.coordinate()

        assert manager_svc._emit_dispatch_intent.call_count == 1

    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_instead_of_dispatch_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        planner_issue = make_issue(303)
        planner_svc = make_service("planner", [planner_issue])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [planner_svc])
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
        planner_svc = make_service("planner", [planner_issue])
        capacity = make_capacity(remaining=1)
        coordinator = GlobalDispatchCoordinator(capacity, [planner_svc])
        install_issue_loader(coordinator, {467: IssueState.CLAIMED})

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            _ = level
            events.append(message)

        def emit_side_effect(_issue: MagicMock) -> None:
            capture_event(
                "dispatcher",
                "planner launch failed for #467: Failed to resolve permanent worktree",
            )

        planner_svc._emit_dispatch_intent.side_effect = emit_side_effect

        monkeypatch.setattr(
            "vibe3.orchestra.global_dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        await coordinator.coordinate()

        normalized_events = [
            re.sub(r"\x1b\[[0-9;]*m", "", message) for message in events
        ]

        # New diagnostic logging adds "starting queue collection"
        # and "queue collection complete"
        assert normalized_events[0] == (
            "GlobalDispatchCoordinator: starting queue collection"
        )
        assert normalized_events[1] == (
            "GlobalDispatchCoordinator: queue collection complete, total=1 issues"
        )
        # Original logs now at index 2 and 3
        assert normalized_events[2] == (
            "GlobalDispatchCoordinator: dispatch-intent #467 (planner)"
        )
        assert normalized_events[3] == (
            "planner launch failed for #467: Failed to resolve permanent worktree"
        )

    @pytest.mark.asyncio
    async def test_queue_persisted_after_dispatch_intent(self) -> None:
        """Verify SQLite contains entry after coordinate() emits dispatch intent."""
        issue = make_issue(100)
        service = make_service("planner", [issue])
        capacity = make_capacity(remaining=1)

        # Create mock store
        store = MagicMock()
        store.load_queue_entries.return_value = []

        coordinator = GlobalDispatchCoordinator(capacity, [service], store=store)
        install_issue_loader(coordinator, {100: IssueState.CLAIMED})

        await coordinator.coordinate()

        # Verify persistence was called to save the entry
        store.save_queue_entry.assert_called()
        call_args = store.save_queue_entry.call_args
        assert call_args[1]["issue_number"] == 100
        assert call_args[1]["collected_state"] == "claimed"

    @pytest.mark.asyncio
    async def test_queue_loaded_on_coordinator_init(self) -> None:
        """Verify entries restored from SQLite on coordinator initialization."""
        # Setup mock store with persisted data
        store = MagicMock()
        store.load_queue_entries.return_value = [
            {
                "issue_number": 200,
                "collected_state": "in-progress",
                "waiting_state": None,
                "retry_count": 2,
            },
            {
                "issue_number": 201,
                "collected_state": "review",
                "waiting_state": "review",
                "retry_count": 1,
            },
        ]

        service = make_service("planner", [])
        capacity = make_capacity(remaining=1)

        coordinator = GlobalDispatchCoordinator(capacity, [service], store=store)

        # Verify queue was loaded from persistence
        assert coordinator._frozen_queue is not None
        assert len(coordinator._frozen_queue) == 2
        assert coordinator._frozen_queue[0].issue_number == 200
        assert coordinator._frozen_queue[0].retry_count == 2
        assert coordinator._frozen_queue[1].issue_number == 201
        assert coordinator._frozen_queue[1].waiting_state == "review"

    @pytest.mark.asyncio
    async def test_entry_removed_after_state_done(self) -> None:
        """Verify SQLite cleanup on terminal state."""
        issue = make_issue(300)
        service = make_service("manager", [issue])
        capacity = make_capacity(remaining=1)

        store = MagicMock()
        # Simulate a persisted entry being loaded
        store.load_queue_entries.return_value = [
            {
                "issue_number": 300,
                "collected_state": "ready",
                "waiting_state": None,
                "retry_count": 0,
            }
        ]

        coordinator = GlobalDispatchCoordinator(capacity, [service], store=store)
        states = {300: IssueState.READY}
        install_issue_loader(coordinator, states)

        # First coordinate - dispatch intent emitted
        await coordinator.coordinate()

        # Now issue is done
        states[300] = IssueState.DONE
        await coordinator.coordinate()

        # Verify entry was removed from persistence
        store.remove_queue_entry.assert_called_with(300)

    @pytest.mark.asyncio
    async def test_retry_threshold_removes_entry(self) -> None:
        """Verify auto-removal after exceeding MAX_RETRY_COUNT."""
        service = make_service("planner", [])
        capacity = make_capacity(remaining=1)

        store = MagicMock()
        # Return entry with retry_count exceeding threshold
        store.load_queue_entries.return_value = [
            {
                "issue_number": 400,
                "collected_state": "claimed",
                "waiting_state": "claimed",
                "retry_count": MAX_RETRY_COUNT + 1,
            }
        ]
        store.get_queue_entries_over_retry_limit.return_value = [400]

        coordinator = GlobalDispatchCoordinator(capacity, [service], store=store)
        install_issue_loader(coordinator, {400: IssueState.CLAIMED})

        await coordinator.coordinate()

        # Verify entry was removed from both memory and persistence
        assert coordinator._frozen_queue is not None
        assert 400 not in [e.issue_number for e in coordinator._frozen_queue]
        store.remove_queue_entry.assert_called_with(400)

    @pytest.mark.asyncio
    async def test_server_restart_preserves_queue(self) -> None:
        """Integration test: queue survives simulated restart."""
        issue = make_issue(500)
        manager_service = make_service("manager", [issue])
        planner_service = make_service("planner", [])
        capacity = make_capacity(remaining=1)

        # First run: collect and dispatch
        store = MagicMock()
        store.load_queue_entries.return_value = []

        coordinator1 = GlobalDispatchCoordinator(
            capacity, [manager_service, planner_service], store=store
        )
        install_issue_loader(coordinator1, {500: IssueState.READY})

        await coordinator1.coordinate()
        assert manager_service._emit_dispatch_intent.call_count == 1

        # Verify entry was persisted with waiting_state
        save_call = store.save_queue_entry.call_args
        assert save_call[1]["issue_number"] == 500
        assert save_call[1]["waiting_state"] == "ready"

        # Simulate restart: load persisted state
        store.load_queue_entries.return_value = [
            {
                "issue_number": 500,
                "collected_state": "ready",
                "waiting_state": "ready",
                "retry_count": 1,
            }
        ]

        coordinator2 = GlobalDispatchCoordinator(
            capacity, [manager_service, planner_service], store=store
        )
        install_issue_loader(coordinator2, {500: IssueState.CLAIMED})  # State changed

        # Verify queue was restored on restart
        assert coordinator2._frozen_queue is not None
        assert len(coordinator2._frozen_queue) == 1
        assert coordinator2._frozen_queue[0].issue_number == 500
        assert coordinator2._frozen_queue[0].retry_count == 1

        # State changed from ready to claimed - should be promoted to front
        await coordinator2.coordinate()
        # Entry should be promoted and dispatched via planner service
        assert len(coordinator2._frozen_queue) == 1
        assert (
            coordinator2._frozen_queue[0].waiting_state == "claimed"
        )  # Set after dispatch
        assert coordinator2._frozen_queue[0].retry_count == 0  # Reset on promotion
        # Should dispatch via planner service (for CLAIMED state)
        assert planner_service._emit_dispatch_intent.call_count == 1
