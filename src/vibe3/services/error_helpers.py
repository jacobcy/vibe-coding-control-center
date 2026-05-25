"""Convenience functions for error recording."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.exceptions.error_severity import ErrorSeverity


def record_error(
    error_code: str,
    error_message: str,
    tick_id: int = 0,
    issue_number: int | None = None,
    branch: str | None = None,
    store: "SQLiteClient | None" = None,
    severity: "ErrorSeverity | None" = None,
) -> tuple[bool, int]:
    """Convenient error recording function (auto-get singleton).

    Args:
        error_code: Error code (E_MODEL_*, E_API_*, E_EXEC_*)
        error_message: Error message
        tick_id: Heartbeat tick ID
        issue_number: Associated issue number
        branch: Associated branch name
        store: SQLiteClient instance (uses default if None)
        severity: Severity level (inferred from registry if None)

    Returns:
        (threshold_reached, error_count_in_window)
    """
    from vibe3.services.error_tracking_service import ErrorTrackingService

    error_svc = ErrorTrackingService.get_instance(store=store)
    return error_svc.record_error(
        error_code=error_code,
        error_message=error_message,
        tick_id=tick_id,
        issue_number=issue_number,
        branch=branch,
        severity=severity,
    )
