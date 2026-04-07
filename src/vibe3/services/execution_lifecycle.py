"""Shared helpers for execution lifecycle events."""

import re
from datetime import datetime
from typing import Literal

from loguru import logger

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


def execution_prefix(role: ExecutionRole) -> str:
    """Return the lifecycle prefix for a role."""
    return _ROLE_PREFIX[role]


def _parse_branch_target(branch: str) -> tuple[str, str]:
    """Extract (target_type, target_id) from branch name.

    Examples:
      task/issue-42  -> ("issue", "42")
      dev/issue-123  -> ("issue", "123")
      other-branch   -> ("branch", branch)
    """
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
) -> None:
    """Sync runtime_session registry based on lifecycle event.

    - started  -> create a new running session in registry
    - completed -> mark the live session for this branch+role as done
    - aborted   -> mark the live session for this branch+role as aborted
    """
    if lifecycle == "started":
        # Check if a live session already exists for this branch+role
        live_sessions = store.list_live_runtime_sessions(role=role)
        for session in live_sessions:
            if session.get("branch") == branch:
                # Already have a live session for this context
                # Skip creation to avoid duplicates
                logger.bind(
                    domain="execution_lifecycle",
                    branch=branch,
                    role=role,
                ).warning(
                    f"Live session already exists for {role}+{branch}, "
                    "skipping duplicate creation"
                )
                return

        # No duplicate found, proceed with creation
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
        )
        return

    # terminal events: find live sessions for this branch+role and close them
    terminal_status = {
        "completed": "done",
        "aborted": "aborted",
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
) -> None:
    """Persist lifecycle state and timeline event for an execution role.

    Terminal events (completed/aborted) no longer write to legacy session_id fields.
    The runtime_session registry is the single source of truth for session tracking.
    """
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
    _sync_registry_from_lifecycle_event(store, branch, role, lifecycle, session_id)
