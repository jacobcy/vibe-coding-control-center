"""Session registry service: reserve, track, and reconcile runtime sessions."""

import datetime
from typing import Any

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.manager.session_naming import build_session_name

WORKER_ROLES = frozenset({"manager", "planner", "executor", "reviewer"})


class SessionRegistryService:
    """Centralises session lifecycle: naming, status transitions, and liveness."""

    def __init__(self, store: SQLiteClient, backend: CodeagentBackend) -> None:
        self._store = store
        self._backend = backend

    def reserve(
        self,
        role: str,
        target_type: str,
        target_id: str,
        branch: str,
        **kwargs: Any,
    ) -> int:
        """Pre-register a session before tmux is started.

        Returns:
            The newly created session_id.
        """
        session_name = build_session_name(role, target_type, target_id)
        return self._store.create_runtime_session(
            role=role,
            target_type=target_type,
            target_id=target_id,
            branch=branch,
            session_name=session_name,
            status="starting",
            **kwargs,
        )

    def mark_started(
        self, session_id: int, tmux_session: str | None = None, **kwargs: Any
    ) -> None:
        """Mark a session as running after tmux has launched."""
        updates: dict[str, Any] = {"status": "running", "started_at": _now_iso()}
        if tmux_session is not None:
            updates["tmux_session"] = tmux_session
        updates.update(kwargs)
        self._store.update_runtime_session(session_id, **updates)

    def mark_finished(self, session_id: int, success: bool = True) -> None:
        """Mark a session as done or failed."""
        status = "done" if success else "failed"
        self._store.update_runtime_session(
            session_id, status=status, ended_at=_now_iso()
        )

    def count_live_worker_sessions(self, *, role: str | None = None) -> int:
        """Count truly live worker sessions.

        Rules:
        - Only considers sessions in starting|running status.
        - Excludes governance role.
        - For sessions with a tmux_session, confirms liveness via backend.
        - Sessions still in starting with no tmux_session are counted as live.
        """
        sessions = self._store.list_live_runtime_sessions(role=role)
        count = 0
        for session in sessions:
            session_role = session.get("role", "")
            if session_role not in WORKER_ROLES:
                continue
            tmux = session.get("tmux_session")
            if tmux:
                if self._backend.has_tmux_session(tmux):
                    count += 1
            else:
                # Still starting, no tmux yet - count as live
                count += 1
        return count

    def count_live_governance_sessions(self) -> int:
        """Count truly live governance sessions.

        Checks sessions with role='governance' in starting|running status,
        confirming liveness via tmux when a session name is available.
        """
        sessions = self._store.list_live_runtime_sessions(role="governance")
        count = 0
        for session in sessions:
            tmux = session.get("tmux_session")
            if tmux:
                if self._backend.has_tmux_session(tmux):
                    count += 1
            else:
                # Still starting, no tmux yet - count as live
                count += 1
        return count

    def reconcile_live_state(self) -> list[int]:
        """Mark starting|running sessions whose tmux is gone as orphaned.

        Sessions in starting status with no tmux_session are left untouched.

        Returns:
            List of session_ids that were transitioned to orphaned.
        """
        sessions = self._store.list_live_runtime_sessions()
        orphaned_ids: list[int] = []
        for session in sessions:
            tmux = session.get("tmux_session")
            if not tmux:
                # No tmux assigned yet - not orphanable
                continue
            if not self._backend.has_tmux_session(tmux):
                session_id = session["id"]
                self._store.update_runtime_session(
                    session_id, status="orphaned", ended_at=_now_iso()
                )
                orphaned_ids.append(session_id)
        return orphaned_ids


def _now_iso() -> str:
    return datetime.datetime.now().isoformat()
