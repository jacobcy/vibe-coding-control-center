"""Error tracking query functions.

Extracted from ErrorTrackingService to keep the main service file under LOC limits.
All functions are pure queries that take db_path and config as parameters.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from loguru import logger

from vibe3.exceptions import ErrorSeverity, is_api_error, is_model_error

# Known canonical severity values
_KNOWN_SEVERITIES = {"CRITICAL", "ERROR", "WARNING"}


def get_error_counts(db_path: str) -> dict[str, int]:
    """Get current error counts from error_log.

    Returns:
        Dict mapping error_code -> count
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT error_code, COUNT(*) as count
            FROM error_log
            GROUP BY error_code
        """
        ).fetchall()

    return {row[0]: row[1] for row in rows}


def has_critical_error(db_path: str) -> bool:
    """Check if there are any CRITICAL severity errors.

    Returns:
        True if any CRITICAL-severity error has been recorded
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT COUNT(*) FROM error_log
            WHERE severity = ?
            """,
            (ErrorSeverity.CRITICAL.value,),
        ).fetchone()

    return rows[0] > 0 if rows else False


def get_critical_error_codes(db_path: str) -> list[str]:
    """Get error codes of CRITICAL severity errors.

    Returns:
        List of error codes with CRITICAL severity.
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT error_code FROM error_log
            WHERE severity = ?
            ORDER BY error_code
            """,
            (ErrorSeverity.CRITICAL.value,),
        ).fetchall()

    return [row[0] for row in rows]


def has_model_config_error(db_path: str) -> bool:
    """Check if there are any model configuration errors.

    Uses severity-based check for CRITICAL errors, falling back to
    E_MODEL_* prefix check for backward compatibility with pre-migration data.

    Returns:
        True if any CRITICAL-severity or E_MODEL_* error has been recorded
    """
    # Check by severity first (standard approach)
    if has_critical_error(db_path):
        return True

    # Fallback to prefix check for backward compatibility
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT COUNT(*) FROM error_log
            WHERE error_code LIKE 'E_MODEL_%'
        """
        ).fetchone()

    return rows[0] > 0 if rows else False


def get_api_error_count(db_path: str, time_window_minutes: int) -> int:
    """Get count of recent API errors within configured time window.

    Returns:
        Count of E_API_* errors in the last time_window_minutes minutes
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT COUNT(*) FROM error_log
            WHERE error_code LIKE 'E_API_%'
              AND created_at >= datetime('now', ? || ' minutes')
            """,
            (f"-{time_window_minutes}",),
        ).fetchone()

    return rows[0] if rows else 0


def get_api_and_exec_error_count(db_path: str, time_window_minutes: int) -> int:
    """Get count of E_API_* and E_EXEC_* errors within time window.

    .. deprecated::
        Use :func:`get_threshold_error_count` instead, which counts by
        severity rather than error code prefix.

    Returns:
        Number of API/exec errors in the sliding window.
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT COUNT(*) FROM error_log
            WHERE (error_code LIKE 'E_API_%' OR error_code LIKE 'E_EXEC_%')
              AND created_at >= datetime('now', ? || ' minutes')
            """,
            (f"-{time_window_minutes}",),
        ).fetchone()

    return rows[0] if rows else 0


def get_threshold_error_count(db_path: str, time_window_minutes: int) -> int:
    """Get count of ERROR-severity errors within time window.

    Counts by severity level rather than error code prefix, providing
    accurate threshold detection for all ERROR-severity errors regardless
    of their code classification.

    Returns:
        Number of ERROR-severity errors in the sliding window.
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT COUNT(*) FROM error_log
            WHERE severity = ?
              AND created_at >= datetime('now', ? || ' minutes')
            """,
            (ErrorSeverity.ERROR.value, f"-{time_window_minutes}"),
        ).fetchone()

    return rows[0] if rows else 0


def get_warning_count(db_path: str, time_window_minutes: int) -> int:
    """Get count of WARNING-severity errors within time window.

    Returns:
        Number of WARNING-severity errors in the sliding window.
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT COUNT(*) FROM error_log
            WHERE severity = ?
              AND created_at >= datetime('now', ? || ' minutes')
            """,
            (ErrorSeverity.WARNING.value, f"-{time_window_minutes}"),
        ).fetchone()

    return rows[0] if rows else 0


def _get_severity_count(db_path: str, severity: str, time_window_minutes: int) -> int:
    """Get count of errors by severity level within time window.

    Args:
        severity: Severity level string (CRITICAL, ERROR, WARNING)

    Returns:
        Count of errors with the given severity in the sliding window.
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT COUNT(*) FROM error_log
            WHERE severity = ?
              AND created_at >= datetime('now', ? || ' minutes')
            """,
            (severity, f"-{time_window_minutes}"),
        ).fetchone()

    return rows[0] if rows else 0


def get_recent_errors(db_path: str, limit: int = 10) -> list[dict[str, Any]]:
    """Get recent errors for status display.

    Args:
        limit: Maximum number of errors to return

    Returns:
        List of error records (newest first)
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT tick_id, error_code, error_message,
                   issue_number, branch, created_at, severity
            FROM error_log
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "tick_id": row[0],
            "error_code": row[1],
            "error_message": row[2],
            "issue_number": row[3],
            "branch": row[4],
            "created_at": row[5],
            "severity": row[6] or "ERROR",  # Default to ERROR if NULL
        }
        for row in rows
    ]


def get_status(
    db_path: str, time_window_minutes: int, threshold_count: int
) -> dict[str, Any]:
    """Get error tracking status for display with severity breakdown.

    Returns:
        Dict with error statistics (all counts are windowed)
    """
    # Severity-based counts (all within time window)
    critical_count = _get_severity_count(db_path, "CRITICAL", time_window_minutes)
    error_count = get_threshold_error_count(db_path, time_window_minutes)
    warning_count = get_warning_count(db_path, time_window_minutes)
    windowed_total = critical_count + error_count + warning_count

    # Legacy prefix counts (also windowed for consistency)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT error_code, COUNT(*) as count
            FROM error_log
            WHERE created_at >= datetime('now', ? || ' minutes')
            GROUP BY error_code
            """,
            (f"-{time_window_minutes}",),
        ).fetchall()
    windowed_error_counts = {row[0]: row[1] for row in rows}

    model_errors = sum(
        count for code, count in windowed_error_counts.items() if is_model_error(code)
    )
    api_errors = sum(
        count for code, count in windowed_error_counts.items() if is_api_error(code)
    )
    exec_errors = sum(
        count
        for code, count in windowed_error_counts.items()
        if code.startswith("E_EXEC_")
    )

    return {
        "total_errors": windowed_total,
        # New severity-based counts
        "critical_count": critical_count,
        "error_count": error_count,
        "warning_count": warning_count,
        # Legacy prefix counts (windowed for consistency)
        "model_errors": model_errors,
        "api_errors": api_errors,
        "exec_errors": exec_errors,
        "error_counts": windowed_error_counts,
        "api_error_window_count": get_api_error_count(db_path, time_window_minutes),
        "threshold": threshold_count,
        "time_window_minutes": time_window_minutes,
    }


def get_all_errors_status(db_path: str) -> dict[str, Any]:
    """Get error tracking status for ALL errors in database.

    This returns counts for all errors regardless of time window,
    for visibility into historical errors.

    Returns:
        Dict with error statistics for all errors in database
    """
    # Severity-based counts (all errors, no time filter)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT severity, COUNT(*) as count
            FROM error_log
            GROUP BY severity
            """,
        ).fetchall()

    severity_counts = {row[0] or "ERROR": row[1] for row in rows}
    critical_count = severity_counts.get("CRITICAL", 0)
    error_count = severity_counts.get("ERROR", 0)
    warning_count = severity_counts.get("WARNING", 0)

    # Fix: total_errors = sum of ALL grouped counts, not just known severities
    total_errors = sum(severity_counts.values())

    # Surface unknown severity values for observability
    unknown_severity_counts = {
        sev: count
        for sev, count in severity_counts.items()
        if sev not in _KNOWN_SEVERITIES
    }

    if unknown_severity_counts:
        logger.warning(
            f"error_log contains unknown severity values: {unknown_severity_counts}"
        )

    return {
        "total_errors": total_errors,
        "critical_count": critical_count,
        "error_count": error_count,
        "warning_count": warning_count,
        "unknown_severity_counts": unknown_severity_counts,
    }
