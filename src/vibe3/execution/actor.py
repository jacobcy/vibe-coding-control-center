"""Lightweight actor abstraction for command-job supervision.

This module provides in-memory tracking of job lifecycle (queued → running →
done | failed | dead) with event recording to the existing event_log.

Design notes:
- In-memory only (no SQLite schema change) — matches the spec's "lightweight" intent
- Singleton pattern avoids passing registry through call chains
- The existing runtime_session table remains the durable session store; actor
  complements it with in-process supervision
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


class ActorStatus(str, Enum):
    """Lifecycle status for a JobActor.

    Status transitions:
        queued → running → done | failed | dead

    Note:
        The 'dead' status indicates asyncio task cancellation or unexpected
        termination, distinct from 'aborted' in runtime_session which indicates
        explicit user abort.
    """

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    DEAD = "dead"


class JobType(str, Enum):
    """Type of job being supervised by the actor."""

    DISPATCH = "dispatch"
    GOVERNANCE = "governance"
    FLOW = "flow"


# Valid status transitions
_VALID_TRANSITIONS: dict[ActorStatus, set[ActorStatus]] = {
    ActorStatus.QUEUED: {ActorStatus.RUNNING},
    ActorStatus.RUNNING: {ActorStatus.DONE, ActorStatus.FAILED, ActorStatus.DEAD},
    ActorStatus.DONE: set(),  # Terminal
    ActorStatus.FAILED: set(),  # Terminal
    ActorStatus.DEAD: set(),  # Terminal
}


@dataclass
class JobActor:
    """In-memory state tracker for a supervised job.

    Each mutation (record_launch, record_completion, record_failure, record_dead)
    writes to the event_log via the store reference.

    Attributes:
        actor_id: Unique identifier for this actor
        job_type: Type of job being supervised
        status: Current lifecycle status
        issue_number: Issue number (0 for governance)
        branch: Target branch
        _store: Reference to SQLiteClient for event recording (internal)
        started_at: ISO 8601 timestamp when launched (None if queued)
        completed_at: ISO 8601 timestamp when terminated (None if not terminal)
        pid: Process ID if available (None if not launched or not applicable)
    """

    actor_id: str
    job_type: JobType
    status: ActorStatus
    issue_number: int
    branch: str
    _store: SQLiteClient = field(repr=False, compare=False)
    started_at: str | None = None
    completed_at: str | None = None
    pid: int | None = None

    def _validate_transition(self, new_status: ActorStatus) -> None:
        """Validate that the transition is allowed.

        Args:
            new_status: Target status

        Raises:
            ValueError: If transition is not valid
        """
        allowed = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid status transition: {self.status.value} → {new_status.value}"
            )

    def _record_event(
        self,
        event_type: str,
        detail: str | None = None,
        refs: dict[str, str] | None = None,
    ) -> None:
        """Record an event to the event_log.

        Args:
            event_type: Event type (e.g., "actor_started", "actor_done")
            detail: Optional detail string
            refs: Optional refs dict (will include actor_id)
        """
        event_refs = {**(refs or {}), "actor_id": self.actor_id}

        try:
            self._store.add_event(
                branch=self.branch,
                event_type=event_type,
                actor=f"actor:{self.job_type.value}",
                detail=detail,
                refs=event_refs,
            )
        except Exception as e:
            logger.warning(f"Failed to record actor event {event_type}: {e}")

    def record_launch(self, pid: int | None = None) -> None:
        """Record that the job has launched.

        Args:
            pid: Optional process ID

        Raises:
            ValueError: If not in QUEUED status
        """
        self._validate_transition(ActorStatus.RUNNING)

        self.status = ActorStatus.RUNNING
        self.started_at = datetime.now(tz=timezone.utc).isoformat()
        self.pid = pid

        detail = f"Actor launched (pid={pid})" if pid else "Actor launched"
        self._record_event("actor_started", detail=detail)

    def record_completion(self, detail: str | None = None) -> None:
        """Record that the job has completed successfully.

        Args:
            detail: Optional detail string

        Raises:
            ValueError: If not in RUNNING status
        """
        self._validate_transition(ActorStatus.DONE)

        self.status = ActorStatus.DONE
        self.completed_at = datetime.now(tz=timezone.utc).isoformat()

        event_detail = detail or "Actor completed"
        self._record_event("actor_done", detail=event_detail)

    def record_failure(self, error: str) -> None:
        """Record that the job has failed.

        Args:
            error: Error message

        Raises:
            ValueError: If not in RUNNING status
        """
        self._validate_transition(ActorStatus.FAILED)

        self.status = ActorStatus.FAILED
        self.completed_at = datetime.now(tz=timezone.utc).isoformat()

        self._record_event("actor_failed", detail=error)

    def record_dead(self, detail: str | None = None) -> None:
        """Record that the job has died (cancelled or unexpected termination).

        Args:
            detail: Optional detail string

        Raises:
            ValueError: If not in RUNNING status
        """
        self._validate_transition(ActorStatus.DEAD)

        self.status = ActorStatus.DEAD
        self.completed_at = datetime.now(tz=timezone.utc).isoformat()

        event_detail = detail or "Actor died"
        self._record_event("actor_dead", detail=event_detail)


class ActorRegistry:
    """Registry for tracking active actors.

    This is a module-level singleton accessed via get_actor_registry().

    Note:
        The registry is in-memory only. Actors are lost if the orchestrator
        process exits. This matches the "lightweight" design intent — the
        runtime_session table remains the durable session store.
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._actors: dict[str, JobActor] = {}

    def create_actor(
        self,
        job_type: JobType,
        issue_number: int,
        branch: str,
        store: SQLiteClient,
    ) -> JobActor:
        """Create a new actor in QUEUED state.

        Args:
            job_type: Type of job
            issue_number: Issue number (0 for governance)
            branch: Target branch
            store: SQLite client for event recording

        Returns:
            The created actor
        """
        actor_id = f"actor-{uuid.uuid4().hex[:12]}"

        actor = JobActor(
            actor_id=actor_id,
            job_type=job_type,
            status=ActorStatus.QUEUED,
            issue_number=issue_number,
            branch=branch,
            _store=store,
        )

        self._actors[actor_id] = actor

        # Record creation event
        try:
            store.add_event(
                branch=branch,
                event_type="actor_created",
                actor=f"actor:{job_type.value}",
                detail=f"Actor created for {job_type.value}",
                refs={"actor_id": actor_id, "issue": str(issue_number)},
            )
        except Exception as e:
            logger.warning(f"Failed to record actor_created event: {e}")

        return actor

    def get_actor(self, actor_id: str) -> JobActor | None:
        """Get an actor by ID.

        Args:
            actor_id: Actor ID

        Returns:
            The actor if found, None otherwise
        """
        return self._actors.get(actor_id)

    def get_active_actors(self) -> list[JobActor]:
        """Get all non-terminal actors.

        Returns:
            List of actors in QUEUED or RUNNING status
        """
        return [
            actor
            for actor in self._actors.values()
            if actor.status in (ActorStatus.QUEUED, ActorStatus.RUNNING)
        ]

    def remove_actor(self, actor_id: str) -> None:
        """Remove an actor from the registry.

        Args:
            actor_id: Actor ID
        """
        self._actors.pop(actor_id, None)


# Module-level singleton
_REGISTRY: ActorRegistry | None = None


def get_actor_registry() -> ActorRegistry:
    """Get the module-level actor registry singleton.

    Returns:
        The singleton ActorRegistry instance
    """
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ActorRegistry()
    return _REGISTRY


def _reset_registry() -> None:
    """Reset the module-level registry singleton.

    This is for test use only.
    """
    global _REGISTRY
    _REGISTRY = None
