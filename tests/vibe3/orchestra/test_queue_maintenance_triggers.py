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

        coordinator._queue_persistence.restore = MagicMock(return_value=None)

        assert coordinator._frozen_queue is None

        await coordinator.coordinate()

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

        coordinator._queue_persistence.restore = MagicMock(return_value=None)

        assert coordinator._frozen_queue is None

        await coordinator.coordinate()

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

        coordinator._config.queue_refresh.enabled = True
        coordinator._config.queue_refresh.interval_ticks = 10

        coordinator._frozen_queue = [
            QueueEntry(issue_number=999, collected_state="ready")
        ]

        collect_called = []

        async def mock_collect():
            collect_called.append(True)
            return [QueueEntry(issue_number=1, collected_state="ready")]

        coordinator._collect_frozen_queue = mock_collect

        coordinator._capacity.get_capacity_status = MagicMock(
            return_value={"remaining": 0, "active_count": 10, "max_capacity": 10}
        )

        await coordinator.coordinate(tick_id=0)
        assert len(collect_called) == 0

        await coordinator.coordinate(tick_id=5)
        assert len(collect_called) == 0

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

        coordinator._config.queue_refresh.enabled = False
        coordinator._config.queue_refresh.interval_ticks = 10

        coordinator._frozen_queue = [
            QueueEntry(issue_number=999, collected_state="ready")
        ]

        collect_called = []

        async def mock_collect():
            collect_called.append(True)
            return []

        coordinator._collect_frozen_queue = mock_collect

        coordinator._capacity.get_capacity_status = MagicMock(
            return_value={"remaining": 0, "active_count": 10, "max_capacity": 10}
        )

        await coordinator.coordinate(tick_id=10)
        assert len(collect_called) == 0

    @pytest.mark.asyncio
    async def test_scheduled_refresh_preserves_paused_when_nothing_dispatchable(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        coordinator._config.queue_refresh.enabled = True
        coordinator._config.queue_refresh.interval_ticks = 10
        coordinator._dispatch_paused = True
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state="ready"),
        ]

        async def mock_collect():
            return [QueueEntry(issue_number=2, collected_state="handoff")]

        coordinator._collect_frozen_queue = mock_collect
        coordinator._has_dispatchable_entries = lambda _entries: False
        coordinator._has_actionable_entries = MagicMock(return_value=False)
        await coordinator.coordinate(tick_id=10)
        assert coordinator.is_dispatch_paused() is True

    @pytest.mark.asyncio
    async def test_scheduled_refresh_then_preflight_fail_repauses(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Regression: scheduled_refresh weak check flips paused=False, then
        _dispatch_loop preflight removes the entry (dispatched_count=0).
        exhausted_refresh re-verification must re-pause instead of leaving
        paused=False, which would reset the exhausted counter and prevent
        server auto-stop.
        """
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        coordinator._config.queue_refresh.enabled = True
        coordinator._config.queue_refresh.interval_ticks = 10
        coordinator._dispatch_paused = True
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready"),
        ]

        async def mock_collect():
            return [QueueEntry(issue_number=1, collected_state="ready")]

        coordinator._collect_frozen_queue = mock_collect

        # Weak check passes during scheduled_refresh (entry present), then
        # fails during exhausted_refresh re-verification (entry popped by
        # _dispatch_loop since _load_issue returns None by default).
        weak_check_results = [True, False]
        coordinator._has_dispatchable_entries = lambda _entries: (
            weak_check_results.pop(0)
        )
        coordinator._has_actionable_entries = MagicMock(return_value=False)

        await coordinator.coordinate(tick_id=10)

        assert coordinator.is_dispatch_paused() is True


class TestQueueExhaustedRefresh:
    """Tests for _queue_exhausted_refresh trigger."""

    @pytest.mark.asyncio
    @pytest.mark.slow
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

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready"),
        ]

        coordinator._capacity.get_capacity_status = MagicMock(
            return_value={"remaining": 10, "active_count": 0, "max_capacity": 10}
        )

        collect_called = []

        async def mock_collect():
            collect_called.append(True)
            return [QueueEntry(issue_number=2, collected_state="ready")]

        coordinator._collect_frozen_queue = mock_collect

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) >= 1
        assert len(collect_called) >= 1

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

        coordinator._config.queue_refresh.enabled = True
        coordinator._config.queue_refresh.interval_ticks = 10

        collect_count = []

        async def mock_collect():
            collect_count.append("collect")
            return [QueueEntry(issue_number=1, collected_state="ready")]

        coordinator._collect_frozen_queue = mock_collect

        await coordinator.coordinate(tick_id=10)

        assert len(collect_count) == 1

    @pytest.mark.asyncio
    async def test_exhausted_refresh_stays_paused_when_fresh_entries_not_dispatchable(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """Recollection should not reset exhaustion without dispatchable work."""
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )
        coordinator._dispatch_paused = True
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state="ready"),
        ]

        async def mock_collect():
            return [QueueEntry(issue_number=2, collected_state="handoff")]

        coordinator._collect_frozen_queue = mock_collect
        coordinator._has_dispatchable_entries = lambda _entries: False

        await coordinator.coordinate(tick_id=6)

        assert coordinator.is_dispatch_paused() is True

    @pytest.mark.asyncio
    async def test_exhausted_refresh_respects_qualifiable_blocked_exception(
        self,
        make_capacity,
        make_coordinator,
    ) -> None:
        """When unpaused_for_qualifiable_blocked=True, the re-verification
        block must NOT force-pause — respects the "keep unpaused to observe
        remote state" exception, mirroring the need_collect branch.
        """
        capacity = make_capacity(remaining=2)
        coordinator = make_coordinator(
            "planner", capacity=capacity, with_branches=True, mock_health_check=True
        )

        coordinator._config.queue_refresh.enabled = True
        coordinator._config.queue_refresh.interval_ticks = 10
        coordinator._dispatch_paused = True
        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="blocked"),
        ]

        async def mock_collect():
            return [QueueEntry(issue_number=1, collected_state="blocked")]

        coordinator._collect_frozen_queue = mock_collect
        # Weak check returns False so scheduled_refresh keeps paused=True,
        # letting paused_blocked_check produce unpaused_for_qualifiable_blocked.
        coordinator._has_dispatchable_entries = lambda _entries: False
        coordinator._has_actionable_entries = MagicMock(return_value=False)
        coordinator._has_pending_blocked_entries = MagicMock(return_value=True)
        coordinator._has_qualifiable_blocked_entries = MagicMock(return_value=True)

        await coordinator.coordinate(tick_id=10)

        # Stays unpaused: qualifiable blocked exception overrides re-verification.
        assert coordinator.is_dispatch_paused() is False


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

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="blocked"),
            QueueEntry(issue_number=2, collected_state="blocked"),
        ]

        coordinator._dispatch_paused = True

        coordinator._has_actionable_entries = MagicMock(return_value=False)
        coordinator._has_pending_blocked_entries = MagicMock(return_value=True)
        coordinator._has_qualifiable_blocked_entries = MagicMock(return_value=False)

        await coordinator.coordinate()

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

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="blocked"),
            QueueEntry(issue_number=2, collected_state="blocked"),
        ]

        coordinator._dispatch_paused = True

        coordinator._has_actionable_entries = MagicMock(return_value=False)
        coordinator._has_pending_blocked_entries = MagicMock(return_value=True)
        coordinator._has_qualifiable_blocked_entries = MagicMock(return_value=True)

        await coordinator.coordinate()

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

        coordinator._queue_persistence.restore = MagicMock(return_value=None)

        assert coordinator._frozen_queue is None

        await coordinator.coordinate(tick_id=0)

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

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready")
        ]

        promote_called = []
        original_promote = coordinator._queue_persistence.promote
        coordinator._queue_persistence.promote = lambda: (
            promote_called.append(True),
            original_promote(),
        )[1]

        await coordinator.coordinate(tick_id=0)

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

        coordinator._dispatch_paused = True

        coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="blocked")
        ]

        coordinator._has_actionable_entries = lambda: False
        coordinator._has_pending_blocked_entries = lambda: True
        coordinator._has_qualifiable_blocked_entries = lambda: False

        await coordinator.coordinate(tick_id=0)

        assert coordinator._dispatch_paused is True
