"""Tests for GlobalDispatchCoordinator state transitions and priority handling."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import QueueEntry
from vibe3.orchestra.queue_operations import promote_progressed_entries


class TestStateTransitions:
    @pytest.mark.asyncio
    async def test_collect_order_prefers_higher_state_roles_first(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        make_issue_info,
    ) -> None:
        """Test that issues are collected in priority order."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        async def mock_poll(state: IssueState) -> list:
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2
        assert emit_calls[0][1].number == 2

    @pytest.mark.asyncio
    async def test_capacity_limit_stops_dispatch(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        make_issue_info,
    ) -> None:
        """Test that capacity limit stops dispatch after limit reached."""
        _ = make_issue(304)
        _ = make_issue(303)
        _ = make_issue(372)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        async def mock_poll(state: IssueState) -> list:
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2
        dispatched_numbers = [call[1].number for call in emit_calls]
        assert 304 in dispatched_numbers
        assert 303 in dispatched_numbers
        assert 372 not in dispatched_numbers

    @pytest.mark.asyncio
    async def test_state_change_requeues_issue_to_front(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        make_issue_info,
    ) -> None:
        """Test that issue with state change gets promoted to front of queue."""
        _ = make_issue(1)
        _ = make_issue(2)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True
        )

        async def mock_poll(state: IssueState) -> list:
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
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()
        assert len(emit_calls) == 1
        assert emit_calls[0][1].number == 1

        states[1] = IssueState.CLAIMED

        async def mock_poll_claimed(state: IssueState) -> list:
            if state == IssueState.CLAIMED:
                return [make_issue_info(1, IssueState.CLAIMED)]
            return []

        coordinator._poll_issues_by_state = mock_poll_claimed

        await coordinator.coordinate()

        assert len(emit_calls) == 2
        assert emit_calls[1][1].number == 1

    @pytest.mark.asyncio
    async def test_terminal_state_removes_issue_from_queue(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        make_issue_info,
    ) -> None:
        """Test that BLOCKED issues are removed from queue."""
        manager_issue = make_issue(1)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator("manager", [manager_issue], capacity=capacity)

        async def mock_poll(state: IssueState) -> list:
            if state == IssueState.READY:
                return [make_issue_info(1, IssueState.READY)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        states = {1: IssueState.READY}
        install_issue_loader(coordinator, states)

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
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
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
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
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
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

        def emit_side_effect(role, issue, tick_id=0) -> None:
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


class TestRetryBudget:
    """Tests for retry budget and eviction policy."""

    def test_retry_count_increments_on_stale_state(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test retry_count increments when state unchanged, no active session."""
        # Setup: entry with waiting_state, state unchanged, no active session
        entry = {
            "issue_number": 1,
            "collected_state": "claimed",
            "waiting_state": "claimed",
            "retry_count": 0,
            "last_attempted_at": None,
        }

        # Mock issue loader to return unchanged state
        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.CLAIMED,
                labels=["state/claimed"],
                assignees=["manager-bot"],
            )

        # Mock config
        config = MagicMock()
        config.manager_usernames = ["manager-bot"]

        # Mock github
        github = MagicMock()

        # Mock registry with no active session
        registry = MagicMock()
        registry.get_live_sessions_for_issue = MagicMock(return_value=[])

        # Capture events
        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            events.append(message)

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            capture_event,
        )

        # First call: retry_count should increment to 1
        promoted, retained, removed = promote_progressed_entries(
            [entry],
            config,
            github,
            registry=registry,  # Registry exists but no active session
            supervisor_label="supervisor",
            load_issue_func=mock_load_issue,
            max_retry_budget=3,
        )

        assert len(promoted) == 1
        assert promoted[0]["retry_count"] == 1
        assert promoted[0]["last_attempted_at"] is not None

        # Simulate re-dispatch: set waiting_state back
        entry2 = promoted[0]
        entry2["waiting_state"] = "claimed"

        # Second call: retry_count should increment to 2
        promoted2, retained2, removed2 = promote_progressed_entries(
            [entry2],
            config,
            github,
            registry=registry,
            supervisor_label="supervisor",
            load_issue_func=mock_load_issue,
            max_retry_budget=3,
        )

        assert len(promoted2) == 1
        assert promoted2[0]["retry_count"] == 2

    def test_retry_count_resets_on_state_change(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that retry_count resets to 0 when state changes."""
        # Setup: entry with retry_count=2, state changes from claimed to in_progress
        entry = {
            "issue_number": 1,
            "collected_state": "claimed",
            "waiting_state": "claimed",
            "retry_count": 2,
            "last_attempted_at": "2025-01-01T00:00:00+00:00",
        }

        # Mock issue loader to return changed state
        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.IN_PROGRESS,  # State changed!
                labels=["state/in-progress"],
                assignees=["manager-bot"],
            )

        config = MagicMock()
        config.manager_usernames = ["manager-bot"]
        github = MagicMock()

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            events.append(message)

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            capture_event,
        )

        promoted, retained, removed = promote_progressed_entries(
            [entry],
            config,
            github,
            registry=None,
            supervisor_label="supervisor",
            load_issue_func=mock_load_issue,
            max_retry_budget=3,
        )

        assert len(promoted) == 1
        assert promoted[0]["retry_count"] == 0
        assert promoted[0]["last_attempted_at"] is None

    def test_eviction_at_threshold(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that entry is evicted when retry_count >= max_retry_budget."""
        # Setup: entry with retry_count=2, max_retry_budget=3, state unchanged
        entry = {
            "issue_number": 1,
            "collected_state": "claimed",
            "waiting_state": "claimed",
            "retry_count": 2,
            "last_attempted_at": "2025-01-01T00:00:00+00:00",
        }

        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.CLAIMED,  # State unchanged
                labels=["state/claimed"],
                assignees=["manager-bot"],
            )

        config = MagicMock()
        config.manager_usernames = ["manager-bot"]
        github = MagicMock()

        # Mock registry with no active session
        registry = MagicMock()
        registry.get_live_sessions_for_issue = MagicMock(return_value=[])

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            events.append(message)

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            capture_event,
        )

        promoted, retained, removed = promote_progressed_entries(
            [entry],
            config,
            github,
            registry=registry,  # Registry exists but no active session
            supervisor_label="supervisor",
            load_issue_func=mock_load_issue,
            max_retry_budget=3,
        )

        # Entry should be in removed list (retry_count 2 -> 3 >= max_retry_budget 3)
        assert len(promoted) == 0
        assert len(retained) == 0
        assert len(removed) == 1
        assert removed[0]["issue_number"] == 1
        assert removed[0]["retry_count"] == 3

        # Verify eviction event is logged
        assert any("evicted #1" in event for event in events)
        assert any("retry budget exhausted" in event for event in events)

    def test_no_eviction_below_threshold(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that entry is promoted when retry_count < max_retry_budget."""
        # Setup: entry with retry_count=1, max_retry_budget=3, state unchanged
        entry = {
            "issue_number": 1,
            "collected_state": "claimed",
            "waiting_state": "claimed",
            "retry_count": 1,
            "last_attempted_at": "2025-01-01T00:00:00+00:00",
        }

        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.CLAIMED,  # State unchanged
                labels=["state/claimed"],
                assignees=["manager-bot"],
            )

        config = MagicMock()
        config.manager_usernames = ["manager-bot"]
        github = MagicMock()

        # Mock registry with no active session
        registry = MagicMock()
        registry.get_live_sessions_for_issue = MagicMock(return_value=[])

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            events.append(message)

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            capture_event,
        )

        promoted, retained, removed = promote_progressed_entries(
            [entry],
            config,
            github,
            registry=registry,  # Registry exists but no active session
            supervisor_label="supervisor",
            load_issue_func=mock_load_issue,
            max_retry_budget=3,
        )

        # Entry should be in promoted list (retry_count 1 -> 2 < max_retry_budget 3)
        assert len(promoted) == 1
        assert len(retained) == 0
        assert len(removed) == 0
        assert promoted[0]["retry_count"] == 2

    def test_active_session_resets_waiting_without_retry_increment(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that entry stays in retained when active session exists."""
        # Setup: entry with active session, state unchanged
        entry = {
            "issue_number": 1,
            "collected_state": "claimed",
            "waiting_state": "claimed",
            "retry_count": 1,
            "last_attempted_at": "2025-01-01T00:00:00+00:00",
        }

        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.CLAIMED,  # State unchanged
                labels=["state/claimed"],
                assignees=["manager-bot"],
            )

        config = MagicMock()
        config.manager_usernames = ["manager-bot"]
        github = MagicMock()

        # Mock registry with active session
        registry = MagicMock()
        registry.get_live_sessions_for_issue = MagicMock(
            return_value=[MagicMock()]  # Active session exists
        )

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO") -> None:
            events.append(message)

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            capture_event,
        )

        promoted, retained, removed = promote_progressed_entries(
            [entry],
            config,
            github,
            registry=registry,  # Active session exists
            supervisor_label="supervisor",
            load_issue_func=mock_load_issue,
            max_retry_budget=3,
        )

        # Entry should stay in retained (not promoted, retry_count unchanged)
        assert len(promoted) == 0
        assert len(retained) == 1
        assert len(removed) == 0
        assert retained[0]["retry_count"] == 1  # Unchanged
