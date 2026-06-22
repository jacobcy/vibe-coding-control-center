"""Convenience functions for error logging."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient


def has_recent_specific_error(
    issue_number: int | None,
    branch: str | None,
    within_seconds: int = 60,
    store: "SQLiteClient | None" = None,
) -> bool:
    """Check if a specific (non-dispatch) error was recently recorded.

    Used to avoid duplicate error recording when launch_failed occurs
    after a lower layer has already recorded a specific error.

    Args:
        issue_number: Issue number to check
        branch: Branch name to check
        within_seconds: Time window in seconds (default 60)
        store: SQLiteClient instance

    Returns:
        True if a non-E_DISPATCH_FAILURE error exists in the time window
    """
    import sqlite3

    from vibe3.clients import SQLiteClient

    if store is None:
        store = SQLiteClient()

    query = f"""
        SELECT COUNT(*) FROM error_log
        WHERE error_code != 'E_DISPATCH_FAILURE'
          AND issue_number = ?
          AND branch = ?
          AND datetime(created_at) >= datetime('now', '-{within_seconds} seconds')
    """

    try:
        with sqlite3.connect(store.db_path) as conn:
            cursor = conn.execute(query, (issue_number or 0, branch or ""))
            count = cursor.fetchone()[0]
            return bool(count > 0)
    except Exception:
        # If query fails, be conservative and return False
        return False


def log_dispatch_error(context: str, exc: Exception) -> None:
    """Log a dispatch/execution error, classifying known external failures.

    GitHubError and subprocess.CalledProcessError (rate-limit, auth, network)
    are logged as a truncated WARNING with external=True binding, avoiding
    noisy tracebacks. All other exceptions get a full traceback via
    logger.exception for diagnosis.
    """
    from subprocess import CalledProcessError

    from vibe3.exceptions import GitHubError

    if isinstance(exc, (GitHubError, CalledProcessError)):
        error_text = str(exc)
        preview = error_text[:200] + "..." if len(error_text) > 200 else error_text
        logger.bind(external=True).warning(f"{context}: {preview}")
    else:
        logger.exception(f"{context}: {exc}")
