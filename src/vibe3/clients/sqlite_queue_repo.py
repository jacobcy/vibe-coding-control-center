"""SQLite repository methods for orchestra queue persistence."""

import datetime
import sqlite3
from typing import Any

from loguru import logger


class SQLiteQueueRepo:
    """Orchestra queue CRUD operations."""

    db_path: str

    def load_queue_entries(self) -> list[dict[str, Any]]:
        """Load all queued entries from persistence.

        Returns:
            List of queue entry dicts with keys:
            issue_number, collected_state, waiting_state, retry_count,
            enqueued_at, updated_at
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT issue_number, collected_state, waiting_state, "
                "retry_count, enqueued_at, updated_at "
                "FROM orchestra_queue ORDER BY enqueued_at ASC"
            )
            rows = [dict(row) for row in cursor.fetchall()]
        logger.bind(
            external="sqlite",
            operation="load_queue_entries",
            count=len(rows),
        ).debug("Loaded queue entries from persistence")
        return rows

    def save_queue_entry(
        self,
        issue_number: int,
        collected_state: str,
        waiting_state: str | None = None,
        retry_count: int = 0,
    ) -> None:
        """Insert or replace a queue entry.

        Args:
            issue_number: Issue number (primary key)
            collected_state: State when issue was collected
            waiting_state: State issue is waiting for (None if not yet dispatched)
            retry_count: Number of dispatch retries for this issue
        """
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO orchestra_queue
                    (issue_number, collected_state, waiting_state,
                     retry_count, enqueued_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (issue_number, collected_state, waiting_state, retry_count, now, now),
            )
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="save_queue_entry",
            issue_number=issue_number,
            retry_count=retry_count,
        ).debug("Saved queue entry to persistence")

    def remove_queue_entry(self, issue_number: int) -> None:
        """Remove a queue entry by issue number.

        Args:
            issue_number: Issue number to remove
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
        ).debug("Removed queue entry from persistence")

    def increment_retry_count(self, issue_number: int) -> None:
        """Atomically increment retry count for an issue.

        Args:
            issue_number: Issue number to increment retry count for
        """
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE orchestra_queue
                SET retry_count = retry_count + 1, updated_at = ?
                WHERE issue_number = ?
                """,
                (now, issue_number),
            )
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="increment_retry_count",
            issue_number=issue_number,
        ).debug("Incremented retry count")

    def get_queue_entries_over_retry_limit(self, limit: int) -> list[int]:
        """Find issues exceeding retry count threshold.

        Args:
            limit: Maximum allowed retry count

        Returns:
            List of issue numbers with retry_count > limit
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT issue_number FROM orchestra_queue WHERE retry_count > ?",
                (limit,),
            )
            issue_numbers = [row[0] for row in cursor.fetchall()]
        logger.bind(
            external="sqlite",
            operation="get_queue_entries_over_retry_limit",
            limit=limit,
            count=len(issue_numbers),
        ).debug("Found issues over retry limit")
        return issue_numbers

    def clear_queue(self) -> None:
        """Remove all queue entries."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orchestra_queue")
            conn.commit()
        logger.bind(
            external="sqlite",
            operation="clear_queue",
        ).debug("Cleared all queue entries")
