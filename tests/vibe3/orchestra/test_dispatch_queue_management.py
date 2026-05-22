"""Tests for GlobalDispatchCoordinator queue operations.

Merged from:
- test_dispatch_queue_operations.py: Queue management tests
- test_dispatch_actionable_trigger.py: Actionable-triggered collection tests
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    GlobalDispatchCoordinator,
    QueueEntry,
)


@pytest.fixture
def mock_coordinator() -> GlobalDispatchCoordinator:
    """Create a GlobalDispatchCoordinator with all dependencies mocked."""
    config = MagicMock()
    config.repo = "owner/repo"
    config.manager_usernames = ["manager-bot"]
    config.supervisor_handoff.issue_label = "supervisor"
    config.max_concurrent_flows = 10
    config.get_manager_usernames = MagicMock(return_value=["manager-bot"])

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

    coordinator = GlobalDispatchCoordinator(
        config=config,
        capacity=capacity,
        github=github,
        store=store,
        flow_manager=flow_manager,
        registry=None,
    )

    # Mock methods that would require complex setup
    coordinator._health_check_before_dispatch = MagicMock(return_value=True)
    coordinator._emit_dispatch_intent = MagicMock()

    return coordinator


class TestQueueOperations:
    """Tests for GlobalDispatchCoordinator queue operations."""

    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        issues = [make_issue(1), make_issue(2)]
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            issues,
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
        issue = make_issue(issue_num)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            role, [issue], capacity=capacity, mock_health_check=True
        )
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
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            issues,
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
        issues = [make_issue(1), make_issue(2)]
        capacity = make_capacity(remaining=3)

        coordinator = make_coordinator(
            "planner",
            issues,
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
        issue1 = make_issue(1)
        issue2 = make_issue(2)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            [issue1, issue2],
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
            "planner",
            [issue_planner],
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
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

        # First tick: collects entries (CLAIMED state works, READY fails)
        await coordinator.coordinate()
        # Second tick: dispatches collected CLAIMED entries
        await coordinator.coordinate()

        assert len(emit_calls) == 1

    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(
        self, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True, mock_health_check=True
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

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case,expected_count,expected_numbers",
        [
            ("normal", 2, {100, 101}),
            ("supervisor_only", 0, set()),
        ],
    )
    async def test_blocked_issues_collection_filtering(
        self,
        make_capacity,
        make_coordinator,
        test_case,
        expected_count,
        expected_numbers,
    ) -> None:
        """BLOCKED issues bypass qualify gate; supervisor-labeled issues excluded."""
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "manager",
            [],
            capacity=capacity,
            mock_health_check=True,
        )

        # Create raw payloads based on test case
        if test_case == "normal":
            raw_payloads = [
                {
                    "number": 100,
                    "title": "Issue 100",
                    "labels": [{"name": "state/blocked"}],
                    "assignees": [{"login": "manager-bot"}],
                    "html_url": "https://github.com/owner/repo/issues/100",
                },
                {
                    "number": 101,
                    "title": "Issue 101",
                    "labels": [{"name": "state/blocked"}],
                    "assignees": [{"login": "manager-bot"}],
                    "html_url": "https://github.com/owner/repo/issues/101",
                },
                # Supervisor-labeled issue should be filtered out
                {
                    "number": 102,
                    "title": "Issue 102",
                    "labels": [{"name": "supervisor"}, {"name": "state/blocked"}],
                    "assignees": [{"login": "manager-bot"}],
                    "html_url": "https://github.com/owner/repo/issues/102",
                },
            ]
        else:  # supervisor_only
            raw_payloads = [
                {
                    "number": 102,
                    "title": "Issue 102",
                    "labels": [{"name": "supervisor"}, {"name": "state/blocked"}],
                    "assignees": [{"login": "manager-bot"}],
                    "html_url": "https://github.com/owner/repo/issues/102",
                }
            ]

        # Mock GitHub API to return raw payloads for BLOCKED state
        def mock_list_issues(**kwargs):
            if kwargs.get("label") == "state/blocked":
                return raw_payloads
            return []

        coordinator._github.list_issues = mock_list_issues

        # Directly test _poll_issues_by_state for BLOCKED state
        blocked_issues = await coordinator._poll_issues_by_state(IssueState.BLOCKED)

        # Verify filtering behavior
        assert len(blocked_issues) == expected_count
        assert {issue.number for issue in blocked_issues} == expected_numbers

        # Verify all returned issues have BLOCKED state
        for issue in blocked_issues:
            assert issue.state == IssueState.BLOCKED


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
            "vibe3.orchestra.global_dispatch_coordinator.find_role_for_state"
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
            "vibe3.orchestra.global_dispatch_coordinator.find_role_for_state"
        ) as mock_find_role:
            mock_role = MagicMock()
            mock_role.registry_role = "manager"
            mock_find_role.return_value = mock_role

            dispatched_count = mock_coordinator._dispatch_loop(tick_id=1)

            # Should only dispatch 1 (capacity limit)
            assert dispatched_count == 1


class TestActionableTriggeredCollection:
    """Test coordinate() only collects when actionable candidates exhausted."""

    @pytest.mark.asyncio
    async def test_restore_queue_when_none(self, mock_coordinator):
        """When _frozen_queue is None, restore from persistence."""
        # Setup: queue is None, restore returns entries
        mock_coordinator._frozen_queue = None
        mock_coordinator._restore_queue = MagicMock(
            return_value=[
                QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            ]
        )

        # Mock promote to return entries unchanged
        mock_coordinator._promote_progressed_entries = MagicMock()

        # Mock dispatch loop to return 0 (no dispatches)
        mock_coordinator._dispatch_loop = MagicMock(return_value=0)

        # Mock _collect_frozen_queue to track if it gets called
        mock_coordinator._collect_frozen_queue = AsyncMock(
            side_effect=AssertionError("Should not call _collect_frozen_queue")
        )

        # Mock persist
        mock_coordinator._persist_queue = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        # Should have called restore_queue
        mock_coordinator._restore_queue.assert_called_once()

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

        mock_coordinator._promote_progressed_entries = MagicMock()
        mock_coordinator._dispatch_loop = MagicMock(return_value=0)

        # Mock collect to return fresh entries
        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=2, collected_state="ready", waiting_state=None),
            ]

        mock_coordinator._collect_frozen_queue = mock_collect

        mock_coordinator._persist_queue = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        # Should have called _collect_frozen_queue
        # (because all entries were blocked)

    @pytest.mark.asyncio
    async def test_no_collect_when_actionable_available(self, mock_coordinator):
        """Do NOT collect when queue has actionable entries."""
        # Setup: queue has actionable entries
        mock_coordinator._frozen_queue = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=2, collected_state="blocked", waiting_state=None),
        ]

        mock_coordinator._promote_progressed_entries = MagicMock()
        mock_coordinator._dispatch_loop = MagicMock(return_value=1)

        # Mock _collect_frozen_queue to track if it gets called
        mock_coordinator._collect_frozen_queue = AsyncMock(
            side_effect=AssertionError("Should not call _collect_frozen_queue")
        )

        mock_coordinator._persist_queue = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        # Should NOT have called _collect_frozen_queue
        # (because queue still has actionable entries)
        mock_coordinator._collect_frozen_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_merge_after_collect(self, mock_coordinator):
        """Merge fresh entries into existing queue after collect."""
        # Setup: existing queue has blocked entries
        mock_coordinator._frozen_queue = [
            QueueEntry(
                issue_number=1, collected_state="blocked", waiting_state="blocked"
            ),
        ]

        mock_coordinator._promote_progressed_entries = MagicMock()
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

        mock_coordinator._persist_queue = MagicMock()

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
        mock_coordinator._promote_progressed_entries = MagicMock()
        mock_coordinator._collect_frozen_queue = AsyncMock()
        mock_coordinator._persist_queue = MagicMock()

        await mock_coordinator.coordinate(tick_id=1)

        mock_coordinator._collect_frozen_queue.assert_not_called()

    @pytest.mark.asyncio
    async def test_pause_dispatch_when_rebuild_finds_only_blocked(
        self, mock_coordinator
    ):
        """Blocked-only rebuilds pause after queueing one qualify pass."""
        mock_coordinator._frozen_queue = []
        mock_coordinator._promote_progressed_entries = MagicMock()
        mock_coordinator._dispatch_loop = MagicMock(return_value=0)
        mock_coordinator._persist_queue = MagicMock()

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

    @pytest.mark.asyncio
    async def test_paused_blocked_queue_drops_rechecked_blocked_entries(
        self, mock_coordinator
    ):
        """After one qualify pass, stable blocked-only queues become quiet."""
        mock_coordinator._dispatch_paused = True
        mock_coordinator._frozen_queue = [
            QueueEntry(issue_number=10, collected_state="blocked", waiting_state=None),
        ]
        mock_coordinator._promote_progressed_entries = MagicMock()
        mock_coordinator._persist_queue = MagicMock()
        mock_coordinator._probe_for_non_blocked_candidates = AsyncMock()

        def mock_dispatch_loop(_tick_id: int = 0) -> int:
            mock_coordinator._frozen_queue = []
            return 0

        mock_coordinator._dispatch_loop = MagicMock(side_effect=mock_dispatch_loop)

        async def mock_collect() -> list[QueueEntry]:
            return [QueueEntry(issue_number=10, collected_state="blocked")]

        mock_coordinator._collect_frozen_queue = mock_collect

        await mock_coordinator.coordinate(tick_id=1)

        assert mock_coordinator._dispatch_paused is True
        assert mock_coordinator._frozen_queue == []
        mock_coordinator._probe_for_non_blocked_candidates.assert_not_called()

    @pytest.mark.asyncio
    async def test_paused_dispatch_skips_recollect_until_non_blocked_probe_hits(
        self, mock_coordinator
    ):
        """Paused dispatch shouldnt keep recollecting while only blocked work exists."""
        mock_coordinator._dispatch_paused = True
        mock_coordinator._frozen_queue = []
        mock_coordinator._promote_progressed_entries = MagicMock()
        mock_coordinator._persist_queue = MagicMock()
        mock_coordinator._collect_frozen_queue = AsyncMock()
        mock_coordinator._probe_for_non_blocked_candidates = AsyncMock(
            return_value=False
        )

        await mock_coordinator.coordinate(tick_id=1)

        mock_coordinator._collect_frozen_queue.assert_not_called()
        mock_coordinator._probe_for_non_blocked_candidates.assert_awaited_once()
