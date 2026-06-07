"""Tests for GlobalDispatchCoordinator queue operations."""

from __future__ import annotations

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    QueueEntry,
)


class TestQueueOperations:
    """Tests for GlobalDispatchCoordinator queue operations."""

    @pytest.mark.asyncio
    async def test_collect_frozen_queue_uses_one_open_issue_call(
        self, make_issue, make_capacity, make_coordinator
    ) -> None:
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=1),
            mock_health_check=True,
        )
        coordinator._github.list_issues.return_value = [
            {
                "number": 1,
                "title": "Ready",
                "labels": [{"name": "state/ready"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
                "state": "OPEN",
            },
            {
                "number": 2,
                "title": "Blocked",
                "labels": [{"name": "state/blocked"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
                "state": "OPEN",
            },
            {
                "number": 3,
                "title": "Epic",
                "labels": [{"name": "state/ready"}, {"name": "roadmap/epic"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
                "state": "OPEN",
            },
        ]

        queue = await coordinator._collect_frozen_queue()

        coordinator._github.list_issues.assert_called_once()
        _, kwargs = coordinator._github.list_issues.call_args
        assert kwargs.get("label") is None
        assert [entry.issue_number for entry in queue] == [1]

    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
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

        # First tick: collects entries (queue was empty after restore)
        await coordinator.coordinate()
        # Second tick: dispatches collected entries
        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "issue_num,role,collected_state,issue_state,labels,assignees",
        [
            (
                467,
                "handoff-manager",
                "handoff",
                IssueState.HANDOFF,
                ["supervisor", "state/handoff"],
                ["manager-bot"],
            ),
            (468, "manager", "ready", IssueState.READY, ["state/ready"], []),
            (
                469,
                "handoff-manager",
                "handoff",
                IssueState.HANDOFF,
                ["state/handoff"],
                [],
            ),
        ],
    )
    async def test_invalid_issues_removed_from_frozen_queue(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        make_issue_info,
        issue_num,
        role,
        collected_state,
        issue_state,
        labels,
        assignees,
    ) -> None:
        """Issues violating queue criteria are removed (supervisor, no assignee)."""
        _ = make_issue(issue_num)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(role, capacity=capacity, mock_health_check=True)
        coordinator._frozen_queue = [
            QueueEntry(
                issue_number=issue_num,
                collected_state=collected_state,
                waiting_state=None,
            )
        ]
        coordinator._load_issue = lambda n: make_issue_info(
            n, issue_state, labels=labels, assignees=assignees
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda r, i, t: emit_calls.append((r, i))

        # Mock _collect_frozen_queue to return empty list
        # (prevent re-collection after invalid removal)
        async def mock_collect_empty() -> list[QueueEntry]:
            return []

        coordinator._collect_frozen_queue = mock_collect_empty

        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
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

        # First tick: collects entries
        await coordinator.coordinate()
        # Second tick: dispatches (limited by capacity)
        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_frozen_queue_prevents_duplicate_dispatch_without_state_change(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        capacity = make_capacity(remaining=3)

        coordinator = make_coordinator(
            "planner",
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
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
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
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

        # First tick: collects entries
        await coordinator.coordinate()
        # Second tick: tries to dispatch, fails on first emit
        with pytest.raises(RuntimeError, match="emit failed"):
            await coordinator.coordinate()

        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_collect_failure_returns_empty_queue(
        self, make_capacity, make_coordinator, monkeypatch
    ) -> None:
        """Collection failure should leave the frozen queue empty."""
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner",
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
        )

        def fail_collect(self, limit: int = 100) -> list:
            raise RuntimeError("API error")

        monkeypatch.setattr(
            "vibe3.services.issue_collection_service.IssueCollectionService.collect_open_issues",
            fail_collect,
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()
        await coordinator.coordinate()

        assert len(emit_calls) == 0

    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(
        self, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
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
