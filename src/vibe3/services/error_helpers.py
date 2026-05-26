"""Convenience functions for error recording."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.exceptions.error_severity import ErrorSeverity
    from vibe3.execution.contracts import ExecutionLaunchResult


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


def record_dispatch_failure_if_unexpected(
    result: "ExecutionLaunchResult",
    role: str,
    issue_number: int | None,
    branch: str,
) -> None:
    """Record dispatch failure if it's unexpected (not normal throttling).

    Args:
        result: Execution launch result
        role: Role name (planner/executor/reviewer)
        issue_number: Associated issue number
        branch: Associated branch name
    """
    if result.launched or result.skipped:
        return

    reason_code = result.reason_code or "unknown"

    if reason_code in ("capacity_full", "duplicate_dispatch"):
        return

    from vibe3.clients.sqlite_client import SQLiteClient

    # Include manual marker and reason_code for disambiguation
    reason_detail = result.reason or "(no detail)"
    error_message = f"manual {role} dispatch failed [{reason_code}]: {reason_detail}"
    try:
        record_error(
            error_code="E_DISPATCH_FAILURE",
            error_message=error_message,
            issue_number=issue_number,
            branch=branch,
            store=SQLiteClient(),
        )
    except Exception as exc:
        logger.bind(
            domain=f"{role}_dispatch",
            issue_number=issue_number,
        ).warning(f"Failed to record dispatch error: {exc}")


# PR #1498 - Manual CLI dispatch error tracking
