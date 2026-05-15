"""SQLite repository methods for frozen queue persistence."""

import sqlite3
from typing import Any

from loguru import logger


class SQLiteFrozenQueueRepo:
    """Frozen queue CRUD operations."""

    db_path: str

    def save_frozen_queue(self, entries: list[dict[str, Any]]) -> None:
        """Save frozen queue entries to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("BEGIN")
            cursor = conn.cursor()
            for entry in entries:
                cursor.execute(
                    "INSERT OR REPLACE INTO frozen_queue "
                    "(issue_number, collected_state, waiting_state) "
                    "VALUES (?, ?, ?)",
                    (
                        entry["issue_number"],
                        entry.get("collected_state"),
                        entry.get("waiting_state"),
                    ),
                )
            conn.commit()
        logger.bind(external="sqlite").debug(
            f"Saved {len(entries)} frozen queue entries"
        )

    def load_frozen_queue(self) -> list[dict[str, Any]]:
        """Load frozen queue entries from database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM frozen_queue")
            rows = [dict(row) for row in cursor.fetchall()]
        logger.bind(external="sqlite").debug(f"Loaded {len(rows)} frozen queue entries")
        return rows

    def remove_from_frozen_queue(self, issue_number: int) -> None:
        """Remove an issue from frozen queue."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM frozen_queue WHERE issue_number = ?",
                (issue_number,),
            )
            conn.commit()
        logger.bind(external="sqlite").debug(
            f"Removed issue {issue_number} from frozen queue"
        )

    def clear_frozen_queue(self) -> None:
        """Clear all entries from frozen queue."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM frozen_queue")
            conn.commit()
        logger.bind(external="sqlite").debug("Cleared frozen queue")
