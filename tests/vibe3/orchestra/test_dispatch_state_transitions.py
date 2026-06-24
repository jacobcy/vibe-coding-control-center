"""Tests for GlobalDispatchCoordinator state transitions and priority handling."""

from __future__ import annotations

import re

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.global_dispatch_coordinator import QueueEntry


class TestStateTransitions:
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_collect_order_prefers_higher_state_roles_first(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
    ) -> None:
        """Test that issues are collected in priority order."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=2, collected_state="claimed"),
                QueueEntry(issue_number=1, collected_state="ready"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.READY,
                2: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        # First tick: collects entries
        await coordinator.coordinate()
        # Second tick: dispatches in priority order
        await coordinator.coordinate()

        assert len(emit_calls) == 2
        assert emit_calls[0][1].number == 2

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_capacity_limit_stops_dispatch(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
    ) -> None:
        """Test that capacity limit stops dispatch after limit reached."""
        _ = make_issue(304)
        _ = make_issue(303)
        _ = make_issue(372)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=304, collected_state="review"),
                QueueEntry(issue_number=303, collected_state="claimed"),
                QueueEntry(issue_number=372, collected_state="ready"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                304: IssueState.REVIEW,
                303: IssueState.CLAIMED,
                372: IssueState.READY,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        # First tick: collects entries
        await coordinator.coordinate()
        # Second tick: dispatches (limited by capacity)
        await coordinator.coordinate()

        assert len(emit_calls) == 2
        dispatched_numbers = [call[1].number for call in emit_calls]
        assert 304 in dispatched_numbers
        assert 303 in dispatched_numbers
        assert 372 not in dispatched_numbers

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_state_change_requeues_issue_to_front(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
    ) -> None:
        """Test that issue with state change gets promoted to front of queue."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="ready"),
                QueueEntry(issue_number=2, collected_state="ready"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        states = {
            1: IssueState.READY,
            2: IssueState.READY,
        }
        install_issue_loader(coordinator, states)

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        # First tick: collects entries
        await coordinator.coordinate()
        # Second tick: dispatches first issue
        await coordinator.coordinate()
        assert len(emit_calls) == 1
        assert emit_calls[0][1].number == 1

        states[1] = IssueState.CLAIMED

        await coordinator.coordinate()

        assert len(emit_calls) == 2
        assert emit_calls[1][1].number == 1

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_terminal_state_removes_issue_from_queue(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        make_issue_info,
    ) -> None:
        """Blocked issues are removed when qualification keeps them blocked."""
        _ = make_issue(1)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "manager", capacity=capacity, mock_health_check=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [QueueEntry(issue_number=1, collected_state="ready")]

        coordinator._collect_frozen_queue = mock_collect

        states = {1: IssueState.READY}
        install_issue_loader(coordinator, states)

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        # First tick: collects entries
        await coordinator.coordinate()
        # Second tick: dispatches manager issue
        await coordinator.coordinate()
        assert len(emit_calls) == 1

        states[1] = IssueState.BLOCKED
        coordinator._load_issue = lambda issue_number: make_issue_info(
            issue_number,
            IssueState.BLOCKED,
        )
        coordinator._qualify_gate.qualify_blocked_issue = lambda issue: None

        await coordinator.coordinate()
        await coordinator.coordinate()

        assert len(emit_calls) == 1

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_blocked_issue_removed_from_queue_when_qualify_gate_fails(
        self,
        make_capacity,
        make_coordinator,
        make_issue_info,
    ) -> None:
        """Blocked issues are removed from queue when qualify gate finds no target."""
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "manager",
            capacity=capacity,
            mock_health_check=True,
        )

        async def mock_collect() -> list[QueueEntry]:
            return [QueueEntry(issue_number=100, collected_state="blocked")]

        coordinator._collect_frozen_queue = mock_collect

        # Mock _load_issue to return the issue with BLOCKED label
        coordinator._load_issue = lambda issue_number: make_issue_info(
            issue_number,
            IssueState.BLOCKED,
            labels=["state/blocked"],
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id=0: emit_calls.append((role, issue))
        )

        # First tick: collects BLOCKED issue
        await coordinator.coordinate()
        # Second tick: blocked issue is skipped and removed from queue
        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []


class TestLoggingBehavior:
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_instead_of_dispatch_success(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _ = make_issue(303)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner",
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
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
            "vibe3.domain.dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        # First tick: collects entries
        await coordinator.coordinate()
        # Second tick: dispatches and logs intent
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

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_before_emit_side_effect(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _ = make_issue(467)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner",
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
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
            "vibe3.domain.dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        def emit_side_effect(role, issue, tick_id=0) -> None:
            capture_event(
                "dispatcher",
                "planner launch failed for #467: Failed to resolve permanent worktree",
            )

        coordinator._emit_dispatch_intent = emit_side_effect

        # First tick: collects entries
        await coordinator.coordinate()
        # Second tick: dispatches and logs intent before emit
        await coordinator.coordinate()

        normalized_events = [
            re.sub(r"\x1b\[[0-9;]*m", "", message) for message in events
        ]

        intent_idx = next(
            i
            for i, m in enumerate(normalized_events)
            if "dispatch-intent #467 (planner)" in m
        )
        side_effect_idx = next(
            i
            for i, m in enumerate(normalized_events)
            if "planner launch failed for #467" in m
        )
        assert (
            intent_idx < side_effect_idx
        ), "dispatch-intent should be logged before emit side effect"
