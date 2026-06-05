import sqlite3
from typing import Any

from vibe3.clients.sqlite_base import _HasConnection, _utcnow_iso


class SQLiteQueueRepo(_HasConnection):
    db_path: str

    def load_all_queue_entries(self) -> list[dict[str, Any]]:
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orchestra_queue ORDER BY updated_at")
        return [dict(row) for row in cursor.fetchall()]

    def remove_queue_entry(self, issue_number: int) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute(
                "DELETE FROM orchestra_queue WHERE issue_number = ?",
                (issue_number,),
            )

    def replace_all_queue_entries(self, entries: list[dict[str, Any]]) -> None:
        """DELETE all + INSERT batch in single transaction."""
        now = _utcnow_iso()
        conn = self._get_connection()
        with conn:
            conn.execute("DELETE FROM orchestra_queue")
            for entry in entries:
                conn.execute(
                    "INSERT OR REPLACE INTO orchestra_queue "
                    "(issue_number, collected_state, waiting_state, updated_at) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        entry["issue_number"],
                        entry.get("collected_state"),
                        entry.get("waiting_state"),
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
