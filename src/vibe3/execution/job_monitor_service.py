"""Job monitoring service for unified operational status.

Provides a snapshot of active and recently completed jobs from
the in-memory ActorRegistry, used by both shell (serve status)
and web (/status) interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.execution.actor import JobActor


@dataclass(frozen=True)
class ActiveJob:
    """Immutable view of a single actor job for monitoring display."""

    actor_id: str
    job_type: str  # "dispatch" / "governance" / "flow"
    status: str  # "running" / "done" / "failed" / "dead"
    issue_number: int
    branch: str
    started_at: str | None
    completed_at: str | None
    pid: int | None


@dataclass(frozen=True)
class JobMonitorSnapshot:
    """Aggregated snapshot of all tracked jobs."""

    active_jobs: tuple[ActiveJob, ...]  # QUEUED + RUNNING
    recent_jobs: tuple[ActiveJob, ...]  # terminal within TTL
    running_count: int
    completed_count: int
    failed_count: int


class JobMonitorService:
    """Service for querying actor-based job monitoring data."""

    def snapshot(self) -> JobMonitorSnapshot:
        """Build a snapshot from the actor registry.

        Returns:
            JobMonitorSnapshot with active jobs, recent completions,
            and summary counts.
        """
        from vibe3.execution import ActorStatus, get_actor_registry

        registry = get_actor_registry()

        # Cleanup expired before building snapshot
        registry.cleanup_expired()

        active_jobs = tuple(_to_active_job(a) for a in registry.get_active_actors())
        recent_jobs = tuple(_to_active_job(a) for a in registry.get_recent_actors())

        running_count = sum(
            1 for a in registry.get_active_actors() if a.status == ActorStatus.RUNNING
        )
        completed_count = sum(
            1 for a in registry.get_recent_actors() if a.status == ActorStatus.DONE
        )
        failed_count = sum(
            1
            for a in registry.get_recent_actors()
            if a.status in (ActorStatus.FAILED, ActorStatus.DEAD)
        )

        return JobMonitorSnapshot(
            active_jobs=active_jobs,
            recent_jobs=recent_jobs,
            running_count=running_count,
            completed_count=completed_count,
            failed_count=failed_count,
        )


def _to_active_job(actor: JobActor) -> ActiveJob:
    """Convert a JobActor to an immutable ActiveJob for display.

    Args:
        actor: A JobActor instance

    Returns:
        ActiveJob with actor data
    """
    return ActiveJob(
        actor_id=actor.actor_id,
        job_type=actor.job_type.value,
        status=actor.status.value,
        issue_number=actor.issue_number,
        branch=actor.branch,
        started_at=actor.started_at,
        completed_at=actor.completed_at,
        pid=actor.pid,
    )
