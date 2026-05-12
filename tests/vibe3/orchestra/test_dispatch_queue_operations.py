"""Tests for GlobalDispatchCoordinator queue operations."""

from __future__ import annotations

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.global_dispatch_coordinator import QueueEntry


class TestQueueOperations:
    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_supervisor_issue_removed_from_existing_frozen_queue(
        self, make_issue, make_capacity, make_coordinator, make_issue_info
    ) -> None:
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_ready_issue_no_manager_assignee_removed_from_frozen_queue(
        self, make_issue, make_capacity, make_coordinator, make_issue_info
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_unassigned_handoff_issue_removed_from_frozen_queue(
        self, make_issue, make_capacity, make_coordinator, make_issue_info
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_frozen_queue_prevents_duplicate_dispatch_without_state_change(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()
        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_emit_failure_handled_gracefully(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
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

        def emit_with_failure(role, issue, tick_id=0):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("emit failed")
            emit_calls.append((role, issue))

        coordinator._emit_dispatch_intent = emit_with_failure

        await coordinator.coordinate()

        assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_collect_failure_does_not_affect_other_roles(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        make_issue_info,
    ) -> None:
        """Test that polling failure for one state doesn't prevent others."""
        issue_planner = make_issue(10)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [issue_planner], capacity=capacity, with_branches=True
        )

        async def mock_poll(state: IssueState) -> list:
            if state == IssueState.READY:
                raise RuntimeError("API error")
            elif state == IssueState.CLAIMED:
                return [make_issue_info(10, IssueState.CLAIMED)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        install_issue_loader(coordinator, {10: IssueState.CLAIMED})

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 1

    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(
        self, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return []

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(coordinator, {})

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0
