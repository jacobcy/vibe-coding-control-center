"""Tests for GlobalDispatchCoordinator."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import GlobalDispatchCoordinator


def make_issue(number: int, priority: int = 5) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.labels = [f"priority/{priority}"]
    issue.milestone = None
    return issue


def make_issue_info(number: int, state: IssueState) -> IssueInfo:
    return IssueInfo(
        number=number,
        title=f"Issue {number}",
        state=state,
        labels=[state.to_label()],
        assignees=[],
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
            "max_capacity": 5,
        }
    )
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
