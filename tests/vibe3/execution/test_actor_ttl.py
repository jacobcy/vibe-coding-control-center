"""Tests for actor supervision tracking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from vibe3.clients import SQLiteClient
from vibe3.execution.actor import (
    ActorRegistry,
    JobType,
    _reset_registry,
    get_actor_registry,
)


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Reset the singleton registry before each test."""
    _reset_registry()


class TestTTLTracking:
    """Test TTL-based actor retention in registry."""

    def test_terminal_actor_stays_in_registry(self) -> None:
        """Terminal actors are not immediately removed from registry."""
        store = MagicMock(spec=SQLiteClient)
        # Use global singleton since _notify_terminal targets it
        registry = get_actor_registry()

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_completion()

        # Actor should still be in registry
        assert registry.get_actor(actor.actor_id) is actor

    def test_mark_terminal_records_timestamp(self) -> None:
        """mark_terminal() records terminal timestamp for the actor."""
        store = MagicMock(spec=SQLiteClient)
        # Use global singleton since _notify_terminal targets it
        registry = get_actor_registry()

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_completion()

        # mark_terminal is called internally by record_completion
        assert actor.actor_id in registry._completed_at

    def test_get_recent_actors_returns_terminal_within_ttl(self) -> None:
        """get_recent_actors() returns terminal actors within TTL."""
        store = MagicMock(spec=SQLiteClient)
        # Use global singleton since _notify_terminal targets it
        registry = get_actor_registry()
        registry._ttl_seconds = 1800

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_completion()

        recent = registry.get_recent_actors()
        assert len(recent) == 1
        assert recent[0] is actor

    def test_get_recent_actors_excludes_expired(self) -> None:
        """get_recent_actors() excludes actors past TTL."""
        store = MagicMock(spec=SQLiteClient)
        # Use global singleton since _notify_terminal targets it
        registry = get_actor_registry()
        registry._ttl_seconds = 60

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_completion()

        # Manually backdate the completion time
        registry._completed_at[actor.actor_id] = datetime.now(
            tz=timezone.utc
        ) - timedelta(seconds=120)

        recent = registry.get_recent_actors()
        assert len(recent) == 0

    def test_get_active_actors_excludes_terminal(self) -> None:
        """get_active_actors() excludes terminal actors."""
        store = MagicMock(spec=SQLiteClient)
        registry = ActorRegistry()

        running = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="branch-1",
            store=store,
        )
        running.record_launch()

        done = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=200,
            branch="branch-2",
            store=store,
        )
        done.record_launch()
        done.record_completion()

        active = registry.get_active_actors()
        assert len(active) == 1
        assert active[0] is running

    def test_cleanup_expired_removes_old_actors(self) -> None:
        """cleanup_expired() removes actors past TTL."""
        store = MagicMock(spec=SQLiteClient)
        # Use global singleton since _notify_terminal targets it
        registry = get_actor_registry()
        registry._ttl_seconds = 60

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_completion()

        # Backdate completion
        registry._completed_at[actor.actor_id] = datetime.now(
            tz=timezone.utc
        ) - timedelta(seconds=120)

        expired_ids = registry.cleanup_expired()
        assert actor.actor_id in expired_ids
        assert registry.get_actor(actor.actor_id) is None

    def test_cleanup_expired_keeps_fresh_actors(self) -> None:
        """cleanup_expired() keeps actors within TTL."""
        store = MagicMock(spec=SQLiteClient)
        # Use global singleton since _notify_terminal targets it
        registry = get_actor_registry()
        registry._ttl_seconds = 1800

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_completion()

        expired_ids = registry.cleanup_expired()
        assert len(expired_ids) == 0
        assert registry.get_actor(actor.actor_id) is actor

    def test_cleanup_expired_returns_empty_for_no_expired(self) -> None:
        """cleanup_expired() returns empty list when nothing expired."""
        registry = ActorRegistry(ttl_seconds=1800)
        expired = registry.cleanup_expired()
        assert expired == []

    def test_remove_actor_clears_completed_at(self) -> None:
        """remove_actor() also clears completed_at tracking."""
        store = MagicMock(spec=SQLiteClient)
        # Use global singleton since _notify_terminal targets it
        registry = get_actor_registry()

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_completion()

        registry.remove_actor(actor.actor_id)
        assert actor.actor_id not in registry._completed_at

    def test_default_ttl_is_1800(self) -> None:
        """Default TTL is 1800 seconds (30 minutes)."""
        registry = ActorRegistry()
        assert registry._ttl_seconds == 1800

    def test_custom_ttl(self) -> None:
        """Custom TTL can be set."""
        registry = ActorRegistry(ttl_seconds=60)
        assert registry._ttl_seconds == 60


class TestTerminalNotification:
    """Test that terminal state changes notify the registry."""

    def test_record_completion_notifies_registry(self) -> None:
        """record_completion() marks actor as terminal in registry."""
        _reset_registry()
        registry = get_actor_registry()
        store = MagicMock(spec=SQLiteClient)

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_completion()

        assert actor.actor_id in registry._completed_at

    def test_record_failure_notifies_registry(self) -> None:
        """record_failure() marks actor as terminal in registry."""
        _reset_registry()
        registry = get_actor_registry()
        store = MagicMock(spec=SQLiteClient)

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_failure(error="test error")

        assert actor.actor_id in registry._completed_at

    def test_record_dead_notifies_registry(self) -> None:
        """record_dead() marks actor as terminal in registry."""
        _reset_registry()
        registry = get_actor_registry()
        store = MagicMock(spec=SQLiteClient)

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()
        actor.record_dead(detail="cancelled")

        assert actor.actor_id in registry._completed_at

    def test_notify_terminal_logs_unexpected_exceptions(self, monkeypatch) -> None:
        """_notify_terminal should log unexpected exceptions, not silently swallow."""
        _reset_registry()
        registry = get_actor_registry()
        store = MagicMock(spec=SQLiteClient)

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=100,
            branch="test-branch",
            store=store,
        )
        actor.record_launch()

        # Make mark_terminal raise an unexpected exception type
        original = registry.mark_terminal

        def _broken_mark_terminal(actor_id: str) -> None:
            raise TypeError("unexpected bug")

        registry.mark_terminal = _broken_mark_terminal  # type: ignore[assignment]

        # Should NOT raise — it logs instead
        actor.record_completion()

        # Restore for other tests
        registry.mark_terminal = original  # type: ignore[assignment]
