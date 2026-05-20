import datetime
import sqlite3
from typing import Any


class SQLiteQueueRepo:
    db_path: str
    _enqueued_at_cache: dict[str, bool] = {}  # db_path -> has_enqueued_at

    def _check_has_enqueued_at(self, conn: sqlite3.Connection) -> bool:
        """Check if legacy enqueued_at column exists (cached per db_path)."""
        if self.db_path not in self._enqueued_at_cache:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(orchestra_queue)")
            columns = {row[1] for row in cursor.fetchall()}
            self._enqueued_at_cache[self.db_path] = "enqueued_at" in columns
        return self._enqueued_at_cache[self.db_path]

    def save_queue_entry(
        self,
        issue_number: int,
        collected_state: str | None = None,
        waiting_state: str | None = None,
        retry_count: int = 0,
        last_attempted_at: str | None = None,
    ) -> None:
        """INSERT OR REPLACE a single queue entry."""
        updated_at = datetime.datetime.now().isoformat()
        # Use last_attempted_at for enqueued_at if column exists (backward compat)
        timestamp = last_attempted_at or updated_at

        conn = self._get_connection()  # type: ignore[attr-defined]
        if self._check_has_enqueued_at(conn):
            conn.execute(
                "INSERT OR REPLACE INTO orchestra_queue "
                "(issue_number, collected_state, waiting_state, retry_count, "
                "last_attempted_at, enqueued_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    issue_number,
                    collected_state,
                    waiting_state,
                    retry_count,
                    last_attempted_at,
                    timestamp,
                    updated_at,
                ),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO orchestra_queue "
                "(issue_number, collected_state, waiting_state, retry_count, "
                "last_attempted_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    issue_number,
                    collected_state,
                    waiting_state,
                    retry_count,
                    last_attempted_at,
                    updated_at,
                ),
            )

    def load_queue_entry(self, issue_number: int) -> dict[str, Any] | None:
        conn = self._get_connection()  # type: ignore[attr-defined]
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM orchestra_queue WHERE issue_number = ?",
            (issue_number,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def load_all_queue_entries(self) -> list[dict[str, Any]]:
        conn = self._get_connection()  # type: ignore[attr-defined]
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orchestra_queue ORDER BY updated_at")
        return [dict(row) for row in cursor.fetchall()]

    def remove_queue_entry(self, issue_number: int) -> None:
        conn = self._get_connection()  # type: ignore[attr-defined]
        conn.execute(
            "DELETE FROM orchestra_queue WHERE issue_number = ?",
            (issue_number,),
        )

    def replace_all_queue_entries(self, entries: list[dict[str, Any]]) -> None:
        """DELETE all + INSERT batch in single transaction."""
        now = datetime.datetime.now().isoformat()
        conn = self._get_connection()  # type: ignore[attr-defined]
        conn.execute("DELETE FROM orchestra_queue")
        has_enqueued_at = self._check_has_enqueued_at(conn)
        for entry in entries:
            timestamp = entry.get("last_attempted_at") or now
            if has_enqueued_at:
                conn.execute(
                    "INSERT OR REPLACE INTO orchestra_queue "
                    "(issue_number, collected_state, waiting_state, retry_count, "
                    "last_attempted_at, enqueued_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        entry["issue_number"],
                        entry.get("collected_state"),
                        entry.get("waiting_state"),
                        entry.get("retry_count", 0),
                        entry.get("last_attempted_at"),
                        timestamp,
                        now,
                    ),
                )
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO orchestra_queue "
                    "(issue_number, collected_state, waiting_state, retry_count, "
                    "last_attempted_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        entry["issue_number"],
                        entry.get("collected_state"),
                        entry.get("waiting_state"),
                        entry.get("retry_count", 0),
                        entry.get("last_attempted_at"),
                        now,
                    ),
                )

    # Frozen queue compatibility methods (alias for orchestra_queue operations)
    def save_frozen_queue(self, entries: list[dict[str, Any]]) -> None:
        """Save frozen queue entries (bulk replace)."""
        self.replace_all_queue_entries(entries)

    def load_frozen_queue(self) -> list[dict[str, Any]]:
        """Load frozen queue entries."""
        return self.load_all_queue_entries()

    def remove_from_frozen_queue(self, issue_number: int) -> None:
        """Remove an issue from frozen queue."""
        self.remove_queue_entry(issue_number)

    def clear_frozen_queue(self) -> None:
        """Clear all entries from frozen queue."""
        self.replace_all_queue_entries([])
