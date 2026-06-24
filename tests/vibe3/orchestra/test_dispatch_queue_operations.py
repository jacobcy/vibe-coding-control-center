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
    @pytest.mark.slow
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
    @pytest.mark.slow
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
    @pytest.mark.slow
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
    @pytest.mark.slow
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
            "vibe3.services.issue.collection.IssueCollectionService.collect_open_issues",
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

    def test_single_issue_qualify_failure_does_not_abort_batch(
        self, make_issue, make_issue_info, monkeypatch
    ) -> None:
        """When one issue's qualify gate fails, other issues should still be
        collected."""
        from unittest.mock import MagicMock

        from vibe3.models.orchestra_config import OrchestraConfig
        from vibe3.orchestra.queue_operations import (
            select_ready_issues_from_collected_issues,
        )

        # Create two issues in READY state
        issue1 = make_issue(1, priority=5)
        issue2 = make_issue(2, priority=5)

        config = OrchestraConfig(repo="owner/repo")
        config.manager_usernames = ["manager-bot"]
        config.supervisor_handoff.issue_label = "supervisor"

        github = MagicMock()
        store = MagicMock()
        store.db_path = ":memory:"
        flow_manager = MagicMock()

        # Mock qualify gate to fail for issue #1, succeed for issue #2
        qualify_gate = MagicMock()
        call_count = [0]

        def mock_run_qualify_gate(issue, branch, flow_state, labels, trigger_state):
            call_count[0] += 1
            if issue.number == 1:
                raise RuntimeError("qualify gate failed for issue #1")
            elif issue.number == 2:
                return trigger_state  # Return trigger_state to indicate success
            return None

        qualify_gate.run_qualify_gate = mock_run_qualify_gate

        # Mock get_flow_context_bulk to return empty results
        monkeypatch.setattr(
            "vibe3.orchestra.get_flow_context_bulk",
            lambda numbers, config, github, store, flow_manager: {
                1: ("task/issue-1", None),
                2: ("task/issue-2", None),
            },
        )

        # Call select_ready_issues_from_collected_issues directly
        selected = select_ready_issues_from_collected_issues(
            issues=[issue1, issue2],
            trigger_state=IssueState.READY,
            config=config,
            github=github,
            store=store,
            flow_manager=flow_manager,
            qualify_gate=qualify_gate,
            supervisor_label="supervisor",
        )

        # Verify: issue #2 is selected, issue #1 is skipped
        assert len(selected) == 1
        assert selected[0].number == 2
        assert call_count[0] == 2  # Both issues were processed


class TestCollectFrozenQueueBlockedRequalification:
    """Regression tests for issue #2765: BLOCKED issues must be
    re-qualified during collection so resolved blockers get relabeled and
    picked up on the next pass."""

    @pytest.mark.asyncio
    async def test_requalifies_blocked_issues_during_collection(
        self, make_capacity, make_coordinator
    ) -> None:
        from unittest.mock import MagicMock

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
        ]

        qualify_mock = MagicMock(return_value=None)
        coordinator._qualify_gate.qualify_blocked_issue = qualify_mock

        queue = await coordinator._collect_frozen_queue()

        qualify_mock.assert_called_once()
        called_issue = qualify_mock.call_args[0][0]
        assert called_issue.number == 2
        assert [entry.issue_number for entry in queue] == [1]

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_requalify_failure_does_not_abort_collection(
        self, make_capacity, make_coordinator, monkeypatch
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
        ]

        def raise_qualify(issue):
            raise RuntimeError("qualify gate boom")

        coordinator._qualify_gate.qualify_blocked_issue = raise_qualify

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            _ = level
            events.append(message)

        monkeypatch.setattr(
            "vibe3.domain.dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        queue = await coordinator._collect_frozen_queue()

        assert [entry.issue_number for entry in queue] == [1]
        assert any(
            "requalify failed for #2" in e for e in events
        ), f"Expected requalify failure event for #2, got: {events}"


class TestCollectFrozenQueueLogging:
    """Regression tests for issue #2765 AC4: empty collections must not
    emit starting/complete orchestra events."""

    @pytest.mark.asyncio
    async def test_empty_collection_suppresses_logs(
        self, make_capacity, make_coordinator, monkeypatch
    ) -> None:
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=1),
            mock_health_check=True,
        )
        coordinator._github.list_issues.return_value = []

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            _ = level
            events.append(message)

        monkeypatch.setattr(
            "vibe3.domain.dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        queue = await coordinator._collect_frozen_queue()

        assert queue == []
        assert not any(
            "starting queue collection" in e or "queue collection complete" in e
            for e in events
        ), f"Expected no starting/complete logs for empty collection, got: {events}"

    @pytest.mark.asyncio
    async def test_nonempty_collection_logs_complete(
        self, make_capacity, make_coordinator, monkeypatch
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
        ]

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            _ = level
            events.append(message)

        monkeypatch.setattr(
            "vibe3.domain.dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        queue = await coordinator._collect_frozen_queue()

        assert [entry.issue_number for entry in queue] == [1]
        assert any(
            "queue collection complete, total=1 issues" in e for e in events
        ), f"Expected completion log for non-empty collection, got: {events}"
        assert not any("starting queue collection" in e for e in events)
