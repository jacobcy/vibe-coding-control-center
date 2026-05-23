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


def cleanup_terminal_issue_errors(db_path: str) -> int:
    """Delete error records for issues with terminal flow status.

    Uses flow_issue_links (issue_role='task') as SSOT to identify current
    task flow for each issue, avoiding false matches on superseded flows.

    Also cleans up orphaned errors that still point at a terminal tombstone
    branch after the current task flow link has already been removed.

    Terminal states: done, aborted, stale (per _is_reusable_auto_flow
    in flow_dispatch.py).

    Args:
        db_path: Path to SQLite database

    Returns:
        Number of deleted records
    """
    with sqlite3.connect(db_path) as conn:
        result = conn.execute("""
            DELETE FROM error_log AS el
            WHERE el.issue_number IS NOT NULL
              AND (
                EXISTS (
                    SELECT 1
                    FROM flow_issue_links fil
                    INNER JOIN flow_state fs ON fs.branch = fil.branch
                    WHERE fil.issue_role = 'task'
                      AND fil.issue_number = el.issue_number
                      AND fs.flow_status IN ('done', 'aborted', 'stale')
                      AND fs.deleted_at IS NULL
                )
                OR (
                    NOT EXISTS (
                        SELECT 1
                        FROM flow_issue_links fil_current
                        INNER JOIN flow_state fs_current
                            ON fs_current.branch = fil_current.branch
                        WHERE fil_current.issue_role = 'task'
                          AND fil_current.issue_number = el.issue_number
                          AND fs_current.deleted_at IS NULL
                    )
                    AND EXISTS (
                        SELECT 1
                        FROM flow_state fs_tomb
                        WHERE fs_tomb.branch = el.branch
                          AND fs_tomb.flow_status IN ('done', 'aborted', 'stale')
                    )
                )
              )
        """)
        conn.commit()
        return result.rowcount
