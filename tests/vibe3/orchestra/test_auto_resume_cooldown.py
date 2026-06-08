"""Tests for auto-resume cooldown circuit breaker mechanism."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.queue_operations import (
    _auto_resume_to_ready,
    _last_auto_resume_attempt,
)


class TestAutoResumeCooldown:
    """Tests for auto-resume cooldown mechanism."""

    def test_cooldown_skips_rapid_retry(self, make_issue_info, monkeypatch) -> None:
        """Second auto-resume within cooldown period is skipped (failure case)."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue = make_issue_info(100, IssueState.CLAIMED)

        # Start with empty cooldown dict for test isolation
        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations._last_auto_resume_attempt",
            {},
        )

        mock_label_service = MagicMock()
        # First call fails, second would succeed
        mock_label_service.transition = MagicMock(
            side_effect=[RuntimeError("API error"), None]
        )

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Mock time to control cooldown
        current_time = [1000.0]

        def mock_time():
            return current_time[0]

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.time.time",
            mock_time,
        )

        # First call - fails but sets cooldown
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # Advance time by 60s (within cooldown)
        current_time[0] = 1060.0

        # Second call - should be skipped by cooldown (transition not called)
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # Verify transition was called only once (second was skipped by cooldown)
        mock_label_service.transition.assert_called_once_with(
            100,
            IssueState.READY,
            actor="orchestra:auto-resume",
            force=True,
        )

    def test_cooldown_allows_after_expiry(self, make_issue_info, monkeypatch) -> None:
        """Auto-resume after cooldown expiry is allowed."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue = make_issue_info(101, IssueState.CLAIMED)

        # Start with empty cooldown dict for test isolation
        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations._last_auto_resume_attempt",
            {},
        )

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Mock time to control cooldown
        current_time = [1000.0]

        def mock_time():
            return current_time[0]

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.time.time",
            mock_time,
        )

        # First call
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # Advance time by 301s (beyond cooldown)
        current_time[0] = 1301.0

        # Second call - should be allowed
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # Verify transition was called twice
        assert mock_label_service.transition.call_count == 2

    def test_successful_resume_clears_cooldown(
        self, make_issue_info, monkeypatch
    ) -> None:
        """Successful resume clears cooldown for immediate future resume."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue = make_issue_info(102, IssueState.CLAIMED)

        # Start with empty cooldown dict for test isolation
        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations._last_auto_resume_attempt",
            {},
        )

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Mock time
        current_time = [1000.0]

        def mock_time():
            return current_time[0]

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.time.time",
            mock_time,
        )

        # First call - succeeds and clears cooldown
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # No time advance - should still work because cooldown was cleared
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # Verify transition was called twice (cooldown cleared after success)
        assert mock_label_service.transition.call_count == 2

    def test_cooldown_tracks_per_issue_independently(
        self, make_issue_info, monkeypatch
    ) -> None:
        """Cooldown is tracked independently per issue."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue_100 = make_issue_info(100, IssueState.CLAIMED)
        issue_200 = make_issue_info(200, IssueState.CLAIMED)

        # Start with empty cooldown dict for test isolation
        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations._last_auto_resume_attempt",
            {},
        )

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Mock time
        current_time = [1000.0]

        def mock_time():
            return current_time[0]

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.time.time",
            mock_time,
        )

        # Call for issue #100
        _auto_resume_to_ready(issue_100, config, label_service=mock_label_service)

        # Immediately call for issue #200 - should work (different issue)
        _auto_resume_to_ready(issue_200, config, label_service=mock_label_service)

        # Verify both calls went through
        assert mock_label_service.transition.call_count == 2

    def test_cooldown_evicts_stale_entries(self, make_issue_info, monkeypatch) -> None:
        """Stale cooldown entries (>24h) are evicted to bound memory."""
        from vibe3.models.orchestra_config import OrchestraConfig

        config = OrchestraConfig(repo="owner/repo")
        issue = make_issue_info(300, IssueState.CLAIMED)

        # Seed stale entry from 25 hours ago
        stale_time = 1000.0
        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations._last_auto_resume_attempt",
            {300: stale_time, 999: stale_time},
        )

        mock_label_service = MagicMock()
        mock_label_service.transition = MagicMock()

        event_calls = []

        def mock_append_event(source: str, message: str) -> None:
            event_calls.append((source, message))

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.append_orchestra_event",
            mock_append_event,
        )

        # Current time is 25h after stale entries
        current_time = [stale_time + 86400 + 1]

        def mock_time():
            return current_time[0]

        monkeypatch.setattr(
            "vibe3.orchestra.queue_operations.time.time",
            mock_time,
        )

        # Call triggers eviction + proceeds with resume
        _auto_resume_to_ready(issue, config, label_service=mock_label_service)

        # Entry for 999 should be evicted (stale)
        assert 999 not in _last_auto_resume_attempt
        # Issue 300 was resumed successfully (pop clears on success)
        mock_label_service.transition.assert_called_once()
