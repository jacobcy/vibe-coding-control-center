"""Tests for terminal state handling in frozen queue operations.

Regression tests for #2765: terminal states (blocked/done) should be removed
from the queue instead of promoted to front.
"""

from __future__ import annotations

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import QueueEntry


class TestPromoteProgressedEntriesTerminalStates:
    """Tests that promote_progressed_entries removes terminal states."""

    def _make_issue(
        self, number: int, state: IssueState, labels: list[str] | None = None
    ) -> IssueInfo:
        return IssueInfo(
            number=number,
            title=f"Issue {number}",
            state=state,
            labels=labels or [state.to_label()],
            assignees=["manager-bot"],
        )

    def test_blocked_state_removed_not_promoted(self) -> None:
        """Issues transitioning to blocked should be removed, not promoted."""
        from unittest.mock import MagicMock

        from vibe3.models.orchestra_config import OrchestraConfig
        from vibe3.orchestra.queue_operations import promote_progressed_entries

        config = OrchestraConfig(repo="owner/repo")
        config.supervisor_handoff.issue_label = "supervisor"

        # Entry was waiting for in-progress state, but issue is now blocked
        entry = QueueEntry(
            issue_number=100,
            collected_state="in-progress",
            waiting_state="in-progress",
        )

        issue = self._make_issue(100, IssueState.BLOCKED)
        issue_loader = lambda n: issue  # noqa: E731

        promoted, retained, removed = promote_progressed_entries(
            frozen_queue=[entry],
            config=config,
            github=MagicMock(),
            supervisor_label="supervisor",
            load_issue_func=issue_loader,
        )

        assert len(promoted) == 0, "blocked issue should NOT be promoted"
        assert len(retained) == 0, "blocked issue should NOT be retained"
        assert len(removed) == 1, "blocked issue should be removed"
        assert removed[0].issue_number == 100

    def test_done_state_removed_not_promoted(self) -> None:
        """Issues transitioning to done should be removed, not promoted."""
        from unittest.mock import MagicMock

        from vibe3.models.orchestra_config import OrchestraConfig
        from vibe3.orchestra.queue_operations import promote_progressed_entries

        config = OrchestraConfig(repo="owner/repo")
        config.supervisor_handoff.issue_label = "supervisor"

        entry = QueueEntry(
            issue_number=200,
            collected_state="review",
            waiting_state="review",
        )

        issue = self._make_issue(200, IssueState.DONE)
        issue_loader = lambda n: issue  # noqa: E731

        promoted, retained, removed = promote_progressed_entries(
            frozen_queue=[entry],
            config=config,
            github=MagicMock(),
            supervisor_label="supervisor",
            load_issue_func=issue_loader,
        )

        assert len(promoted) == 0, "done issue should NOT be promoted"
        assert len(retained) == 0, "done issue should NOT be retained"
        assert len(removed) == 1, "done issue should be removed"
        assert removed[0].issue_number == 200

    def test_active_state_still_promoted(self) -> None:
        """Issues transitioning to active states should still be promoted."""
        from unittest.mock import MagicMock

        from vibe3.models.orchestra_config import OrchestraConfig
        from vibe3.orchestra.queue_operations import promote_progressed_entries

        config = OrchestraConfig(repo="owner/repo")
        config.supervisor_handoff.issue_label = "supervisor"

        entry = QueueEntry(
            issue_number=300,
            collected_state="in-progress",
            waiting_state="in-progress",
        )

        # State changed from in-progress to handoff (active transition)
        issue = self._make_issue(300, IssueState.HANDOFF)
        issue_loader = lambda n: issue  # noqa: E731

        promoted, retained, removed = promote_progressed_entries(
            frozen_queue=[entry],
            config=config,
            github=MagicMock(),
            supervisor_label="supervisor",
            load_issue_func=issue_loader,
        )

        assert len(promoted) == 1, "handoff issue should be promoted"
        assert len(retained) == 0
        assert len(removed) == 0

    def test_unchanged_state_stays_retained(self) -> None:
        """Issues with unchanged state should stay in place."""
        from unittest.mock import MagicMock

        from vibe3.models.orchestra_config import OrchestraConfig
        from vibe3.orchestra.queue_operations import promote_progressed_entries

        config = OrchestraConfig(repo="owner/repo")
        config.supervisor_handoff.issue_label = "supervisor"

        entry = QueueEntry(
            issue_number=400,
            collected_state="in-progress",
            waiting_state="in-progress",
        )

        issue = self._make_issue(400, IssueState.IN_PROGRESS)
        issue_loader = lambda n: issue  # noqa: E731

        promoted, retained, removed = promote_progressed_entries(
            frozen_queue=[entry],
            config=config,
            github=MagicMock(),
            supervisor_label="supervisor",
            load_issue_func=issue_loader,
        )

        assert len(promoted) == 0
        assert len(retained) == 1, "unchanged state should be retained"
        assert len(removed) == 0

    def test_mixed_queue_categorization(self) -> None:
        """Multiple entries with different state changes are correctly categorized."""
        from unittest.mock import MagicMock

        from vibe3.models.orchestra_config import OrchestraConfig
        from vibe3.orchestra.queue_operations import promote_progressed_entries

        config = OrchestraConfig(repo="owner/repo")
        config.supervisor_handoff.issue_label = "supervisor"

        entries = [
            QueueEntry(
                issue_number=1,
                collected_state="in-progress",
                waiting_state="in-progress",
            ),
            QueueEntry(
                issue_number=2,
                collected_state="review",
                waiting_state="review",
            ),
            QueueEntry(
                issue_number=3,
                collected_state="handoff",
                waiting_state="handoff",
            ),
        ]

        issues = {
            1: self._make_issue(1, IssueState.HANDOFF),  # active change -> promoted
            2: self._make_issue(2, IssueState.DONE),  # terminal -> removed
            3: self._make_issue(3, IssueState.HANDOFF),  # unchanged -> retained
        }
        issue_loader = lambda n: issues.get(n)  # noqa: E731

        promoted, retained, removed = promote_progressed_entries(
            frozen_queue=entries,
            config=config,
            github=MagicMock(),
            supervisor_label="supervisor",
            load_issue_func=issue_loader,
        )

        assert len(promoted) == 1
        assert promoted[0].issue_number == 1
        assert len(retained) == 1
        assert retained[0].issue_number == 3
        assert len(removed) == 1
        assert removed[0].issue_number == 2


class TestDispatchLoopRemovalLogs:
    """Tests that _dispatch_loop logs removal events when popping entries."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_done_entry_removed_with_event_log(
        self,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DONE issues popped in dispatch loop should produce a removal event."""
        capacity = make_capacity(remaining=1)
        coordinator = make_coordinator(
            "manager", capacity=capacity, mock_health_check=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return [QueueEntry(issue_number=500, collected_state="handoff")]

        coordinator._collect_frozen_queue = mock_collect

        states = {500: IssueState.HANDOFF}
        install_issue_loader(coordinator, states)

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO", **kwargs) -> None:
            _ = level
            events.append(message)

        monkeypatch.setattr(
            "vibe3.domain.dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        # First tick: collects entries
        await coordinator.coordinate()

        # Change state to DONE before next tick
        install_issue_loader(coordinator, {500: IssueState.DONE})

        # Second tick: DONE entry should be removed with log
        events.clear()
        await coordinator.coordinate()

        assert any(
            "removed #500" in e and "done" in e for e in events
        ), f"Expected removal log for #500 (done), got: {events}"
        assert len(emit_calls) == 0, "DONE issue should not be dispatched"

    @pytest.mark.asyncio
    async def test_preflight_failure_logged(
        self,
        make_capacity,
        make_coordinator,
        make_issue_info,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Entries removed by preflight failure should produce a removal event."""
        capacity = make_capacity(remaining=1)
        coordinator = make_coordinator(
            "manager", capacity=capacity, mock_health_check=True
        )

        # Pre-load a blocked issue directly into the frozen queue
        coordinator._frozen_queue = [
            QueueEntry(issue_number=600, collected_state="blocked")
        ]

        coordinator._load_issue = lambda issue_number: make_issue_info(
            issue_number, IssueState.BLOCKED, labels=["state/blocked"]
        )
        coordinator._qualify_gate.qualify_blocked_issue = lambda issue: None

        events: list[str] = []

        def capture_event(_category: str, message: str, level: str = "INFO", **kwargs) -> None:
            _ = level
            events.append(message)

        monkeypatch.setattr(
            "vibe3.domain.dispatch_coordinator.append_orchestra_event",
            capture_event,
        )

        async def mock_collect() -> list[QueueEntry]:
            return []

        coordinator._collect_frozen_queue = mock_collect

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert any(
            "removed #600" in e and "preflight failed" in e for e in events
        ), f"Expected preflight removal log for #600, got: {events}"
