"""Shared helpers for execution lifecycle events."""

from datetime import datetime
from typing import Literal

from vibe3.clients.sqlite_client import SQLiteClient

ExecutionRole = Literal["planner", "executor", "reviewer"]
ExecutionLifecycleEvent = Literal["started", "completed", "aborted"]

_ROLE_PREFIX: dict[ExecutionRole, str] = {
    "planner": "plan",
    "executor": "run",
    "reviewer": "review",
}

_ROLE_STATUS_FIELD: dict[ExecutionRole, str] = {
    "planner": "planner_status",
    "executor": "executor_status",
    "reviewer": "reviewer_status",
}

_ROLE_ACTOR_FIELD: dict[ExecutionRole, str] = {
    "planner": "planner_actor",
    "executor": "executor_actor",
    "reviewer": "reviewer_actor",
}

_ROLE_SESSION_FIELD: dict[ExecutionRole, str] = {
    "planner": "planner_session_id",
    "executor": "executor_session_id",
    "reviewer": "reviewer_session_id",
}


def execution_prefix(role: ExecutionRole) -> str:
    """Return the lifecycle prefix for a role."""
    return _ROLE_PREFIX[role]


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
) -> None:
    """Persist lifecycle state and timeline event for an execution role."""
    now = datetime.now().isoformat()
    status_field = _ROLE_STATUS_FIELD[role]

    if lifecycle == "started":
        status = "running"
        state_updates: dict[str, object] = {
            status_field: status,
            "execution_started_at": now,
            "execution_completed_at": None,
        }
    elif lifecycle == "completed":
        status = "done"
        state_updates = {
            status_field: status,
            "execution_completed_at": now,
            "execution_pid": None,
        }
    else:
        status = "crashed"
        state_updates = {
            status_field: status,
            "execution_completed_at": now,
            "execution_pid": None,
        }

    state_updates[_ROLE_ACTOR_FIELD[role]] = actor
    if session_id:
        state_updates[_ROLE_SESSION_FIELD[role]] = session_id
    if extra_state_updates:
        state_updates.update(extra_state_updates)

    store.update_flow_state(branch, **state_updates)
    store.add_event(
        branch,
        f"{execution_prefix(role)}_{lifecycle}",
        actor,
        detail=detail,
        refs=refs,
    )
