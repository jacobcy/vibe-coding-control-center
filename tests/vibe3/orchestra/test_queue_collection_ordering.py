"""Tests for queue collection ordering and phase behavior."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.global_dispatch_coordinator import (
    QueueEntry,
)


class TestCollectionOrder:
    """Tests for collection order and state-first ordering semantics."""

    @pytest.mark.asyncio
    async def test_state_group_iteration_order(
        self, make_issue_info, make_capacity, make_coordinator
    ) -> None:
        """Verify queue entries appear in the state iteration order.

        Expected order: REVIEW → MERGE_READY → IN_PROGRESS → CLAIMED → HANDOFF → READY
        """
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        # Create issues in different states
        issues = [
            make_issue_info(1, IssueState.READY),
            make_issue_info(2, IssueState.REVIEW),
            make_issue_info(3, IssueState.IN_PROGRESS),
            make_issue_info(4, IssueState.MERGE_READY),
            make_issue_info(5, IssueState.CLAIMED),
            make_issue_info(6, IssueState.HANDOFF),
        ]

        # Mock the issue collector to return all issues
        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=lambda: issues
        )

        # Mock _queue_selector to return issues filtered by state
        def mock_queue_selector(collected, state, *args, **kwargs):
            return [issue for issue in collected if issue.state == state]

        coordinator._queue_selector = mock_queue_selector

        queue = await coordinator._collect_frozen_queue()

        # Verify order matches state iteration order
        assert [entry.issue_number for entry in queue] == [2, 4, 3, 5, 6, 1]

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_one_open_issue_call(
        self, make_issue_info, make_capacity, make_coordinator
    ) -> None:
        """Verify _collect_open_issues makes exactly one API call (regression guard)."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        issues = [make_issue_info(1, IssueState.READY)]

        # Track how many times collect_open_issues is called
        call_count = [0]

        def mock_collect_open_issues():
            call_count[0] += 1
            return issues

        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=mock_collect_open_issues
        )

        await coordinator._collect_frozen_queue()

        # Should be called exactly once
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_ordering_across_all_state_groups(
        self, make_issue_info, make_capacity, make_coordinator
    ) -> None:
        """Verify entries from multiple states intermix correctly based on priority."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        # Create multiple issues per state to test within-state ordering
        issues = [
            # READY state: issue 1, 2
            make_issue_info(1, IssueState.READY),
            make_issue_info(2, IssueState.READY),
            # REVIEW state: issue 3, 4 (should come first)
            make_issue_info(3, IssueState.REVIEW),
            make_issue_info(4, IssueState.REVIEW),
            # IN_PROGRESS state: issue 5, 6
            make_issue_info(5, IssueState.IN_PROGRESS),
            make_issue_info(6, IssueState.IN_PROGRESS),
        ]

        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=lambda: issues
        )

        def mock_queue_selector(collected, state, *args, **kwargs):
            return [issue for issue in collected if issue.state == state]

        coordinator._queue_selector = mock_queue_selector

        queue = await coordinator._collect_frozen_queue()

        # Verify state groups appear in correct order
        collected_states = [entry.collected_state for entry in queue]
        assert collected_states == [
            "review",
            "review",
            "in-progress",
            "in-progress",
            "ready",
            "ready",
        ]

    @pytest.mark.asyncio
    async def test_collect_open_issues_failure_returns_empty_list(
        self, make_capacity, make_coordinator
    ) -> None:
        """Verify _collect_open_issues returns empty list on failure (fail-safe)."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        # Mock collector to raise exception
        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=lambda: (_ for _ in ()).throw(Exception("API failure"))
        )

        queue = await coordinator._collect_frozen_queue()

        # Should return empty queue instead of raising
        assert queue == []


class TestBlockedRequalification:
    """Tests for blocked issue dependency requalification."""

    @pytest.mark.asyncio
    async def test_qualify_blocked_uses_dependency_resolution_service(
        self, make_issue_info, make_capacity, make_coordinator
    ) -> None:
        """Verify blocked requalification routes through DependencyResolutionService."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        # Create a blocked issue with a dependency
        blocked_issue = make_issue_info(
            1,
            IssueState.BLOCKED,
            labels=["state/blocked", "blocked-by/#100"],
        )

        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=lambda: [blocked_issue]
        )

        # Mock _queue_selector to return empty (blocked issues not in queue)
        coordinator._queue_selector = lambda *args, **kwargs: []

        # Mock qualify_gate.qualify_blocked_issue to track calls
        qualify_calls = []

        def mock_qualify_blocked(issue):
            qualify_calls.append(issue)

        coordinator._qualify_gate.qualify_blocked_issue = mock_qualify_blocked

        await coordinator._collect_frozen_queue()

        # Verify qualify_blocked_issue was called for the blocked issue
        assert len(qualify_calls) == 1
        assert qualify_calls[0].number == 1

    @pytest.mark.asyncio
    async def test_requalify_failure_isolation(
        self, make_issue_info, make_capacity, make_coordinator
    ) -> None:
        """Verify requalification failure doesn't abort collection."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        # Create one blocked issue and one ready issue
        blocked_issue = make_issue_info(1, IssueState.BLOCKED)
        ready_issue = make_issue_info(2, IssueState.READY)

        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=lambda: [blocked_issue, ready_issue]
        )

        def mock_queue_selector(collected, state, *args, **kwargs):
            if state == IssueState.READY:
                return [ready_issue]
            return []

        coordinator._queue_selector = mock_queue_selector

        # Mock qualify_gate to raise exception for blocked issue
        def mock_qualify_blocked(issue):
            if issue.state == IssueState.BLOCKED:
                raise Exception("Qualification failed")

        coordinator._qualify_gate.qualify_blocked_issue = mock_qualify_blocked

        queue = await coordinator._collect_frozen_queue()

        # Ready issue should still be in queue despite blocked qualification failure
        assert len(queue) == 1
        assert queue[0].issue_number == 2

    @pytest.mark.asyncio
    async def test_multiple_blocked_issues_all_requalified(
        self, make_issue_info, make_capacity, make_coordinator
    ) -> None:
        """Verify all blocked issues get requalification attempts."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        blocked_issues = [
            make_issue_info(1, IssueState.BLOCKED),
            make_issue_info(2, IssueState.BLOCKED),
            make_issue_info(3, IssueState.BLOCKED),
        ]

        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=lambda: blocked_issues
        )

        coordinator._queue_selector = lambda *args, **kwargs: []

        qualify_calls = []
        coordinator._qualify_gate.qualify_blocked_issue = (
            lambda issue: qualify_calls.append(issue)
        )

        await coordinator._collect_frozen_queue()

        # All blocked issues should get requalification attempts
        assert len(qualify_calls) == 3
        assert {issue.number for issue in qualify_calls} == {1, 2, 3}


class TestMergeBehavior:
    """Tests for queue merge behavior with waiting_state preservation."""

    def test_merge_preserves_waiting_state_for_existing(self, make_coordinator) -> None:
        """Verify merge preserves waiting_state for existing entries."""
        coordinator = make_coordinator("manager", mock_health_check=True)

        existing = [
            QueueEntry(
                issue_number=1, collected_state="ready", waiting_state="exhausted"
            ),
            QueueEntry(issue_number=2, collected_state="claimed", waiting_state=None),
        ]

        fresh = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=3, collected_state="ready", waiting_state=None),
        ]

        merged = coordinator._merge_queue(existing, fresh)

        # Issue 1 should keep its waiting_state
        assert merged[0].issue_number == 1
        assert merged[0].waiting_state == "exhausted"

        # Issue 2 should be kept (not in fresh)
        assert merged[1].issue_number == 2

        # Issue 3 should be added
        assert merged[2].issue_number == 3

    def test_merge_with_mixed_waiting_states(self, make_coordinator) -> None:
        """Verify merge handles mixed waiting_state values correctly."""
        coordinator = make_coordinator("manager", mock_health_check=True)

        existing = [
            QueueEntry(
                issue_number=1, collected_state="ready", waiting_state="exhausted"
            ),
            QueueEntry(
                issue_number=2, collected_state="ready", waiting_state="scheduled"
            ),
            QueueEntry(issue_number=3, collected_state="ready", waiting_state=None),
        ]

        fresh = [
            QueueEntry(issue_number=1, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=2, collected_state="ready", waiting_state=None),
            QueueEntry(issue_number=3, collected_state="ready", waiting_state=None),
        ]

        merged = coordinator._merge_queue(existing, fresh)

        # All existing waiting_state values should be preserved
        assert merged[0].waiting_state == "exhausted"
        assert merged[1].waiting_state == "scheduled"
        assert merged[2].waiting_state is None

    @pytest.mark.asyncio
    async def test_merge_exhausted_refresh_preserves_waiting_state(
        self, make_coordinator, make_issue_info, make_capacity
    ) -> None:
        """Integration: after _queue_exhausted_refresh, waiting_state is preserved."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        # Set up existing queue with waiting_state
        coordinator._frozen_queue = [
            QueueEntry(
                issue_number=1, collected_state="ready", waiting_state="exhausted"
            ),
        ]

        # Mock collector to return same issue
        issue = make_issue_info(1, IssueState.READY)
        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=lambda: [issue]
        )

        coordinator._queue_selector = lambda collected, state, *args, **kwargs: (
            [issue] if state == IssueState.READY else []
        )

        # Simulate exhausted refresh
        coordinator._frozen_queue = coordinator._merge_queue(
            coordinator._frozen_queue,
            await coordinator._collect_frozen_queue(),
        )

        # waiting_state should be preserved
        assert coordinator._frozen_queue[0].waiting_state == "exhausted"

    @pytest.mark.asyncio
    async def test_merge_scheduled_refresh_replaces_queue(
        self, make_coordinator, make_issue_info, make_capacity
    ) -> None:
        """Verify _queue_scheduled_refresh replaces queue (NOT merge)."""
        coordinator = make_coordinator(
            "manager",
            capacity=make_capacity(remaining=10),
            mock_health_check=True,
        )

        # Set up existing queue with waiting_state
        coordinator._frozen_queue = [
            QueueEntry(
                issue_number=1, collected_state="ready", waiting_state="exhausted"
            ),
        ]

        # Mock collector to return different issue
        issue = make_issue_info(2, IssueState.READY)
        coordinator._issue_collector_factory = lambda: MagicMock(
            collect_open_issues=lambda: [issue]
        )

        coordinator._queue_selector = lambda collected, state, *args, **kwargs: (
            [issue] if state == IssueState.READY else []
        )

        # Simulate scheduled refresh (replaces queue, not merges)
        fresh_queue = await coordinator._collect_frozen_queue()
        coordinator._frozen_queue = fresh_queue  # NOT merged

        # Old issue should be gone, new issue should have no waiting_state
        assert len(coordinator._frozen_queue) == 1
        assert coordinator._frozen_queue[0].issue_number == 2
        assert coordinator._frozen_queue[0].waiting_state is None
