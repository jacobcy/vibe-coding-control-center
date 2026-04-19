"""Shared helpers for execution lifecycle events."""

import re
from datetime import datetime
from typing import Literal

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient

ExecutionRole = Literal[
    "planner", "executor", "reviewer", "manager", "supervisor", "governance"
]
ExecutionLifecycleEvent = Literal["started", "completed", "aborted", "failed"]

_ROLE_PREFIX: dict[ExecutionRole, str] = {
    "planner": "plan",
    "executor": "run",
    "reviewer": "review",
    "manager": "manager",
    "supervisor": "supervisor",
    "governance": "governance",
}

_ROLE_STATUS_FIELD: dict[ExecutionRole, str | None] = {
    "planner": "planner_status",
    "executor": "executor_status",
    "reviewer": "reviewer_status",
    "manager": None,
    "supervisor": None,
    "governance": None,
}

_ROLE_ACTOR_FIELD: dict[ExecutionRole, str | None] = {
    "planner": "planner_actor",
    "executor": "executor_actor",
    "reviewer": "reviewer_actor",
    "manager": None,
    "supervisor": None,
    "governance": None,
}


def execution_prefix(role: ExecutionRole) -> str:
    """Return the lifecycle prefix for a role."""
    return _ROLE_PREFIX[role]


class ExecutionLifecycleService:
    """Unified execution lifecycle recording for all roles."""

    def __init__(self, store: SQLiteClient) -> None:
        self._store = store

    def record_started(
        self,
        role: ExecutionRole,
        target: str,
        actor: str,
        session_id: str | None = None,
        refs: dict[str, str] | None = None,
        *,
        event_type: str | None = None,
    ) -> None:
        # Determine appropriate detail based on actor type
        # orchestra: prefix indicates dispatch intent, not execution start
        if actor.startswith("orchestra:"):
            detail = f"{role} dispatched"
        else:
            detail = f"{role} execution started"

        persist_execution_lifecycle_event(
            store=self._store,
            branch=target,
            role=role,
            lifecycle="started",
            actor=actor,
            detail=detail,
            session_id=session_id,
            refs=refs,
            event_type=event_type,
        )

    def record_completed(
        self,
        role: ExecutionRole,
        target: str,
        actor: str,
        detail: str | None = None,
        refs: dict[str, str] | None = None,
        *,
        event_type: str | None = None,
    ) -> None:
        persist_execution_lifecycle_event(
            store=self._store,
            branch=target,
            role=role,
            lifecycle="completed",
            actor=actor,
            detail=detail or f"{role} execution completed",
            refs=refs,
            event_type=event_type,
        )

    def record_failed(
        self,
        role: ExecutionRole,
        target: str,
        actor: str,
        error: str | None = None,
        refs: dict[str, str] | None = None,
        *,
        event_type: str | None = None,
    ) -> None:
        persist_execution_lifecycle_event(
            store=self._store,
            branch=target,
            role=role,
            lifecycle="aborted",
            actor=actor,
            detail=error or f"{role} execution failed",
            refs=refs,
            event_type=event_type,
        )


def _parse_branch_target(branch: str) -> tuple[str, str]:
    """Extract (target_type, target_id) from branch name."""
    match = re.search(r"issue-(\d+)", branch)
    if match:
        return ("issue", match.group(1))
    return ("branch", branch)


def _sync_registry_from_lifecycle_event(
    store: SQLiteClient,
    branch: str,
    role: ExecutionRole,
    lifecycle: ExecutionLifecycleEvent,
    session_id: str | None,
    refs: dict[str, str] | None = None,
) -> None:
    """Sync runtime_session registry based on lifecycle event."""
    if lifecycle == "started":
        tmux_session = None
        if refs:
            candidate = refs.get("tmux_session")
            if isinstance(candidate, str) and candidate.strip():
                tmux_session = candidate.strip()

        live_sessions = store.list_live_runtime_sessions(role=role)
        for session in live_sessions:
            if session.get("branch") == branch:
                if tmux_session and not session.get("tmux_session"):
                    store.update_runtime_session(
                        session["id"],
                        tmux_session=tmux_session,
                    )
                logger.bind(
                    domain="execution_lifecycle",
                    branch=branch,
                    role=role,
                ).warning(
                    f"Live session already exists for {role}+{branch}, "
                    "skipping duplicate creation"
                )
                return

        target_type, target_id = _parse_branch_target(branch)
        session_name = f"vibe3-{role}-{target_type}-{target_id}"
        store.create_runtime_session(
            role=role,
            target_type=target_type,
            target_id=target_id,
            branch=branch,
            session_name=session_name,
            status="running",
            backend_session_id=session_id,
            tmux_session=tmux_session,
            started_at=datetime.now().isoformat(),
        )
        return

    terminal_status = {
        "completed": "done",
        "aborted": "aborted",
        "failed": "failed",
    }.get(lifecycle, "failed")
    live_sessions = store.list_live_runtime_sessions(role=role)
    for session in live_sessions:
        if session.get("branch") == branch:
            store.update_runtime_session(
                session["id"],
                status=terminal_status,
                ended_at=datetime.now().isoformat(),
            )


def persist_execution_lifecycle_event(
    store: SQLiteClient,
    branch: str,
    role: ExecutionRole,
    lifecycle: ExecutionLifecycleEvent,
    actor: str,
    detail: str,
    session_id: str | None = None,
    refs: dict[str, str] | None = None,
    extra_state_updates: dict[str, object] | None = None,
    event_type: str | None = None,
) -> None:
    """Persist lifecycle state and timeline event for an execution role."""
    now = datetime.now().isoformat()
    state_updates: dict[str, object] = {}

    if lifecycle == "started":
        state_updates["execution_started_at"] = now
        # Update role status to running
        status_field = _ROLE_STATUS_FIELD[role]
        if status_field:
            state_updates[status_field] = "running"
    elif lifecycle == "completed":
        state_updates["execution_completed_at"] = now
        state_updates["execution_pid"] = None
        # Update role status to completed
        status_field = _ROLE_STATUS_FIELD[role]
        if status_field:
            state_updates[status_field] = "completed"
    else:
        state_updates["execution_completed_at"] = now
        state_updates["execution_pid"] = None
        # Update role status to lifecycle value (aborted/failed)
        status_field = _ROLE_STATUS_FIELD[role]
        if status_field:
            state_updates[status_field] = lifecycle

        actor_field = _ROLE_ACTOR_FIELD[role]
        if actor_field:
            state_updates[actor_field] = actor

    if extra_state_updates:
        state_updates.update(extra_state_updates)

    if state_updates:
        store.update_flow_state(branch, **state_updates)

    resolved_event_type = event_type or f"{execution_prefix(role)}_{lifecycle}"
    store.add_event(
        branch,
        resolved_event_type,
        actor,
        detail=detail,
        refs=refs,
    )
    _sync_registry_from_lifecycle_event(
        store,
        branch,
        role,
        lifecycle,
        session_id,
        refs=refs,
    )
