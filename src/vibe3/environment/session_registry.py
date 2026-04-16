"""Session registry service: reserve, track, and reconcile runtime sessions."""

import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients.protocols import BackendProtocol
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.session_naming import build_session_name

# All supported execution roles (L1/L2/L3 chains)
WORKER_ROLES = frozenset(
    {"manager", "planner", "executor", "reviewer", "supervisor", "governance"}
)


class SessionRegistryService:
    """Centralises session lifecycle: naming, status transitions, and liveness.

    ## Backend Parameter Contract

    The `backend` parameter controls liveness verification behavior:

    - **backend=None**: Read-only mode. Assumes all tmux sessions exist.
      Use ONLY for queries that don't affect capacity checks or dispatch gates.
      Example: `load_session_id()` reading resume hints.

    - **backend=CodeagentBackend()**: Full liveness verification.
      REQUIRED for capacity checks, dispatch gates, and state reconciliation.
      Example: `ExecutionCoordinator`, `GlobalDispatchCoordinator`.

    **WARNING**: Using backend=None in capacity/dispatch logic will cause
    false positives (treating dead sessions as live), leading to queue starvation.
    """

    def __init__(
        self,
        store: SQLiteClient,
        backend: BackendProtocol | None = None,
    ) -> None:
        self._store = store
        self._backend = backend

    def _has_tmux_session(self, tmux: str) -> bool:
        """Check if tmux session exists.

        In read-only mode (backend=None), assumes True to avoid false negatives
        in query scenarios. This is safe only for non-capacity logic.
        """
        if self._backend is None:
            return True
        return self._backend.has_tmux_session(tmux)

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

    def mark_aborted(self, session_id: int) -> None:
        """Mark a session as aborted (user-initiated termination)."""
        self._store.update_runtime_session(
            session_id, status="aborted", ended_at=_now_iso()
        )

    def mark_failed(self, session_id: int) -> None:
        """Mark a session as failed (unsuccessful execution)."""
        self._store.update_runtime_session(
            session_id, status="failed", ended_at=_now_iso()
        )

    def count_live_worker_sessions(self, *, role: str | None = None) -> int:
        """Count truly live worker sessions.

        Rules:
        - Only considers sessions in starting|running status.
        - Excludes governance role (governance uses separate capacity pool).
        - For sessions with a tmux_session, confirms liveness via backend.
        - Sessions still in starting with no tmux_session are counted as live
          only if recently created (< 60s); stale sessions are marked orphaned.
        """
        if self._backend is None:
            logger.bind(
                domain="session_registry",
                mode="read_only",
            ).warning(
                "count_live_worker_sessions called with backend=None; "
                "results may include dead sessions. This is incorrect for "
                "capacity checks. Use backend=CodeagentBackend() instead."
            )
        sessions = self._store.list_live_runtime_sessions(role=role)
        count = 0
        now = datetime.datetime.now()
        starting_timeout_seconds = 60

        for session in sessions:
            session_role = session.get("role", "")
            # Exclude governance (has separate capacity pool)
            if session_role == "governance":
                continue
            if session_role not in WORKER_ROLES:
                continue
            tmux = session.get("tmux_session")
            if tmux:
                if self._has_tmux_session(tmux):
                    count += 1
            else:
                # No tmux_session - check if it's a stale session
                created_at_str = session.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.datetime.fromisoformat(created_at_str)
                        age_seconds = (now - created_at).total_seconds()
                        if age_seconds > starting_timeout_seconds:
                            # Mark stale session as orphaned
                            session_id = session.get("id")
                            if session_id:
                                self._store.update_runtime_session(
                                    session_id,
                                    status="orphaned",
                                    ended_at=now.isoformat(),
                                )
                                logger.bind(
                                    domain="session_registry",
                                    session_id=session_id,
                                    age_seconds=age_seconds,
                                ).warning(
                                    f"Session {session_id} marked orphaned: "
                                    f"no tmux after {age_seconds:.0f}s"
                                )
                            # Don't count - it's failed, not starting
                            continue
                    except Exception as exc:
                        logger.bind(
                            domain="session_registry",
                            session=session,
                        ).warning(f"Failed to parse created_at timestamp: {exc}")
                # Recently created, no tmux yet - count as live
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
                if self._has_tmux_session(tmux):
                    count += 1
            else:
                # Still starting, no tmux yet - count as live
                count += 1
        return count

    def list_live_governance_sessions(self) -> list[dict[str, Any]]:
        """List truly live governance sessions with tmux liveness check.

        Returns sessions with role='governance' in starting|running status,
        confirming liveness via tmux when a session name is available.

        Returns:
            List of session dicts that are truly live.
        """
        sessions = self._store.list_live_runtime_sessions(role="governance")
        truly_live: list[dict[str, Any]] = []
        for session in sessions:
            tmux = session.get("tmux_session")
            if tmux:
                if self._has_tmux_session(tmux):
                    truly_live.append(session)
            else:
                # Still starting, no tmux yet - count as live
                truly_live.append(session)
        return truly_live

    def mark_governance_sessions_done_when_tmux_gone(self) -> list[int]:
        """Mark governance sessions whose tmux is gone as done.

        Unlike reconcile_live_state which marks as orphaned,
        this method marks governance sessions as 'done' because
        normal governance completion should be reflected as done.

        Returns:
            List of session_ids that were transitioned to done.
        """
        sessions = self._store.list_live_runtime_sessions(role="governance")
        done_ids: list[int] = []
        for session in sessions:
            tmux = session.get("tmux_session")
            if not tmux:
                # No tmux assigned yet - not complete
                continue
            if not self._has_tmux_session(tmux):
                session_id = session["id"]
                self._store.update_runtime_session(
                    session_id, status="done", ended_at=_now_iso()
                )
                done_ids.append(session_id)
        return done_ids

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
            if not self._has_tmux_session(tmux):
                session_id = session["id"]
                self._store.update_runtime_session(
                    session_id, status="orphaned", ended_at=_now_iso()
                )
                self._cleanup_orphaned_session_resources(session)
                orphaned_ids.append(session_id)
        return orphaned_ids

    def _cleanup_orphaned_session_resources(self, session: dict[str, Any]) -> None:
        """Best-effort cleanup for resources owned by a dead session."""
        role = str(session.get("role") or "")
        if role != "supervisor":
            return

        target_id = str(session.get("target_id") or "").strip()
        if not target_id:
            return

        try:
            from vibe3.clients.git_client import GitClient
            from vibe3.environment.worktree import WorktreeContext, WorktreeManager
            from vibe3.models.orchestra_config import OrchestraConfig

            git_common_dir = GitClient().get_git_common_dir()
            repo_root = Path(git_common_dir).parent if git_common_dir else Path.cwd()
            config = OrchestraConfig.from_settings()
            context = WorktreeContext(
                path=repo_root / ".worktrees" / "tmp" / target_id,
                is_temporary=True,
                issue_number=int(target_id),
            )
            WorktreeManager(config, repo_root).release_temporary_worktree(context)
        except Exception:
            # Best-effort cleanup only; orphan reconciliation should still succeed.
            pass

    def get_truly_live_sessions_for_branch(self, branch: str) -> list[dict[str, Any]]:
        """Return truly live sessions for a branch, confirming tmux liveness.

        Unlike list_live_runtime_sessions which only checks status,
        this method confirms tmux liveness for each session.

        Sessions in starting status with no tmux_session are included
        only if recently created (< 60s); stale sessions are marked orphaned.

        Args:
            branch: The branch to filter sessions by.

        Returns:
            List of session dicts that are truly live.
        """
        sessions = self._store.list_live_runtime_sessions()
        truly_live: list[dict[str, Any]] = []
        now = datetime.datetime.now()
        starting_timeout_seconds = 60

        for session in sessions:
            if session.get("branch") != branch:
                continue
            tmux = session.get("tmux_session")
            if tmux:
                if self._has_tmux_session(tmux):
                    truly_live.append(session)
            else:
                # No tmux_session field - check if it's truly still starting
                created_at_str = session.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.datetime.fromisoformat(created_at_str)
                        age_seconds = (now - created_at).total_seconds()
                        if age_seconds > starting_timeout_seconds:
                            # Mark stale session as orphaned
                            session_id = session.get("id")
                            if session_id:
                                self._store.update_runtime_session(
                                    session_id,
                                    status="orphaned",
                                    ended_at=now.isoformat(),
                                )
                                logger.bind(
                                    domain="session_registry",
                                    session_id=session_id,
                                    age_seconds=age_seconds,
                                ).warning(
                                    f"Session {session_id} marked orphaned: "
                                    f"no tmux after {age_seconds:.0f}s"
                                )
                            continue
                    except Exception as exc:
                        logger.bind(
                            domain="session_registry",
                            session=session,
                        ).warning(f"Failed to parse created_at timestamp: {exc}")
                # Recently created, no tmux yet - count as live
                truly_live.append(session)
        return truly_live

    def get_truly_live_sessions_for_target(
        self, role: str, branch: str, target_id: str
    ) -> list[dict[str, Any]]:
        """Return truly live sessions matching role + branch + target_id.

        This is the canonical method for checking if a specific execution
        context has a live session, with proper tmux liveness verification.

        Args:
            role: The session role (e.g., 'planner', 'executor', 'reviewer').
            branch: The branch to filter sessions by.
            target_id: The target ID (e.g., issue number as string).

        Returns:
            List of session dicts that are truly live and match all criteria.
        """
        sessions = self._store.list_live_runtime_sessions(role=role)
        from loguru import logger

        truly_live: list[dict[str, Any]] = []
        now = datetime.datetime.now()
        # Timeout threshold: sessions without tmux for longer than this are
        # considered failed launches, not "still starting"
        starting_timeout_seconds = 60

        for session in sessions:
            if session.get("branch") != branch:
                continue
            if session.get("target_id") != target_id:
                continue
            tmux = session.get("tmux_session")
            if tmux:
                if self._has_tmux_session(tmux):
                    truly_live.append(session)
            else:
                # No tmux_session field - check if it's truly still starting
                # or if it's a stale session from a failed launch
                created_at_str = session.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.datetime.fromisoformat(created_at_str)
                        age_seconds = (now - created_at).total_seconds()
                        if age_seconds > starting_timeout_seconds:
                            # Session created too long ago without tmux - failed launch
                            # Mark as orphaned to prevent future false positives
                            session_id = session.get("id")
                            if session_id:
                                self._store.update_runtime_session(
                                    session_id,
                                    status="orphaned",
                                    ended_at=now.isoformat(),
                                )
                                logger.bind(
                                    domain="session_registry",
                                    session_id=session_id,
                                    role=role,
                                    target_id=target_id,
                                    age_seconds=age_seconds,
                                ).warning(
                                    f"Session {session_id} marked orphaned: "
                                    f"no tmux after {age_seconds:.0f}s"
                                )
                            # Don't add to truly_live - it's failed, not starting
                            continue
                    except Exception as exc:
                        logger.bind(
                            domain="session_registry",
                            session=session,
                        ).warning(f"Failed to parse created_at timestamp: {exc}")
                # Recently created, no tmux yet - count as live (still starting)
                truly_live.append(session)
        return truly_live

    def clear_all_sessions(self) -> int:
        """Mark ALL active sessions as stopped. Called on server start and stop.

        Unconditionally marks every starting|running session as stopped.

        Design: server lifecycle owns session state. When the server starts or
        stops, all sessions from the previous run are considered ended. The tmux
        processes are NOT killed -- agents may continue running and writing results
        -- but from the capacity/dispatch perspective the slots are fully released.

        Returns:
            Number of sessions cleared.
        """
        sessions = self._store.list_live_runtime_sessions()
        cleared = 0
        for session in sessions:
            session_id = session.get("id")
            if session_id is not None:
                self._store.update_runtime_session(int(session_id), status="stopped")
                cleared += 1
                logger.bind(
                    domain="session_registry",
                    session_id=session_id,
                    tmux=session.get("tmux_session"),
                    role=session.get("role"),
                ).debug(f"clear_all_sessions: marked session {session_id} as stopped")
        if cleared:
            logger.bind(domain="session_registry", cleared=cleared).info(
                f"Server lifecycle cleanup: {cleared} sessions marked stopped "
                f"(tmux may still be running)"
            )
        return cleared


def _now_iso() -> str:
    return datetime.datetime.now().isoformat()
