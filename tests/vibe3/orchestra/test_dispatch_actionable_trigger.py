"""Tests for GlobalDispatchCoordinator actionable-triggered collection.

Merged from actionable trigger tests and dispatch pause logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.queue_entry import QueueEntry
from vibe3.orchestra.global_dispatch_coordinator import GlobalDispatchCoordinator


@pytest.fixture
@patch(
    "vibe3.domain.dispatch_coordinator.get_manager_usernames",
    return_value=["manager-bot"],
)
def mock_coordinator(mock_get_manager_usernames) -> GlobalDispatchCoordinator:
    """Create a GlobalDispatchCoordinator with all dependencies mocked."""
    config = MagicMock()
    config.repo = "owner/repo"
    config.manager_usernames = ["manager-bot"]
    config.supervisor_handoff.issue_label = "supervisor"
    config.queue_refresh.enabled = True
    config.queue_refresh.interval_ticks = 10
    config.max_concurrent_flows = 10

    capacity = MagicMock()
    capacity.get_capacity_status = MagicMock(
        return_value={
            "remaining": 10,
            "active_count": 0,
            "max_capacity": 10,
        }
    )

    github = MagicMock()
    store = MagicMock()
    store.db_path = ":memory:"
    store.get_flow_state = MagicMock(return_value=None)
    store.get_flows_by_issue = MagicMock(return_value=[])

    flow_manager = MagicMock()
    flow_manager.get_flow_for_issue = MagicMock(return_value=None)

    flow_blocker = MagicMock()
    queue_persistence = MagicMock()
    queue_persistence.frozen_queue = None
    queue_persistence.restore.return_value = None
    queue_persistence.promote.return_value = False
    queue_persistence.get_queued_issue_numbers.return_value = set()

    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=capacity,
        github=github,
        store=store,
        flow_manager=flow_manager,
        registry=None,
        flow_blocker=flow_blocker,
        queue_persistence=queue_persistence,
        issue_loader=lambda issue_number: None,
        flow_context_resolver=lambda issue_number: (f"task/issue-{issue_number}", None),
        queue_selector=lambda *args, **kwargs: [],
        check_service=MagicMock(),
    )

    # Mock methods that would require complex setup
    coordinator._check_dispatch_health = MagicMock(return_value=True)
    coordinator._emit_dispatch_intent = MagicMock()

    return coordinator


class TestMergeQueue:
    """Test _merge_queue deduplication logic."""

    def test_merge_keeps_existing_entries(self, mock_coordinator):
        """When same issue_number exists in both, keep existing entry."""
        # Create existing queue entries
        existing = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(
                issue_number=2, collected_state="blocked", waiting_state="blocked"
            ),
        ]

        # Create fresh queue entries (issue 1 and 3)
        fresh = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=3, collected_state="claimed", waiting_state=None),
        ]

        merged = mock_coordinator._merge_queue(existing, fresh)

        # Should have 3 entries: 1 (existing), 2, 3
        assert len(merged) == 3
        assert merged[0].issue_number == 1
        assert merged[0].waiting_state is None  # From existing
        assert merged[1].issue_number == 2
        assert merged[2].issue_number == 3

    def test_merge_preserves_waiting_state(self, mock_coordinator):
        """Existing entry's waiting_state should not be overwritten."""
        existing = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state="ready"),
        ]

        fresh = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
        ]

        merged = mock_coordinator._merge_queue(existing, fresh)

        # Should keep existing entry's waiting_state
        assert merged[0].waiting_state == "ready"

    def test_merge_empty_existing(self, mock_coordinator):
        """When existing is empty, return fresh entries."""
        existing = []
        fresh = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=2, collected_state="blocked", waiting_state=None),
        ]

        merged = mock_coordinator._merge_queue(existing, fresh)

        assert len(merged) == 2
        assert merged[0].issue_number == 1
        assert merged[1].issue_number == 2

    def test_merge_empty_fresh(self, mock_coordinator):
        """When fresh is empty, return existing entries."""
        existing = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
        ]
        fresh = []

        merged = mock_coordinator._merge_queue(existing, fresh)

        assert len(merged) == 1
        assert merged[0].issue_number == 1


class TestDispatchLoop:
    """Test _dispatch_loop extraction."""

    @pytest.mark.slow
    def test_dispatch_loop_returns_count(self, mock_coordinator):
        """_dispatch_loop should return dispatched_count."""
        # Setup: create queue with actionable entries
        mock_coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=2, collected_state="blocked", waiting_state=None),
        ]

        # Mock issue loader: issue 1 is READY, issue 2 is BLOCKED
        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            if issue_number == 1:
                return IssueInfo(
                    number=1,
                    title="Issue 1",
                    state=IssueState.READY,
                    labels=["state/ready"],
                    assignees=["manager-bot"],
                )
            elif issue_number == 2:
                return IssueInfo(
                    number=2,
                    title="Issue 2",
                    state=IssueState.BLOCKED,
                    labels=["state/blocked"],
                    assignees=["manager-bot"],
                )
            return None

        mock_coordinator._load_issue = mock_load_issue

        # Mock role finding
        with patch(
            "vibe3.domain.dispatch_coordinator.find_role_for_state"
        ) as mock_find_role:
            mock_role = MagicMock()
            mock_role.registry_role = "manager"
            mock_find_role.return_value = mock_role

            # Mock qualify_gate for BLOCKED issue (returns None = still blocked)
            mock_coordinator._qualify_gate.qualify_blocked_issue = MagicMock(
                return_value=None
            )

            dispatched_count = mock_coordinator._dispatch_loop(tick_id=1)

            # Issue 1 should be dispatched, issue 2 skipped (BLOCKED)
            assert dispatched_count == 1

    @pytest.mark.slow
    def test_dispatch_loop_respects_capacity(self, mock_coordinator):
        """_dispatch_loop should stop when capacity is full."""
        # Setup: capacity = 1 slot
        mock_coordinator._capacity.get_capacity_status = MagicMock(
            return_value={
                "remaining": 1,
                "active_count": 0,
                "max_capacity": 10,
            }
        )

        # Queue has 2 actionable entries
        mock_coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=2, collected_state="ready", waiting_state=None),
        ]

        def mock_load_issue(issue_number: int) -> IssueInfo | None:
            return IssueInfo(
                number=issue_number,
                title=f"Issue {issue_number}",
                state=IssueState.READY,
                labels=["state/ready"],
                assignees=["manager-bot"],
            )

        mock_coordinator._load_issue = mock_load_issue

        with patch(
            "vibe3.domain.dispatch_coordinator.find_role_for_state"
        ) as mock_find_role:
            mock_role = MagicMock()
            mock_role.registry_role = "manager"
            mock_find_role.return_value = mock_role

            dispatched_count = mock_coordinator._dispatch_loop(tick_id=1)

            # Should only dispatch 1 (capacity limit)
            assert dispatched_count == 1

    def test_dispatch_loop_rechecks_qualify_gate_for_ready_issue(
        self, mock_coordinator
    ):
        """READY issue must pass qualify gate again immediately before dispatch."""
        mock_coordinator._frozen_queue = [
            QueueEntry(issue_number=42, collected_state="ready", waiting_state=None),
        ]

        mock_coordinator._load_issue = lambda issue_number: IssueInfo(
            number=issue_number,
            title=f"Issue {issue_number}",
            state=IssueState.READY,
            labels=["state/ready"],
            assignees=["manager-bot"],
        )
        mock_coordinator._flow_context = MagicMock(
            return_value=(
                "task/issue-42",
                {"branch": "task/issue-42", "flow_status": "active"},
            )
        )
        mock_coordinator._store.get_flow_state.return_value = {
            "branch": "task/issue-42",
            "flow_status": "active",
        }
        mock_coordinator._qualify_gate.run_qualify_gate = MagicMock(return_value=None)

        with patch(
            "vibe3.domain.dispatch_coordinator.find_role_for_state"
        ) as mock_find_role:
            mock_role = MagicMock()
            mock_role.registry_role = "manager"
            mock_find_role.return_value = mock_role

            dispatched_count = mock_coordinator._dispatch_loop(tick_id=1)

        assert dispatched_count == 0
        mock_coordinator._qualify_gate.run_qualify_gate.assert_called_once()
        mock_coordinator._emit_dispatch_intent.assert_not_called()


class TestActionableTriggeredCollection:
    """Test coordinate() only collects when actionable candidates exhausted."""

    @pytest.mark.asyncio
    async def test_restore_queue_when_none(self, mock_coordinator):
        """When _frozen_queue is None, restore from persistence."""
        # Setup: queue is None, restore returns entries
        mock_coordinator._frozen_queue = None
        mock_coordinator._queue_persistence.restore = MagicMock(
            return_value=[
                QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            ]
        )

        # Mock promote to return entries unchanged
        mock_coordinator._queue_persistence.promote = MagicMock(return_value=False)

        # Mock _queue_resort_existing (part of coordinate flow)
        mock_coordinator._queue_resort_existing = MagicMock()

        # Mock dispatch loop to return 0 (no dispatches)
        mock_coordinator._dispatch_loop = MagicMock(return_value=0)

        # Mock _collect_frozen_queue to track if it gets called
        mock_coordinator._collect_frozen_queue = AsyncMock(
            side_effect=AssertionError("Should not call _collect_frozen_queue")
        )

        # Mock persist
        mock_coordinator._queue_persistence.persist = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        # Should have called restore_queue
        mock_coordinator._queue_persistence.restore.assert_called_once()

        # Should NOT have called _collect_frozen_queue
        # (since restored queue has actionable entries)
        mock_coordinator._collect_frozen_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_collect_when_actionable_exhausted(self, mock_coordinator):
        """Collect fresh queue when all entries are blocked."""
        # Setup: queue has only blocked entries
        mock_coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="blocked", waiting_state=None),
        ]

        mock_coordinator._queue_persistence.promote = MagicMock(return_value=False)
        mock_coordinator._dispatch_loop = MagicMock(return_value=0)

        # Mock collect to return fresh entries
        mock_coordinator._collect_frozen_queue = AsyncMock(
            return_value=[
                QueueEntry(issue_number=2, collected_state="ready", waiting_state=None),
            ]
        )

        mock_coordinator._queue_persistence.persist = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        # Should have called _collect_frozen_queue
        # (because all entries were blocked)
        mock_coordinator._collect_frozen_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_collect_when_actionable_available(self, mock_coordinator):
        """Do NOT collect when queue has actionable entries."""
        # Setup: queue has actionable entries
        mock_coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=2, collected_state="blocked", waiting_state=None),
        ]

        mock_coordinator._queue_persistence.promote = MagicMock(return_value=False)

        # Mock _queue_resort_existing (part of coordinate flow)
        mock_coordinator._queue_resort_existing = MagicMock()

        mock_coordinator._dispatch_loop = MagicMock(return_value=1)

        # Mock _collect_frozen_queue to track if it gets called
        mock_coordinator._collect_frozen_queue = AsyncMock(
            side_effect=AssertionError("Should not call _collect_frozen_queue")
        )

        mock_coordinator._queue_persistence.persist = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        # Should NOT have called _collect_frozen_queue
        # (because queue still has actionable entries)
        mock_coordinator._collect_frozen_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_periodic_check_tick_refreshes_queue_when_actionable_available(
        self, mock_coordinator
    ):
        """Periodic check ticks refresh queue before exhaustion."""
        mock_coordinator._config.queue_refresh.enabled = True
        mock_coordinator._config.queue_refresh.interval_ticks = 10
        mock_coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=2, collected_state="ready", waiting_state=None),
        ]

        mock_coordinator._queue_persistence.promote = MagicMock(return_value=False)
        mock_coordinator._dispatch_loop = MagicMock(return_value=0)
        mock_coordinator._collect_frozen_queue = AsyncMock(
            return_value=[
                QueueEntry(issue_number=2, collected_state="ready"),
                QueueEntry(issue_number=1, collected_state="ready"),
                QueueEntry(issue_number=3, collected_state="ready"),
            ]
        )
        mock_coordinator._queue_persistence.persist = MagicMock()

        await mock_coordinator.coordinate(tick_id=10)

        mock_coordinator._collect_frozen_queue.assert_called_once()
        assert [entry.issue_number for entry in mock_coordinator._frozen_queue] == [
            2,
            1,
            3,
        ]

    @pytest.mark.asyncio
    async def test_merge_after_collect(self, mock_coordinator):
        """Merge fresh entries into existing queue after collect."""
        # Setup: existing queue has blocked entries
        mock_coordinator._frozen_queue = [
            QueueEntry(
                issue_number=1, collected_state="blocked", waiting_state="blocked"
            ),
        ]

        mock_coordinator._queue_persistence.promote = MagicMock(return_value=False)

        # Mock _queue_resort_existing (part of coordinate flow)
        mock_coordinator._queue_resort_existing = MagicMock()

        mock_coordinator._dispatch_loop = MagicMock(return_value=0)

        # Mock collect to return fresh entries (including new issue 2)
        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(
                    issue_number=1, collected_state="blocked", waiting_state=None
                ),
                QueueEntry(issue_number=2, collected_state="ready", waiting_state=None),
            ]

        mock_coordinator._collect_frozen_queue = mock_collect

        mock_coordinator._queue_persistence.persist = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        # After coordinate, queue should be merged
        # Issue 1 should be from existing (waiting_state = "blocked")
        # Issue 2 should be from fresh
        assert len(mock_coordinator._frozen_queue) == 2
        assert mock_coordinator._frozen_queue[0].issue_number == 1
        assert mock_coordinator._frozen_queue[0].waiting_state == "blocked"
        assert mock_coordinator._frozen_queue[1].issue_number == 2
        assert mock_coordinator._frozen_queue[1].waiting_state is None

    @pytest.mark.asyncio
    async def test_no_collect_when_capacity_full_and_only_waiting_entries(
        self, mock_coordinator
    ):
        """Capacity-full ticks should not recollect just because actionable is empty."""
        mock_coordinator._frozen_queue = [
            QueueEntry(
                issue_number=1,
                collected_state="claimed",
                waiting_state="claimed",
            ),
        ]
        mock_coordinator._capacity.get_capacity_status = MagicMock(
            return_value={
                "remaining": 0,
                "active_count": 1,
                "max_capacity": 1,
            }
        )
        mock_coordinator._queue_persistence.promote = MagicMock(return_value=False)
        mock_coordinator._collect_frozen_queue = AsyncMock()
        mock_coordinator._queue_persistence.persist = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        mock_coordinator._collect_frozen_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_dispatch_when_rebuild_finds_only_blocked(
        self, mock_coordinator
    ):
        """Blocked-only rebuilds pause after queueing one qualify pass."""
        mock_coordinator._frozen_queue = []
        mock_coordinator._queue_persistence.promote = MagicMock(return_value=False)
        mock_coordinator._dispatch_loop = MagicMock(return_value=0)
        mock_coordinator._queue_persistence.persist = MagicMock()

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=10, collected_state="blocked"),
                QueueEntry(issue_number=11, collected_state="blocked"),
            ]

        mock_coordinator._collect_frozen_queue = mock_collect

        await mock_coordinator.coordinate(tick_id=1)

        assert mock_coordinator._dispatch_paused is True
        assert [entry.issue_number for entry in mock_coordinator._frozen_queue] == [
            10,
            11,
        ]
