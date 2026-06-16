"""Tests for named queue maintenance trigger methods."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.global_dispatch_coordinator import QueueEntry


class TestQueueStartupRestore:
    """Tests for _queue_startup_restore trigger."""

    @pytest.mark.asyncio
    async def test_startup_restore_calls_persistence_restore(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Cold-start queue restoration calls persistence restore."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Mock persistence restore
        coordinator._queue_persistence.restore = MagicMock(return_value=None)

        # Ensure queue starts as None (cold start)
        assert coordinator._frozen_queue is None

        # First coordinate() should trigger restore
        await coordinator.coordinate()

        # Verify persistence restore was called
        coordinator._queue_persistence.restore.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_restore_sets_empty_list_on_none(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Startup restore sets empty list when persistence returns None."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Mock persistence to return None
        coordinator._queue_persistence.restore = MagicMock(return_value=None)

        # Ensure queue starts as None
        assert coordinator._frozen_queue is None

        # First coordinate() should trigger restore
        await coordinator.coordinate()

        # Verify queue is empty list (not None)
        assert coordinator._frozen_queue == []


class TestQueueScheduledRefresh:
    """Tests for _queue_scheduled_refresh trigger."""

    @pytest.mark.asyncio
    async def test_scheduled_refresh_fires_at_interval(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Periodic refresh fires at interval_ticks."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Set interval_ticks = 10
        coordinator._config.queue_refresh.enabled = True
        coordinator._config.queue_refresh.interval_ticks = 10

        # Pre-populate queue to avoid queue_exhausted trigger
        coordinator._frozen_queue = [
            QueueEntry(issue_number=999, collected_state="ready")
        ]

        # Mock collection to track calls
        collect_called = []

        async def mock_collect():
            collect_called.append(True)
            return [QueueEntry(issue_number=1, collected_state="ready")]

        coordinator._collect_frozen_queue = mock_collect

        # Mock capacity to prevent dispatch (keeps queue populated)
        coordinator._capacity.get_capacity_status = MagicMock(
            return_value={"remaining": 0, "active_count": 10, "max_capacity": 10}
        )

        # First tick (tick_id=0) - should NOT fire (tick_id > 0 check)
        await coordinator.coordinate(tick_id=0)
        assert len(collect_called) == 0

        # Tick 5 - should NOT fire (not at interval)
        await coordinator.coordinate(tick_id=5)
        assert len(collect_called) == 0

        # Tick 10 - SHOULD fire
        await coordinator.coordinate(tick_id=10)
        assert len(collect_called) == 1

    @pytest.mark.asyncio
    async def test_scheduled_refresh_disabled(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Scheduled refresh does not fire when disabled."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Disable periodic check
        coordinator._config.queue_refresh.enabled = False
        coordinator._config.queue_refresh.interval_ticks = 10

        # Pre-populate queue to avoid queue_exhausted trigger
        coordinator._frozen_queue = [
            QueueEntry(issue_number=999, collected_state="ready")
        ]

        # Mock collection to track calls
        collect_called = []

        async def mock_collect():
            collect_called.append(True)
            return []

        coordinator._collect_frozen_queue = mock_collect

        # Mock capacity to prevent dispatch
        coordinator._capacity.get_capacity_status = MagicMock(
            return_value={"remaining": 0, "active_count": 10, "max_capacity": 10}
        )

        # Tick 10 - should NOT fire (disabled)
        await coordinator.coordinate(tick_id=10)
        assert len(collect_called) == 0


class TestQueueExhaustedRefresh:
    """Tests for _queue_exhausted_refresh trigger."""

    @pytest.mark.asyncio
    async def test_queue_exhausted_triggers_rebuild(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
    ) -> None:
        """Rebuild triggered after dispatch depletes actionable entries."""
        _ = make_issue(1)
        capacity = make_capacity(remaining=10)

        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        install_issue_loader(
            coordinator,
            {
                1: IssueState.READY,
            },
        )

        # Pre-load queue with actionable entry
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready"),
        ]

        # Mock capacity to allow dispatch
        coordinator._capacity.get_capacity_status = MagicMock(
            return_value={"remaining": 10, "active_count": 0, "max_capacity": 10}
        )

        # Mock collection to track rebuild calls
        collect_called = []

        async def mock_collect():
            collect_called.append(True)
            return [QueueEntry(issue_number=2, collected_state="ready")]

        coordinator._collect_frozen_queue = mock_collect

        # Mock dispatch to succeed (this will exhaust the queue)
        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        # Tick: dispatch entry, queue should be exhausted
        await coordinator.coordinate()

        # After dispatch, queue should be exhausted and collection triggered
        assert len(emit_calls) >= 1  # At least one dispatch happened
        assert len(collect_called) >= 1  # Collection was triggered

    @pytest.mark.asyncio
    async def test_queue_exhausted_not_triggered_when_refreshed(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Exhausted refresh NOT triggered when queue was already refreshed."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Set up scheduled refresh to fire
        coordinator._config.queue_refresh.enabled = True
        coordinator._config.queue_refresh.interval_ticks = 10

        # Mock collection
        collect_count = []

        async def mock_collect():
            collect_count.append("collect")
            return [QueueEntry(issue_number=1, collected_state="ready")]

        coordinator._collect_frozen_queue = mock_collect

        # Tick 10 triggers scheduled refresh
        await coordinator.coordinate(tick_id=10)

        # Only one collection (scheduled), not additional exhausted collection
        assert len(collect_count) == 1


class TestQueuePausedBlockedCheck:
    """Tests for _queue_paused_blocked_check trigger."""

    @pytest.mark.asyncio
    async def test_paused_blocked_check_remains_paused(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Paused state maintained when all entries blocked and none qualifiable."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Pre-load queue with all blocked entries
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="blocked"),
            QueueEntry(issue_number=2, collected_state="blocked"),
        ]

        # Set paused state
        coordinator._dispatch_paused = True

        # Mock to indicate no actionable entries and no qualifiable blocked
        coordinator._has_actionable_entries = MagicMock(return_value=False)
        coordinator._has_pending_blocked_entries = MagicMock(return_value=True)
        coordinator._has_qualifiable_blocked_entries = MagicMock(return_value=False)

        await coordinator.coordinate()

        # Should remain paused
        assert coordinator._dispatch_paused is True

    @pytest.mark.asyncio
    async def test_paused_blocked_check_unpauses_when_qualifiable(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Paused cleared when a qualifiable blocked entry exists."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Pre-load queue with all blocked entries
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="blocked"),
            QueueEntry(issue_number=2, collected_state="blocked"),
        ]

        # Set paused state
        coordinator._dispatch_paused = True

        # Mock to indicate no actionable but has qualifiable blocked
        coordinator._has_actionable_entries = MagicMock(return_value=False)
        coordinator._has_pending_blocked_entries = MagicMock(return_value=True)
        coordinator._has_qualifiable_blocked_entries = MagicMock(return_value=True)

        await coordinator.coordinate()

        # Should unpause to let blocked entry through
        assert coordinator._dispatch_paused is False


class TestTriggerLogging:
    """Tests for trigger method behavior."""

    @pytest.mark.asyncio
    async def test_startup_restore_on_cold_start(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Verify startup_restore is called on cold start."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Mock persistence restore
        coordinator._queue_persistence.restore = MagicMock(return_value=None)

        # Ensure queue starts as None
        assert coordinator._frozen_queue is None

        # coordinate() should call _queue_startup_restore
        await coordinator.coordinate(tick_id=0)

        # Verify persistence restore was called
        coordinator._queue_persistence.restore.assert_called_once()

    @pytest.mark.asyncio
    async def test_promote_progressed_called_on_coordinate(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Verify promote_progressed is called during coordinate."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Pre-populate queue
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready")
        ]

        # Mock promote to track calls
        promote_called = []
        original_promote = coordinator._queue_persistence.promote
        coordinator._queue_persistence.promote = lambda: (
            promote_called.append(True),
            original_promote(),
        )[1]

        await coordinator.coordinate(tick_id=0)

        # Verify promote was called
        assert len(promote_called) >= 1

    @pytest.mark.asyncio
    async def test_paused_blocked_check_called_when_paused(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Verify paused_blocked_check is called when dispatch is paused."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        # Set paused state
        coordinator._dispatch_paused = True

        # Pre-populate queue with blocked entries
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="blocked")
        ]

        # Mock methods
        coordinator._has_actionable_entries = lambda: False
        coordinator._has_pending_blocked_entries = lambda: True
        coordinator._has_qualifiable_blocked_entries = lambda: False

        await coordinator.coordinate(tick_id=0)

        # Should remain paused (paused_blocked_check executed)
        assert coordinator._dispatch_paused is True
