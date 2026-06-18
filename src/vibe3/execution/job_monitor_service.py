"""Job monitoring service for unified operational status.

Provides a snapshot of active and recently completed jobs from
the in-memory ActorRegistry, used by both shell (serve status)
and web (/status) interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vibe3.execution.actor import ActorStatus, JobType

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.execution.actor import JobActor


@dataclass(frozen=True)
class ActiveJob:
    """Immutable view of a single actor job for monitoring display."""

    actor_id: str
    job_type: JobType  # DISPATCH / GOVERNANCE / FLOW
    status: ActorStatus  # RUNNING / DONE / FAILED / DEAD / QUEUED
    issue_number: int
    branch: str
    started_at: str | None
    completed_at: str | None
    pid: int | None
    runtime_status: str | None = None
    log_path: str | None = None


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

    def __init__(self, store: SQLiteClient | None = None) -> None:
        self._store = store

    def snapshot(self) -> JobMonitorSnapshot:
        """Build a snapshot from the actor registry and optional runtime sessions.

        Returns:
            JobMonitorSnapshot with active jobs, recent completions,
            and summary counts.
        """
        from vibe3.execution import ActorStatus, get_actor_registry

        registry = get_actor_registry()

        # Cleanup expired before building snapshot
        registry.cleanup_expired()

        active_actors = registry.get_active_actors()
        recent_actors = registry.get_recent_actors()

        active_jobs_list = [_to_active_job(a) for a in active_actors]
        recent_jobs = tuple(_to_active_job(a) for a in recent_actors)

        active_jobs_list.extend(self._runtime_active_jobs(active_jobs_list))
        active_jobs = tuple(active_jobs_list)
        recent_jobs = tuple([*recent_jobs, *self._runtime_recent_jobs(recent_jobs)])

        running_count = sum(
            1 for job in active_jobs if job.status == ActorStatus.RUNNING
        )
        completed_count = sum(
            1
            for job in recent_jobs
            if _job_status_value(job) in {ActorStatus.DONE.value, "done"}
        )
        failed_count = sum(
            1
            for job in recent_jobs
            if _job_status_value(job)
            in {ActorStatus.FAILED.value, ActorStatus.DEAD.value, "failed", "orphaned"}
        )

        return JobMonitorSnapshot(
            active_jobs=active_jobs,
            recent_jobs=recent_jobs,
            running_count=running_count,
            completed_count=completed_count,
            failed_count=failed_count,
        )

    def _runtime_active_jobs(self, existing_jobs: list[ActiveJob]) -> list[ActiveJob]:
        """Return live runtime_session rows not already represented by actors."""
        if self._store is None:
            return []

        try:
            sessions = self._store.list_live_runtime_sessions()
        except Exception:
            return []

        existing_actor_ids = {job.actor_id for job in existing_jobs}
        jobs: list[ActiveJob] = []
        for session in sessions:
            job = _session_to_active_job(session)
            if job.actor_id in existing_actor_ids:
                continue
            jobs.append(job)
        return jobs

    def _runtime_recent_jobs(
        self, existing_jobs: tuple[ActiveJob, ...]
    ) -> list[ActiveJob]:
        """Return recent terminal runtime_session rows not represented by actors."""
        if self._store is None:
            return []

        try:
            sessions = self._store.list_recent_runtime_sessions(limit=10)
        except Exception:
            return []

        existing_actor_ids = {job.actor_id for job in existing_jobs}
        jobs: list[ActiveJob] = []
        for session in sessions:
            job = _session_to_active_job(session)
            if job.actor_id in existing_actor_ids:
                continue
            jobs.append(job)
        return jobs


def _to_active_job(actor: JobActor) -> ActiveJob:
    """Convert a JobActor to an immutable ActiveJob for display.

    Args:
        actor: A JobActor instance

    Returns:
        ActiveJob with actor data
    """
    return ActiveJob(
        actor_id=actor.actor_id,
        job_type=actor.job_type,
        status=actor.status,
        issue_number=actor.issue_number,
        branch=actor.branch,
        started_at=actor.started_at,
        completed_at=actor.completed_at,
        pid=actor.pid,
        runtime_status=None,
        log_path=None,
    )


def _session_to_active_job(session: dict[str, Any]) -> ActiveJob:
    """Convert a durable runtime_session row to an ActiveJob."""
    role = str(session.get("role") or "")
    status = _runtime_status_to_actor_status(str(session.get("status") or ""))
    actor_id = str(session.get("session_name") or f"runtime-{session.get('id')}")

    issue_number = 0
    if session.get("target_type") == "issue":
        try:
            issue_number = int(str(session.get("target_id") or "0"))
        except ValueError:
            issue_number = 0

    return ActiveJob(
        actor_id=actor_id,
        job_type=_role_to_job_type(role),
        status=status,
        issue_number=issue_number,
        branch=str(session.get("branch") or ""),
        started_at=session.get("started_at") or session.get("created_at"),
        completed_at=session.get("ended_at"),
        pid=None,
        runtime_status=str(session.get("status") or ""),
        log_path=session.get("log_path"),
    )


def _runtime_status_to_actor_status(status: str) -> ActorStatus:
    if status == "running":
        return ActorStatus.RUNNING
    if status == "starting":
        return ActorStatus.QUEUED
    if status == "done":
        return ActorStatus.DONE
    if status == "failed":
        return ActorStatus.FAILED
    return ActorStatus.DEAD


def _role_to_job_type(role: str) -> JobType:
    if role in {"governance", "supervisor"}:
        return JobType.GOVERNANCE
    if role == "flow":
        return JobType.FLOW
    return JobType.DISPATCH


def _job_status_value(job: ActiveJob) -> str:
    return job.runtime_status or job.status.value
