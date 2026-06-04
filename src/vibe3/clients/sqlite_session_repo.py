"""SQLite repository methods for runtime session persistence."""

import datetime
import sqlite3
from typing import Any

from loguru import logger

from vibe3.clients.sqlite_base import _HasConnection


class SQLiteSessionRepo(_HasConnection):
    """Runtime session CRUD operations."""

    db_path: str

    VALID_RUNTIME_SESSION_FIELDS = {
        "role",
        "target_type",
        "target_id",
        "branch",
        "session_name",
        "backend_session_id",
        "tmux_session",
        "log_path",
        "status",
        "started_at",
        "ended_at",
        "worktree_path",
        "created_at",
        "updated_at",
    }

    def create_runtime_session(
        self,
        *,
        role: str,
        target_type: str,
        target_id: str,
        branch: str,
        session_name: str,
        status: str = "starting",
        **kwargs: Any,
    ) -> int:
        now = datetime.datetime.now().isoformat()
        row: dict[str, Any] = {
            "role": role,
            "target_type": target_type,
            "target_id": target_id,
            "branch": branch,
            "session_name": session_name,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        extra_valid = self.VALID_RUNTIME_SESSION_FIELDS - row.keys()
        for key, value in kwargs.items():
            if key in extra_valid:
                row[key] = value
        columns = ", ".join(row.keys())
        placeholders = ", ".join(["?"] * len(row))
        values = list(row.values())
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                f"INSERT INTO runtime_session ({columns}) VALUES ({placeholders})",
                values,
            )
            last_id = cursor.lastrowid
        if last_id is None:
            raise RuntimeError("Failed to insert runtime_session: no lastrowid")
        session_id = int(last_id)
        logger.bind(
            external="sqlite",
            operation="create_runtime_session",
            role=role,
            branch=branch,
            session_id=session_id,
        ).debug("Created runtime session")
        return session_id

    def get_runtime_session(self, session_id: int) -> dict[str, Any] | None:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM runtime_session WHERE id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def update_runtime_session(self, session_id: int, **kwargs: Any) -> None:
        invalid = set(kwargs.keys()) - self.VALID_RUNTIME_SESSION_FIELDS
        if invalid:
            raise ValueError(f"Invalid runtime_session fields: {invalid}")
        if not kwargs:
            return
        kwargs["updated_at"] = datetime.datetime.now().isoformat()
        set_clause = ", ".join([f"{f} = ?" for f in kwargs])
        values = list(kwargs.values()) + [session_id]
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE runtime_session SET {set_clause} WHERE id = ?",
                values,
            )
        logger.bind(
            external="sqlite",
            operation="update_runtime_session",
            session_id=session_id,
            fields=list(kwargs.keys()),
        ).debug("Updated runtime session")

    def list_live_runtime_sessions(
        self, *, role: str | None = None
    ) -> list[dict[str, Any]]:
        params: list[Any] = ["starting", "running"]
        query = "SELECT * FROM runtime_session WHERE status IN (?, ?)"
        if role is not None:
            query += " AND role = ?"
            params.append(role)
        query += " ORDER BY created_at DESC"
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        logger.bind(
            external="sqlite",
            operation="list_live_runtime_sessions",
            role=role,
            count=len(rows),
        ).debug("Listed live runtime sessions")
        return rows

    def list_live_sessions_by_worktree(
        self, worktree_path: str
    ) -> list[dict[str, Any]]:
        """List truly live sessions for a specific worktree path.

        Args:
            worktree_path: Absolute path to worktree directory

        Returns:
            List of session dicts with status in (starting, running)
        """
        query = (
            "SELECT * FROM runtime_session "
            "WHERE worktree_path = ? AND status IN (?, ?) "
            "ORDER BY created_at DESC"
        )
        params = [worktree_path, "starting", "running"]
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
        logger.bind(
            external="sqlite",
            operation="list_live_sessions_by_worktree",
            worktree_path=worktree_path,
            count=len(rows),
        ).debug("Listed live sessions for worktree")
        return rows

    def get_terminated_target_ids_for_role(
        self, role: str, target_ids: set[int]
    ) -> set[int]:
        """Return subset of target_ids that have terminal-state sessions for role.

        Terminal states: orphaned, done, failed, stopped, aborted.
        Used by reconcile_in_flight() to prune in-flight markers for targets
        whose sessions completed or died without being observed as live.
        """
        if not target_ids:
            return set()
        terminal_statuses = ("orphaned", "done", "failed", "stopped", "aborted")
        target_strs = [str(t) for t in target_ids]
        target_placeholders = ",".join("?" * len(target_strs))
        status_placeholders = ",".join("?" * len(terminal_statuses))
        query = (
            f"SELECT DISTINCT target_id FROM runtime_session "
            f"WHERE role = ? AND target_id IN ({target_placeholders}) "
            f"AND status IN ({status_placeholders})"
        )
        params: list[Any] = [role] + target_strs + list(terminal_statuses)
        result: set[int] = set()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        for row in cursor.fetchall():
            raw = row[0]
            if raw is not None:
                try:
                    result.add(int(raw))
                except (ValueError, TypeError):
                    pass
        return result

    def get_latest_session_with_backend_id(
        self, *, branch: str, role: str
    ) -> dict[str, Any] | None:
        """Return the most recent session for branch+role with a backend_session_id.

        Queries across all statuses (live and terminal), ordered by created_at DESC.
        Used by load_session_id() as a fallback when no live session has a
        backend_session_id.
        """
        query = (
            "SELECT * FROM runtime_session "
            "WHERE branch = ? AND role = ? AND backend_session_id IS NOT NULL "
            "AND backend_session_id != '' "
            "ORDER BY created_at DESC LIMIT 1"
        )
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, (branch, role))
        row = cursor.fetchone()
        return dict(row) if row else None
