"""Error tracking cleanup functions.

Extracted from ErrorTrackingService to keep the main service file under LOC limits.
All functions perform cleanup operations on the error_log table.
"""

from __future__ import annotations

import sqlite3

from loguru import logger


def clear_errors(db_path: str, cleared_by: str, reason: str) -> None:
    """Clear all error records.

    Args:
        db_path: Path to SQLite database
        cleared_by: Who cleared (e.g., "admin:manual")
        reason: Reason for clearing
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM error_log")

    logger.bind(
        domain="error_tracking",
        cleared_by=cleared_by,
        reason=reason,
    ).info("Error log cleared")


def cleanup_old_errors(db_path: str, retention_days: int) -> int:
    """Delete error records older than retention period.

    Args:
        db_path: Path to SQLite database
        retention_days: Days to retain error records

    Returns:
        Number of deleted records
    """
    with sqlite3.connect(db_path) as conn:
        result = conn.execute(
            """
            DELETE FROM error_log
            WHERE created_at < datetime('now', ? || ' days')
            """,
            (f"-{retention_days}",),
        )
        conn.commit()
        return result.rowcount
