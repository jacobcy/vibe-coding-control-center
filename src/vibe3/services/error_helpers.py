"""Convenience functions for error recording."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
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
    result: "ExecutionLaunchResult | None" = None,
    role: str = "",
    issue_number: int | None = None,
    branch: str = "",
    *,
    exception: Exception | None = None,
    tick_id: int | None = None,
    dispatch_source: str = "manual",
) -> None:
    """Record dispatch failure if it's unexpected (not normal throttling).

    Args:
        result: Execution launch result (optional if exception provided)
        role: Role name (planner/executor/reviewer/governance/supervisor)
        issue_number: Associated issue number (None for governance-scoped dispatches)
        branch: Associated branch name
        exception: Exception that was raised during dispatch (keyword-only)
        tick_id: Heartbeat tick ID for automatic dispatches (keyword-only)
        dispatch_source: Source of dispatch - "manual" or "automatic" (keyword-only)
    """
    # Preserve None for governance, coerce to 0 for other roles
    effective_issue_number = (
        issue_number if role == "governance" else (issue_number or 0)
    )

    # Handle exception-level failures
    if exception is not None:
        from vibe3.clients.sqlite_client import SQLiteClient

        error_message = (
            f"{dispatch_source} {role} dispatch failed [exception]: {exception}"
        )
        try:
            record_error(
                error_code="E_DISPATCH_FAILURE",
                error_message=error_message,
                tick_id=tick_id or 0,
                issue_number=effective_issue_number,
                branch=branch,
                store=SQLiteClient(),
            )
        except Exception as exc:
            logger.bind(
                domain=f"{role}_dispatch",
                issue_number=issue_number,
            ).warning(f"Failed to record dispatch error: {exc}")
        return

    # Handle result-level failures
    if result is None:
        return

    if result.launched or result.skipped:
        return

    reason_code = result.reason_code or "unknown"

    if reason_code in ("capacity_full", "duplicate_dispatch", "launch_failed"):
        return

    from vibe3.clients.sqlite_client import SQLiteClient

    # Include dispatch_source marker and reason_code for disambiguation
    reason_detail = result.reason or "(no detail)"
    error_message = (
        f"{dispatch_source} {role} dispatch failed [{reason_code}]: {reason_detail}"
    )
    try:
        record_error(
            error_code="E_DISPATCH_FAILURE",
            error_message=error_message,
            tick_id=tick_id or 0,
            issue_number=effective_issue_number,
            branch=branch,
            store=SQLiteClient(),
        )
    except Exception as exc:
        logger.bind(
            domain=f"{role}_dispatch",
            issue_number=issue_number,
        ).warning(f"Failed to record dispatch error: {exc}")
