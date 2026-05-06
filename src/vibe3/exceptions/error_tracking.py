"""Error tracking service for threshold detection.

Implements sliding window tracking for API errors to distinguish between:
- Sporadic API errors (local blocked)
- Frequent API errors (global failed gate)

All error state is persisted to SQLite for durability across restarts.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.exceptions.error_codes import is_api_error, is_model_error


class ErrorTrackingService:
    """Track API errors in time window for threshold detection.

    Threshold rule: 2+ API errors in last 10 minutes → failed gate

    Error categories:
    - MODEL_CONFIG: Immediate failed gate
    - API_ERROR: Threshold-based failed gate
    - EXEC_ERROR: Local blocked only

    All error records are persisted to SQLite `error_log` table.
    """

    # Time window size (minutes)
    TIME_WINDOW_MINUTES = 10

    # Threshold count in time window
    THRESHOLD_COUNT = 2

    # Default retention period (days)
    DEFAULT_RETENTION_DAYS = 7

    # Global singleton instance (backward compatibility)
    _instance: ErrorTrackingService | None = None

    # Per-db-path registry for multi-instance support
    _registry: dict[str, ErrorTrackingService] = {}

    # Default instance for backward compatibility
    _default_instance: ErrorTrackingService | None = None

    @classmethod
    def get_instance(cls, store: SQLiteClient | None = None) -> ErrorTrackingService:
        """Get error tracking instance.

        Args:
            store: Optional SQLiteClient for persistence. If None, returns/creates
                   the default instance for backward compatibility.

        Returns:
            ErrorTrackingService instance keyed by store.db_path if store provided,
            otherwise the default instance.
        """
        if store is None:
            # Backward compatibility: check _instance first (tests may set it directly)
            if cls._instance is not None:
                return cls._instance
            # If no _instance, create default instance
            if cls._default_instance is None:
                cls._default_instance = cls()
                cls._instance = cls._default_instance  # Keep _instance in sync
            return cls._default_instance
        else:
            # Per-db-path instance
            db_path = store.db_path
            if db_path not in cls._registry:
                cls._registry[db_path] = cls(store=store)
            return cls._registry[db_path]

    @classmethod
    def clear_instance(cls, db_path: str | None = None) -> None:
        """Clear instance(s) for testing.

        Args:
            db_path: If provided, clear only the instance for that db_path.
                     If None, clear only the default instance.
        """
        if db_path is None:
            # Clear default instance
            cls._default_instance = None
            cls._instance = None  # Keep _instance in sync
        else:
            # Clear specific db_path instance
            cls._registry.pop(db_path, None)

    def __init__(
        self, store: SQLiteClient | None = None, retention_days: int | None = None
    ) -> None:
        """Initialize error tracking service.

        Args:
            store: SQLiteClient for persistence
            retention_days: Days to retain error records (default: 7)
        """
        self.store = store or SQLiteClient()
        # Access db_path from base class
        self.db_path = self.store.db_path
        self.retention_days = (
            self.DEFAULT_RETENTION_DAYS if retention_days is None else retention_days
        )
        if self.retention_days <= 0:
            raise ValueError(f"retention_days must be positive, got {retention_days}")

    def record_error(
        self,
        error_code: str,
        error_message: str,
        tick_id: int = 0,
        issue_number: int | None = None,
        branch: str | None = None,
    ) -> tuple[bool, int]:
        """Record error and check if threshold reached.

        Args:
            error_code: Error code (E_MODEL_*, E_API_*, E_EXEC_*)
            error_message: Error message/details
            tick_id: Tick ID (defaults to 0)
            issue_number: Optional linked issue
            branch: Optional linked branch

        Returns:
            (threshold_reached: bool, error_count_in_window: int)
        """
        # Persist to error_log table
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO error_log
                (tick_id, error_code, error_message, issue_number, branch)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tick_id, error_code, error_message, issue_number, branch),
            )

        logger.bind(
            domain="error_tracking",
            error_code=error_code,
            tick=tick_id,
        ).info("Error recorded to error_log")

        # Only track API errors for threshold
        if not is_api_error(error_code):
            # Model config errors → immediate threshold (but handled separately)
            # Execution errors → no threshold
            return False, 0

        # Count API errors in recent window
        api_error_count = self.get_api_error_count()

        # Check threshold
        threshold_reached = api_error_count >= self.THRESHOLD_COUNT

        if threshold_reached:
            logger.bind(
                domain="error_tracking",
                error_code=error_code,
                window_count=api_error_count,
                threshold=self.THRESHOLD_COUNT,
            ).error("API error threshold reached")

        return threshold_reached, api_error_count

    def get_error_counts(self) -> dict[str, int]:
        """Get current error counts from error_log.

        Returns:
            Dict mapping error_code -> count
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT error_code, COUNT(*) as count
                FROM error_log
                GROUP BY error_code
                """).fetchall()

        return {row[0]: row[1] for row in rows}

    def has_model_config_error(self) -> bool:
        """Check if there are any model configuration errors.

        Returns:
            True if any E_MODEL_* error has been recorded
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT COUNT(*) FROM error_log
                WHERE error_code LIKE 'E_MODEL_%'
                """).fetchone()

        return rows[0] > 0 if rows else False

    def get_api_error_count(self) -> int:
        """Get count of recent API errors (10-minute time window).

        Returns:
            Count of E_API_* errors in the last 10 minutes
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT COUNT(*) FROM error_log
                WHERE error_code LIKE 'E_API_%'
                  AND created_at >= datetime('now', '-10 minutes')
                """).fetchone()

        return rows[0] if rows else 0

    def get_recent_errors(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent errors for status display.

        Args:
            limit: Maximum number of errors to return

        Returns:
            List of error records (newest first)
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT tick_id, error_code, error_message,
                       issue_number, branch, created_at
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
            }
            for row in rows
        ]

    def clear(self, cleared_by: str, reason: str) -> None:
        """Clear all error records.

        Args:
            cleared_by: Who cleared (e.g., "admin:manual")
            reason: Reason for clearing
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM error_log")

        logger.bind(
            domain="error_tracking",
            cleared_by=cleared_by,
            reason=reason,
        ).info("Error log cleared")

    def cleanup_old_errors(self) -> int:
        """Delete error records older than retention period.

        Returns:
            Number of deleted records
        """
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                """
                DELETE FROM error_log
                WHERE created_at < datetime('now', ? || ' days')
                """,
                (f"-{self.retention_days}",),
            )
            conn.commit()
            return result.rowcount

    def get_status(self) -> dict[str, Any]:
        """Get error tracking status for display.

        Returns:
            Dict with error statistics
        """
        error_counts = self.get_error_counts()
        model_errors = sum(1 for code in error_counts.keys() if is_model_error(code))
        api_errors = sum(1 for code in error_counts.keys() if is_api_error(code))
        exec_errors = sum(
            1 for code in error_counts.keys() if code.startswith("E_EXEC_")
        )

        return {
            "total_errors": sum(error_counts.values()),
            "model_errors": model_errors,
            "api_errors": api_errors,
            "exec_errors": exec_errors,
            "error_counts": error_counts,
            "api_error_window_count": self.get_api_error_count(),
            "threshold": self.THRESHOLD_COUNT,
            "time_window_minutes": self.TIME_WINDOW_MINUTES,
        }
