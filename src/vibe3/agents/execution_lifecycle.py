"""Shared helpers for execution lifecycle events."""

import re
from datetime import datetime
from typing import Literal

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient

# Extended to support all orchestration roles
ExecutionRole = Literal[
    "planner", "executor", "reviewer", "manager", "supervisor", "governance"
]
ExecutionLifecycleEvent = Literal["started", "completed", "aborted", "failed"]

# Role prefixes for event naming
_ROLE_PREFIX: dict[ExecutionRole, str] = {
    "planner": "plan",
    "executor": "run",
    "reviewer": "review",
    "manager": "manager",
    "supervisor": "supervisor",
    "governance": "governance",
}

# Status fields for L3 agent roles (planner/executor/reviewer)
_ROLE_STATUS_FIELD: dict[ExecutionRole, str | None] = {
    "planner": "planner_status",
    "executor": "executor_status",
    "reviewer": "reviewer_status",
    "manager": None,  # Manager doesn't write to flow_state
    "supervisor": None,  # Supervisor doesn't write to flow_state
    "governance": None,  # Governance doesn't write to flow_state
}

# Actor fields for L3 agent roles
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
    """Unified execution lifecycle recording for all roles.

    提供统一的生命周期记录接口，避免每个链路重复实现。
    支持 manager、supervisor、governance、planner、executor、reviewer。
    """

    def __init__(self, store: SQLiteClient) -> None:
        """Initialize with SQLite store.

        Args:
            store: SQLiteClient instance for persistence
        """
        self._store = store

    def record_started(
        self,
        role: ExecutionRole,
        target: str,
        actor: str,
        session_id: str | None = None,
        refs: dict[str, str] | None = None,
    ) -> None:
        """Record execution started event.

        Args:
            role: Execution role (manager/planner/executor/reviewer/
                supervisor/governance)
            target: Target identifier (usually branch name)
            actor: Actor who initiated the execution
            session_id: Optional backend session ID
            refs: Optional reference dict (e.g., tmux_session)
        """
        persist_execution_lifecycle_event(
            store=self._store,
            branch=target,
            role=role,
            lifecycle="started",
            actor=actor,
            detail=f"{role} execution started",
            session_id=session_id,
            refs=refs,
        )

    def record_completed(
        self,
        role: ExecutionRole,
        target: str,
        actor: str,
        detail: str | None = None,
        refs: dict[str, str] | None = None,
    ) -> None:
        """Record execution completed event.

        Args:
            role: Execution role
            target: Target identifier
            actor: Actor who completed the execution
            detail: Optional detail message
            refs: Optional reference dict
        """
        persist_execution_lifecycle_event(
            store=self._store,
            branch=target,
            role=role,
            lifecycle="completed",
            actor=actor,
            detail=detail or f"{role} execution completed",
            refs=refs,
        )

    def record_failed(
        self,
        role: ExecutionRole,
        target: str,
        actor: str,
        error: str | None = None,
        refs: dict[str, str] | None = None,
    ) -> None:
        """Record execution failed event.

        Args:
            role: Execution role
            target: Target identifier
            actor: Actor when execution failed
            error: Optional error message
            refs: Optional reference dict
        """
        persist_execution_lifecycle_event(
            store=self._store,
            branch=target,
            role=role,
            lifecycle="aborted",  # Use aborted for failed state
            actor=actor,
            detail=error or f"{role} execution failed",
            refs=refs,
        )


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
    refs: dict[str, str] | None = None,
) -> None:
    """Sync runtime_session registry based on lifecycle event.

    - started  -> create a new running session in registry
    - completed -> mark the live session for this branch+role as done
    - aborted/failed -> mark the live session for this branch+role as aborted
    """
    if lifecycle == "started":
        tmux_session = None
        if refs:
            candidate = refs.get("tmux_session")
            if isinstance(candidate, str) and candidate.strip():
                tmux_session = candidate.strip()

        # Check if a live session already exists for this branch+role
        live_sessions = store.list_live_runtime_sessions(role=role)
        for session in live_sessions:
            if session.get("branch") == branch:
                # Already have a live session for this context.
                # If the parent async launcher now knows the tmux session, bind it
                # so later liveness reconciliation can track the real wrapper.
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
            tmux_session=tmux_session,
            started_at=datetime.now().isoformat(),
        )
        return

    # terminal events: find live sessions for this branch+role and close them
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
) -> None:
    """Persist lifecycle state and timeline event for an execution role.

    Terminal events (completed/aborted) no longer write to legacy session_id fields.
    The runtime_session registry is the single source of truth for session tracking.
    """
    now = datetime.now().isoformat()
    status_field = _ROLE_STATUS_FIELD[role]

    # Only update flow_state for L3 agent roles (planner/executor/reviewer)
    state_updates: dict[str, object] = {}

    if status_field:  # L3 agent role
        if lifecycle == "started":
            status = "running"
            state_updates[status_field] = status
            state_updates["execution_started_at"] = now
            state_updates["execution_completed_at"] = None
        elif lifecycle == "completed":
            status = "done"
            state_updates[status_field] = status
            state_updates["execution_completed_at"] = now
            state_updates["execution_pid"] = None
        else:  # aborted or failed
            status = "crashed"
            state_updates[status_field] = status
            state_updates["execution_completed_at"] = now
            state_updates["execution_pid"] = None

        # Update actor field for L3 roles
        actor_field = _ROLE_ACTOR_FIELD[role]
        if actor_field:
            state_updates[actor_field] = actor

    if extra_state_updates:
        state_updates.update(extra_state_updates)

    # Only update flow_state if we have updates
    if state_updates:
        store.update_flow_state(branch, **state_updates)

    store.add_event(
        branch,
        f"{execution_prefix(role)}_{lifecycle}",
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
