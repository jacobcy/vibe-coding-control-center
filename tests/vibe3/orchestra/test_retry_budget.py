"""Tests for retry budget and eviction policy."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.queue_operations import promote_progressed_entries


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
