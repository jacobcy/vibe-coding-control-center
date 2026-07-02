"""SQLite repository for transition_history table."""

import json
import sqlite3
from typing import Literal

from vibe3.clients.sqlite_base import _utcnow_iso


class SQLiteTransitionHistoryRepo:
    """Mixin providing transition_history query methods."""

    db_path: str

    def _get_connection(self) -> sqlite3.Connection:
        raise NotImplementedError

    def count_transition_pairs(
        self, conn: sqlite3.Connection, branch: str
    ) -> dict[tuple[str, str], int]:
        """Count occurrences of each (from_state, to_state) pair for a branch.

        Returns:
            Dict mapping (from_state, to_state) tuples to occurrence counts.
            Example: {("state/handoff", "state/in-progress"): 5}
        """
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT from_state, to_state, COUNT(*) as count
            FROM transition_history
            WHERE branch = ?
            GROUP BY from_state, to_state
            ORDER BY count DESC
            """,
            (branch,),
        ).fetchall()

        return {(row[0], row[1]): row[2] for row in rows}

    def get_top_transition_pairs(
        self,
        conn: sqlite3.Connection,
        branch: str,
        limit: Literal[3, 5, 10] = 5,
    ) -> list[dict[str, int | str]]:
        """Get top N most frequent transition pairs for a branch.

        Args:
            branch: Flow branch name
            limit: Number of top pairs to return (default 5)

        Returns:
            List of dicts with keys: from_state, to_state, count
        """
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT from_state, to_state, COUNT(*) as count
            FROM transition_history
            WHERE branch = ?
            GROUP BY from_state, to_state
            ORDER BY count DESC
            LIMIT ?
            """,
            (branch, limit),
        ).fetchall()

        return [
            {"from_state": row[0], "to_state": row[1], "count": row[2]} for row in rows
        ]

    def count_specific_pair(
        self,
        conn: sqlite3.Connection,
        branch: str,
        from_state: str,
        to_state: str,
    ) -> int:
        """Count occurrences of a specific transition pair.

        Args:
            branch: Flow branch name
            from_state: Source state label (e.g., "state/handoff")
            to_state: Target state label (e.g., "state/in-progress")

        Returns:
            Number of times this exact pair has occurred
        """
        cursor = conn.cursor()
        row = cursor.execute(
            """
            SELECT COUNT(*)
            FROM transition_history
            WHERE branch = ? AND from_state = ? AND to_state = ?
            """,
            (branch, from_state, to_state),
        ).fetchone()

        return row[0] if row else 0

    def record_transition(
        self,
        conn: sqlite3.Connection,
        branch: str,
        from_state: str,
        to_state: str,
        actor: str,
        event_id: int | None = None,
    ) -> None:
        """Record a new transition in transition_history.

        Args:
            branch: Flow branch name
            from_state: Source state label
            to_state: Target state label
            actor: Who triggered the transition
            event_id: Optional reference to flow_events.id
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO transition_history
                (branch, from_state, to_state, created_at, actor, event_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (branch, from_state, to_state, _utcnow_iso(), actor, event_id),
        )

    def record_confirmed_transition(
        self,
        *,
        branch: str,
        from_state: str,
        to_state: str,
        actor: str,
        detail: str,
        refs: dict[str, str],
    ) -> tuple[int, int, int]:
        """Atomically persist one confirmed state transition."""
        now = _utcnow_iso()
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE flow_state SET transition_count = "
                "COALESCE(transition_count, 0) + 1, updated_at = ? "
                "WHERE branch = ? AND deleted_at IS NULL",
                (now, branch),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Missing active flow state for {branch}")

            cursor.execute(
                "INSERT INTO flow_events "
                "(branch, event_type, actor, detail, refs, created_at) "
                "VALUES (?, 'state_transitioned', ?, ?, ?, ?)",
                (branch, actor, detail, json.dumps(refs), now),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("Confirmed transition event insert returned no id")
            event_id = cursor.lastrowid

            cursor.execute(
                "INSERT INTO transition_history "
                "(branch, from_state, to_state, created_at, actor, event_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (branch, from_state, to_state, now, actor, event_id),
            )

            total_row = cursor.execute(
                "SELECT transition_count FROM flow_state WHERE branch = ?",
                (branch,),
            ).fetchone()
            pair_row = cursor.execute(
                "SELECT COUNT(*) FROM transition_history "
                "WHERE branch = ? AND from_state = ? AND to_state = ?",
                (branch, from_state, to_state),
            ).fetchone()

        total = int(total_row[0]) if total_row else 0
        pair = int(pair_row[0]) if pair_row else 0
        return total, pair, event_id

    def reset_transition_epoch(self, branch: str) -> None:
        """Reset loop evidence for an explicitly new flow epoch."""
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE flow_state SET transition_count = 0, updated_at = ? "
                "WHERE branch = ? AND deleted_at IS NULL",
                (_utcnow_iso(), branch),
            )
            cursor.execute(
                "DELETE FROM transition_history WHERE branch = ?",
                (branch,),
            )

    def clear_transition_history(self, conn: sqlite3.Connection, branch: str) -> None:
        """Clear all transition history records for a branch.

        Called during flow resume to reset loop detection counters.

        Args:
            conn: SQLite connection
            branch: Flow branch name
        """
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM transition_history WHERE branch = ?",
            (branch,),
        )
