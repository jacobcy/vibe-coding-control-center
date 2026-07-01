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
from vibe3.exceptions import ErrorSeverity, get_error_handling_contract
from vibe3.services.orchestra.error_tracking.cleanup import (
    cleanup_old_errors as _cleanup_old_errors,
)
from vibe3.services.orchestra.error_tracking.cleanup import (
    clear_errors as _clear_errors,
)
from vibe3.services.orchestra.error_tracking.queries import (
    get_all_errors_status as _get_all_errors_status,
)
from vibe3.services.orchestra.error_tracking.queries import (
    get_api_and_exec_error_count as _get_api_and_exec_error_count,
)
from vibe3.services.orchestra.error_tracking.queries import (
    get_api_error_count as _get_api_error_count,
)
from vibe3.services.orchestra.error_tracking.queries import (
    get_critical_error_codes as _get_critical_error_codes,
)
from vibe3.services.orchestra.error_tracking.queries import (
    get_error_counts as _get_error_counts,
)
from vibe3.services.orchestra.error_tracking.queries import (
    get_recent_errors as _get_recent_errors,
)
from vibe3.services.orchestra.error_tracking.queries import get_status as _get_status
from vibe3.services.orchestra.error_tracking.queries import (
    get_threshold_error_count as _get_threshold_error_count,
)
from vibe3.services.orchestra.error_tracking.queries import (
    get_warning_count as _get_warning_count,
)
from vibe3.services.orchestra.error_tracking.queries import (
    has_critical_error as _has_critical_error,
)
from vibe3.services.orchestra.error_tracking.queries import (
    has_model_config_error as _has_model_config_error,
)
from vibe3.services.orchestra.error_tracking.queries import (
    has_recent_specific_error as _has_recent_specific_error,
)


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

    # Per-db-path registry. The "default" instance (no store) is registered
    # under the default SQLiteClient.db_path key so that get_instance() and
    # clear_instance() operate on a single source of truth.
    _registry: dict[str, ErrorTrackingService] = {}

    @classmethod
    def get_instance(cls, store: SQLiteClient | None = None) -> ErrorTrackingService:
        """Get error tracking instance keyed by store.db_path.

        Args:
            store: Optional SQLiteClient for persistence. If None, the default
                   SQLiteClient is used (backward compatibility).

        Returns:
            ErrorTrackingService instance keyed by store.db_path.
        """
        effective_store = store or SQLiteClient()
        db_path = effective_store.db_path
        if db_path not in cls._registry:
            cls._registry[db_path] = cls(store=effective_store)
        return cls._registry[db_path]

    @classmethod
    def clear_instance(cls, db_path: str | None = None) -> None:
        """Clear instance(s) for testing.

        Args:
            db_path: If provided, clear the instance for that db_path. If None,
                     clear all instances (default + registry).
        """
        if db_path is None:
            cls._registry.clear()
        else:
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
        tick_id: int | None = None,
        issue_number: int | None = None,
        branch: str | None = None,
        severity: ErrorSeverity | None = None,
    ) -> tuple[bool, int]:
        """Record error and check if threshold reached.

        Args:
            error_code: Error code (E_MODEL_*, E_API_*, E_EXEC_*)
            error_message: Error message/details
            tick_id: Tick ID (auto-inferred from context if None)
            issue_number: Optional linked issue
            branch: Optional linked branch
            severity: Optional severity level. If None, inferred from error registry.

        Returns:
            (threshold_reached: bool, error_count_in_window: int)
        """
        # Auto-infer tick_id from contextvar if not provided
        if tick_id is None:
            from vibe3.runtime import get_current_tick_id

            tick_id = get_current_tick_id()

        # Infer severity from registry if not provided
        if severity is None:
            contract = get_error_handling_contract(error_code)
            severity = contract.severity

        # Persist to error_log table
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO error_log
                (tick_id, error_code, error_message, severity, issue_number, branch)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    tick_id,
                    error_code,
                    error_message,
                    severity.value,
                    issue_number,
                    branch,
                ),
            )

        logger.bind(
            domain="error_tracking",
            error_code=error_code,
            severity=severity.value,
            tick=tick_id,
        ).info("Error recorded to error_log")

        # Track ERROR-severity errors for threshold
        if severity != ErrorSeverity.ERROR:
            # CRITICAL errors → immediate gate (handled separately)
            # WARNING errors → no gate activation
            return False, 0

        # Count ERROR-severity errors in recent window
        error_count = self.get_threshold_error_count()

        # Check threshold
        threshold_reached = error_count >= self.THRESHOLD_COUNT

        if threshold_reached:
            logger.bind(
                domain="error_tracking",
                error_code=error_code,
                severity=severity.value,
                window_count=error_count,
                threshold=self.THRESHOLD_COUNT,
            ).error("ERROR-severity threshold reached")

        return threshold_reached, error_count

    # --- Query methods (delegate to error_tracking_queries module) ---

    def get_error_counts(self) -> dict[str, int]:
        """Get current error counts from error_log."""
        return _get_error_counts(self.db_path)

    def has_critical_error(self) -> bool:
        """Check if there are any CRITICAL severity errors."""
        return _has_critical_error(self.db_path)

    def has_recent_specific_error(
        self,
        issue_number: int | None,
        branch: str | None,
        within_seconds: int = 60,
    ) -> bool:
        """Check if a specific (non-dispatch) error was recently recorded."""
        return _has_recent_specific_error(
            self.db_path,
            issue_number=issue_number,
            branch=branch,
            within_seconds=within_seconds,
        )

    def get_critical_error_codes(self) -> list[str]:
        """Get error codes of CRITICAL severity errors."""
        return _get_critical_error_codes(self.db_path)

    def has_model_config_error(self) -> bool:
        """Check if there are any model configuration errors."""
        return _has_model_config_error(self.db_path)

    def get_api_error_count(self) -> int:
        """Get count of recent API errors within configured time window."""
        return _get_api_error_count(self.db_path, self.TIME_WINDOW_MINUTES)

    def get_api_and_exec_error_count(self) -> int:
        """Get count of E_API_* and E_EXEC_* errors within time window.

        .. deprecated::
            Use :meth:`get_threshold_error_count` instead.
        """
        return _get_api_and_exec_error_count(self.db_path, self.TIME_WINDOW_MINUTES)

    def get_threshold_error_count(self) -> int:
        """Get count of ERROR-severity errors within time window."""
        return _get_threshold_error_count(self.db_path, self.TIME_WINDOW_MINUTES)

    def get_warning_count(self) -> int:
        """Get count of WARNING-severity errors within time window."""
        return _get_warning_count(self.db_path, self.TIME_WINDOW_MINUTES)

    def get_recent_errors(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent errors for status display."""
        return _get_recent_errors(self.db_path, limit)

    def get_status(self) -> dict[str, Any]:
        """Get error tracking status for display with severity breakdown."""
        return _get_status(self.db_path, self.TIME_WINDOW_MINUTES, self.THRESHOLD_COUNT)

    def get_all_errors_status(self) -> dict[str, Any]:
        """Get error tracking status for ALL errors in database."""
        return _get_all_errors_status(self.db_path)

    # --- Cleanup methods (delegate to error_tracking_cleanup module) ---

    def clear(self, cleared_by: str, reason: str) -> None:
        """Clear all error records."""
        _clear_errors(self.db_path, cleared_by, reason)

    def cleanup_old_errors(self) -> int:
        """Delete error records older than retention period."""
        return _cleanup_old_errors(self.db_path, self.retention_days)
