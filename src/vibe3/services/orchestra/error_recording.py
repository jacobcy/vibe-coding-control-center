"""Convenience wrappers for error recording that auto-create ErrorTrackingService.

These wrappers provide the convenience of automatic ErrorTrackingService singleton
access for command-line and handler usage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.exceptions import ErrorSeverity
    from vibe3.models import ExecutionLaunchResult


def record_error(
    error_code: str,
    error_message: str,
    tick_id: int | None = None,
    issue_number: int | None = None,
    branch: str | None = None,
    store: "SQLiteClient | None" = None,
    severity: "ErrorSeverity | None" = None,
) -> tuple[bool, int]:
    """Convenient error recording function (auto-get singleton).

    Args:
        error_code: Error code (E_MODEL_*, E_API_*, E_EXEC_*)
        error_message: Error message
        tick_id: Heartbeat tick ID (auto-inferred from context if None)
        issue_number: Associated issue number
        branch: Associated branch name
        store: SQLiteClient instance (uses default if None)
        severity: Severity level (inferred from registry if None)

    Returns:
        (threshold_reached, error_count_in_window)
    """
    # Auto-infer tick_id from contextvar if not provided
    if tick_id is None:
        from vibe3.runtime import get_current_tick_id

        tick_id = get_current_tick_id()

    from vibe3.services.orchestra import ErrorTrackingService

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
    from vibe3.services.shared.errors import has_recent_specific_error

    # Preserve None for governance, coerce to 0 for other roles
    effective_issue_number = (
        issue_number if role == "governance" else (issue_number or 0)
    )

    # Handle exception-level failures
    if exception is not None:
        from unittest.mock import MagicMock, Mock

        from vibe3.clients import SQLiteClient
        from vibe3.exceptions import classify_error_hybrid

        # Detect test mock leaks by type inheritance, not string matching
        # This avoids false positives when production errors contain "Mock" strings
        if isinstance(exception, (Mock, MagicMock)):
            logger.bind(
                domain=f"{role}_dispatch",
                issue_number=issue_number,
            ).warning(f"Test mock leak detected, skipping error recording: {exception}")
            return

        # Classify exception to preserve real error types (API/MODEL/EXEC)
        error_code = classify_error_hybrid(exception)

        # If unclassified, check for permanent code errors (vs transient infra)
        # Permanent code bugs → E_DISPATCH_CODE_ERROR (ERROR, counts toward gate)
        # Transient infra → stays E_EXEC_UNKNOWN (WARNING, no gate impact)
        if error_code == "E_EXEC_UNKNOWN":
            from vibe3.exceptions import is_permanent_code_error

            if is_permanent_code_error(exception):
                error_code = "E_DISPATCH_CODE_ERROR"

        # Build error message with classification context
        error_message = (
            f"{dispatch_source} {role} dispatch failed [exception]: {exception}"
        )

        try:
            record_error(
                error_code=error_code,  # Use classified error code
                error_message=error_message,
                tick_id=tick_id,
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

    if reason_code in ("capacity_full", "duplicate_dispatch"):
        return

    # For launch_failed, check if bottom layer already recorded specific error
    # If yes, skip E_DISPATCH_FAILURE to avoid duplicate
    # If no, record E_DISPATCH_FAILURE for infrastructure visibility
    if reason_code == "launch_failed":
        from vibe3.clients import SQLiteClient

        # Use single store instance for both check and potential recording
        _store = SQLiteClient()
        if has_recent_specific_error(
            issue_number=effective_issue_number,
            branch=branch,
            within_seconds=60,
            store=_store,
        ):
            # Bottom layer recorded specific error - skip duplicate
            return
        # else: fall through to record E_DISPATCH_FAILURE using same _store
    else:
        # For other reason_codes, create store only when needed
        from vibe3.clients import SQLiteClient

        _store = SQLiteClient()

    # Include dispatch_source marker and reason_code for disambiguation
    reason_detail = result.reason or "(no detail)"
    error_message = (
        f"{dispatch_source} {role} dispatch failed [{reason_code}]: {reason_detail}"
    )
    try:
        record_error(
            error_code="E_DISPATCH_FAILURE",
            error_message=error_message,
            tick_id=tick_id,
            issue_number=effective_issue_number,
            branch=branch,
            store=_store,
        )
    except Exception as exc:
        logger.bind(
            domain=f"{role}_dispatch",
            issue_number=issue_number,
        ).warning(f"Failed to record dispatch error: {exc}")
