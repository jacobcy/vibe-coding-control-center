"""Tests for JobMonitorService snapshot aggregation."""

from __future__ import annotations

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
from vibe3.execution.job_monitor_service import (
    ActiveJob,
    JobMonitorService,
)


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Reset the singleton registry before each test."""
    _reset_registry()


def _create_running_actor(
    registry: ActorRegistry,
    issue: int = 100,
    branch: str = "task/issue-100",
    job_type: JobType = JobType.DISPATCH,
) -> JobActor:
    """Helper to create and launch an actor."""
    store = MagicMock(spec=SQLiteClient)
    actor = registry.create_actor(
        job_type=job_type,
        issue_number=issue,
        branch=branch,
        store=store,
    )
    actor.record_launch()
    return actor


class TestJobMonitorService:
    """Test JobMonitorService.snapshot() aggregation."""

    def test_empty_registry_returns_empty_snapshot(self) -> None:
        """No actors -> empty snapshot with zero counts."""
        svc = JobMonitorService()
        snap = svc.snapshot()

        assert snap.active_jobs == ()
        assert snap.recent_jobs == ()
        assert snap.running_count == 0
        assert snap.completed_count == 0
        assert snap.failed_count == 0

    def test_running_actor_appears_in_active_jobs(self) -> None:
        """RUNNING actors appear in active_jobs."""
        registry = get_actor_registry()
        actor = _create_running_actor(registry, issue=200)

        svc = JobMonitorService()
        snap = svc.snapshot()

        assert snap.running_count == 1
        assert len(snap.active_jobs) == 1
        job = snap.active_jobs[0]
        assert job.actor_id == actor.actor_id
        assert job.status == ActorStatus.RUNNING
        assert job.issue_number == 200

    def test_queued_actor_appears_in_active_jobs(self) -> None:
        """QUEUED actors also appear in active_jobs."""
        registry = get_actor_registry()
        store = MagicMock(spec=SQLiteClient)
        registry.create_actor(
            job_type=JobType.DISPATCH,
            issue_number=300,
            branch="task/issue-300",
            store=store,
        )

        svc = JobMonitorService()
        snap = svc.snapshot()

        assert len(snap.active_jobs) == 1
        assert snap.active_jobs[0].status == ActorStatus.QUEUED

    def test_completed_actor_appears_in_recent_jobs(self) -> None:
        """DONE actors appear in recent_jobs."""
        registry = get_actor_registry()
        actor = _create_running_actor(registry, issue=400)
        actor.record_completion(detail="planner launched")

        svc = JobMonitorService()
        snap = svc.snapshot()

        assert snap.completed_count == 1
        assert snap.running_count == 0
        assert len(snap.recent_jobs) == 1
        assert snap.recent_jobs[0].status == ActorStatus.DONE

    def test_failed_actor_appears_in_recent_jobs(self) -> None:
        """FAILED actors appear in recent_jobs with failed_count."""
        registry = get_actor_registry()
        actor = _create_running_actor(registry, issue=500)
        actor.record_failure(error="dispatch error")

        svc = JobMonitorService()
        snap = svc.snapshot()

        assert snap.failed_count == 1
        assert snap.completed_count == 0
        assert len(snap.recent_jobs) == 1
        assert snap.recent_jobs[0].status == ActorStatus.FAILED

    def test_dead_actor_counted_as_failed(self) -> None:
        """DEAD actors count toward failed_count."""
        registry = get_actor_registry()
        actor = _create_running_actor(registry, issue=600)
        actor.record_dead(detail="cancelled")

        svc = JobMonitorService()
        snap = svc.snapshot()

        assert snap.failed_count == 1
        assert snap.recent_jobs[0].status == ActorStatus.DEAD

    def test_mixed_states_correct_counts(self) -> None:
        """Multiple actors with different states produce correct counts."""
        registry = get_actor_registry()

        # 2 running
        _create_running_actor(registry, issue=101)
        _create_running_actor(registry, issue=102)

        # 1 completed
        a3 = _create_running_actor(registry, issue=103)
        a3.record_completion()

        # 1 failed
        a4 = _create_running_actor(registry, issue=104)
        a4.record_failure(error="error")

        svc = JobMonitorService()
        snap = svc.snapshot()

        assert snap.running_count == 2
        assert snap.completed_count == 1
        assert snap.failed_count == 1
        assert len(snap.active_jobs) == 2
        assert len(snap.recent_jobs) == 2

    def test_active_job_fields_populated(self) -> None:
        """ActiveJob fields are correctly populated from JobActor."""
        registry = get_actor_registry()
        actor = _create_running_actor(
            registry,
            issue=700,
            branch="task/issue-700",
            job_type=JobType.GOVERNANCE,
        )

        svc = JobMonitorService()
        snap = svc.snapshot()

        job = snap.active_jobs[0]
        assert isinstance(job, ActiveJob)
        assert job.actor_id == actor.actor_id
        assert job.job_type == JobType.GOVERNANCE
        assert job.status == ActorStatus.RUNNING
        assert job.issue_number == 700
        assert job.branch == "task/issue-700"
        assert job.started_at is not None
        assert job.completed_at is None
        assert job.pid is None

    def test_snapshot_is_frozen_dataclass(self) -> None:
        """Snapshot and ActiveJob are frozen (immutable)."""
        svc = JobMonitorService()
        snap = svc.snapshot()

        with pytest.raises(AttributeError):
            snap.running_count = 99  # type: ignore[misc]

    def test_snapshot_calls_cleanup_expired(self) -> None:
        """snapshot() triggers cleanup of expired actors."""
        registry = get_actor_registry()
        # Create an actor with very short TTL
        registry._ttl_seconds = 0
        actor = _create_running_actor(registry, issue=800)
        actor.record_completion()

        # With TTL=0, cleanup_expired should remove it
        svc = JobMonitorService()
        snap = svc.snapshot()

        assert len(snap.recent_jobs) == 0
        assert snap.completed_count == 0
