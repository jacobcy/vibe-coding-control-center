"""Tests for actor supervision tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from vibe3.clients import SQLiteClient
from vibe3.execution.actor import (
    ActorRegistry,
    ActorStatus,
    JobActor,
    JobType,
    _reset_registry,
    get_actor_registry,
)


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Reset the singleton registry before each test."""
    _reset_registry()


class TestActorStatusTransitions:
    """Test ActorStatus transition validation."""

    def test_queued_to_running(self) -> None:
        """Valid transition: queued → running."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.QUEUED,
            issue_number=123,
            branch="test-branch",
            _store=store,
        )

        actor.record_launch()

        assert actor.status == ActorStatus.RUNNING
        assert actor.started_at is not None
        assert actor.pid is None

    def test_running_to_done(self) -> None:
        """Valid transition: running → done."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.RUNNING,
            issue_number=123,
            branch="test-branch",
            started_at=datetime.now(tz=timezone.utc).isoformat(),
            _store=store,
        )

        actor.record_completion(detail="Success")

        assert actor.status == ActorStatus.DONE
        assert actor.completed_at is not None

    def test_running_to_failed(self) -> None:
        """Valid transition: running → failed."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.RUNNING,
            issue_number=123,
            branch="test-branch",
            started_at=datetime.now(tz=timezone.utc).isoformat(),
            _store=store,
        )

        actor.record_failure(error="Something went wrong")

        assert actor.status == ActorStatus.FAILED
        assert actor.completed_at is not None

    def test_running_to_dead(self) -> None:
        """Valid transition: running → dead."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.RUNNING,
            issue_number=123,
            branch="test-branch",
            started_at=datetime.now(tz=timezone.utc).isoformat(),
            _store=store,
        )

        actor.record_dead(detail="Cancelled")

        assert actor.status == ActorStatus.DEAD
        assert actor.completed_at is not None

    def test_invalid_transition_done_to_running(self) -> None:
        """Invalid transition: done → running raises ValueError."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.DONE,
            issue_number=123,
            branch="test-branch",
            started_at=datetime.now(tz=timezone.utc).isoformat(),
            completed_at=datetime.now(tz=timezone.utc).isoformat(),
            _store=store,
        )

        with pytest.raises(ValueError, match="Invalid status transition"):
            actor.record_launch()

    def test_invalid_transition_queued_to_done(self) -> None:
        """Invalid transition: queued → done raises ValueError."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.QUEUED,
            issue_number=123,
            branch="test-branch",
            _store=store,
        )

        with pytest.raises(ValueError, match="Invalid status transition"):
            actor.record_completion()


class TestJobActorMethods:
    """Test JobActor methods."""

    def test_record_launch_sets_pid(self) -> None:
        """record_launch() sets pid when provided."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.QUEUED,
            issue_number=123,
            branch="test-branch",
            _store=store,
        )

        actor.record_launch(pid=12345)

        assert actor.pid == 12345
        assert actor.status == ActorStatus.RUNNING

    def test_record_launch_writes_event(self) -> None:
        """record_launch() writes actor_started event."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.QUEUED,
            issue_number=123,
            branch="test-branch",
            _store=store,
        )

        actor.record_launch()

        store.add_event.assert_called_once()
        call_kwargs = store.add_event.call_args[1]
        assert call_kwargs["event_type"] == "actor_started"
        assert call_kwargs["branch"] == "test-branch"
        assert call_kwargs["refs"]["actor_id"] == "test-1"

    def test_record_completion_writes_event(self) -> None:
        """record_completion() writes actor_done event."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.RUNNING,
            issue_number=123,
            branch="test-branch",
            started_at=datetime.now(tz=timezone.utc).isoformat(),
            _store=store,
        )

        actor.record_completion(detail="planner launched")

        store.add_event.assert_called_once()
        call_kwargs = store.add_event.call_args[1]
        assert call_kwargs["event_type"] == "actor_done"
        assert call_kwargs["detail"] == "planner launched"

    def test_record_failure_writes_event(self) -> None:
        """record_failure() writes actor_failed event."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.RUNNING,
            issue_number=123,
            branch="test-branch",
            started_at=datetime.now(tz=timezone.utc).isoformat(),
            _store=store,
        )

        actor.record_failure(error="Dispatch failed")

        store.add_event.assert_called_once()
        call_kwargs = store.add_event.call_args[1]
        assert call_kwargs["event_type"] == "actor_failed"
        assert call_kwargs["detail"] == "Dispatch failed"

    def test_record_dead_writes_event(self) -> None:
        """record_dead() writes actor_dead event."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-1",
            job_type=JobType.DISPATCH,
            status=ActorStatus.RUNNING,
            issue_number=123,
            branch="test-branch",
            started_at=datetime.now(tz=timezone.utc).isoformat(),
            _store=store,
        )

        actor.record_dead(detail="planner skipped: already planned")

        store.add_event.assert_called_once()
        call_kwargs = store.add_event.call_args[1]
        assert call_kwargs["event_type"] == "actor_dead"
        assert call_kwargs["detail"] == "planner skipped: already planned"


class TestActorRegistry:
    """Test ActorRegistry methods."""

    def test_create_actor_returns_actor(self) -> None:
        """create_actor() returns a new actor in QUEUED state."""
        store = MagicMock(spec=SQLiteClient)
        registry = ActorRegistry()

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=123,
            branch="test-branch",
            store=store,
        )

        assert actor.status == ActorStatus.QUEUED
        assert actor.job_type == JobType.DISPATCH
        assert actor.issue_number == 123
        assert actor.branch == "test-branch"
        assert actor.actor_id.startswith("actor-")

    def test_create_actor_records_event(self) -> None:
        """create_actor() records actor_created event."""
        store = MagicMock(spec=SQLiteClient)
        registry = ActorRegistry()

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=123,
            branch="test-branch",
            store=store,
        )

        store.add_event.assert_called_once()
        call_kwargs = store.add_event.call_args[1]
        assert call_kwargs["event_type"] == "actor_created"
        assert call_kwargs["refs"]["actor_id"] == actor.actor_id
        assert call_kwargs["refs"]["issue"] == "123"

    def test_get_actor_returns_existing(self) -> None:
        """get_actor() returns existing actor."""
        store = MagicMock(spec=SQLiteClient)
        registry = ActorRegistry()

        created = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=123,
            branch="test-branch",
            store=store,
        )

        retrieved = registry.get_actor(created.actor_id)
        assert retrieved is created

    def test_get_actor_returns_none_for_missing(self) -> None:
        """get_actor() returns None for missing actor."""
        registry = ActorRegistry()
        assert registry.get_actor("nonexistent") is None

    def test_get_active_actors_returns_non_terminal(self) -> None:
        """get_active_actors() returns only QUEUED and RUNNING actors."""
        store = MagicMock(spec=SQLiteClient)
        registry = ActorRegistry()

        actor1 = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=123,
            branch="test-branch-1",
            store=store,
        )
        actor2 = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=124,
            branch="test-branch-2",
            store=store,
        )
        actor2.record_launch()  # RUNNING

        actor3 = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=125,
            branch="test-branch-3",
            store=store,
        )
        actor3.record_launch()
        actor3.record_completion()  # DONE (terminal)

        active = registry.get_active_actors()
        assert len(active) == 2
        assert actor1 in active
        assert actor2 in active
        assert actor3 not in active

    def test_remove_actor(self) -> None:
        """remove_actor() removes actor from registry."""
        store = MagicMock(spec=SQLiteClient)
        registry = ActorRegistry()

        actor = registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=123,
            branch="test-branch",
            store=store,
        )

        assert registry.get_actor(actor.actor_id) is actor
        registry.remove_actor(actor.actor_id)
        assert registry.get_actor(actor.actor_id) is None


class TestGetActorRegistry:
    """Test get_actor_registry singleton."""

    def test_returns_singleton(self) -> None:
        """get_actor_registry() returns the same instance."""
        registry1 = get_actor_registry()
        registry2 = get_actor_registry()
        assert registry1 is registry2

    def test_reset_creates_new_instance(self) -> None:
        """_reset_registry() creates a new instance."""
        registry1 = get_actor_registry()
        _reset_registry()
        registry2 = get_actor_registry()
        assert registry1 is not registry2


class TestEventRecording:
    """Test event recording to store."""

    def test_event_refs_include_actor_id(self) -> None:
        """All actor events include actor_id in refs."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-actor-id",
            job_type=JobType.DISPATCH,
            status=ActorStatus.QUEUED,
            issue_number=123,
            branch="test-branch",
            _store=store,
        )

        actor.record_launch()

        call_kwargs = store.add_event.call_args[1]
        assert "actor_id" in call_kwargs["refs"]
        assert call_kwargs["refs"]["actor_id"] == "test-actor-id"

    def test_event_actor_format(self) -> None:
        """Actor events use 'actor:<job_type>' format."""
        store = MagicMock(spec=SQLiteClient)
        actor = JobActor(
            actor_id="test-actor-id",
            job_type=JobType.DISPATCH,
            status=ActorStatus.QUEUED,
            issue_number=123,
            branch="test-branch",
            _store=store,
        )

        actor.record_launch()

        call_kwargs = store.add_event.call_args[1]
        assert call_kwargs["actor"] == "actor:dispatch"
