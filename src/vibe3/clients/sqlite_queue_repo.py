"""SQLite repository methods for orchestra queue persistence."""

import datetime
import sqlite3
from typing import Any

from loguru import logger


class SQLiteQueueRepo:
    """Orchestra queue CRUD operations."""

    db_path: str

    def save_queue_entry(
        self,
        issue_number: int,
        collected_state: str | None = None,
        waiting_state: str | None = None,
    ) -> None:
        """INSERT OR REPLACE a single queue entry.

        Args:
            issue_number: The issue number (primary key).
            collected_state: Serialized collected state (optional).
            waiting_state: Serialized waiting state (optional).
        """
        updated_at = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO orchestra_queue
                    (issue_number, collected_state, waiting_state, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (issue_number, collected_state, waiting_state, updated_at),
            )
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="save_queue_entry",
            issue_number=issue_number,
        ).debug("Saved queue entry")

    def load_queue_entry(self, issue_number: int) -> dict[str, Any] | None:
        """SELECT single entry by primary key.

        Args:
            issue_number: The issue number to load.

        Returns:
            Dict with keys: issue_number, collected_state, waiting_state, updated_at.
            None if entry does not exist.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM orchestra_queue WHERE issue_number = ?",
                (issue_number,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def load_all_queue_entries(self) -> list[dict[str, Any]]:
        """SELECT all entries ordered by updated_at.

        Returns:
            List of dicts, each with keys: issue_number, collected_state,
            waiting_state, updated_at.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orchestra_queue ORDER BY updated_at")
            rows = [dict(row) for row in cursor.fetchall()]
        logger.bind(
            external="sqlite",
            operation="load_all_queue_entries",
            count=len(rows),
        ).debug("Loaded all queue entries")
        return rows

    def remove_queue_entry(self, issue_number: int) -> None:
        """DELETE single entry by primary key.

        Args:
            issue_number: The issue number to remove.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM orchestra_queue WHERE issue_number = ?",
                (issue_number,),
            )
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="remove_queue_entry",
            issue_number=issue_number,
        ).debug("Removed queue entry")

    def replace_all_queue_entries(self, entries: list[dict[str, Any]]) -> None:
        """DELETE all + INSERT batch in single transaction.

        This is the batch primitive for full-queue persistence.
        The queue is never partially written.

        Args:
            entries: List of dicts with keys: issue_number, collected_state,
                     waiting_state. updated_at is auto-set for each entry.
        """
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orchestra_queue")
            for entry in entries:
                cursor.execute(
                    """
                    INSERT INTO orchestra_queue
                        (issue_number, collected_state, waiting_state, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        entry["issue_number"],
                        entry.get("collected_state"),
                        entry.get("waiting_state"),
                        now,
                    ),
                )
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="replace_all_queue_entries",
            count=len(entries),
        ).debug("Replaced all queue entries")
