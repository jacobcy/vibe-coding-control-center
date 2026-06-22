"""Convenience functions for error logging."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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


def record_error(
    error_code: str,
    error_message: str,
    tick_id: int = 0,
    issue_number: int | None = None,
    branch: str | None = None,
    store: "SQLiteClient | None" = None,
    severity: Any = None,
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
    # Lazy import to avoid shared→orchestra violation
    import importlib

    _module = importlib.import_module("vibe3.services.orchestra.error_tracking.service")
    ErrorTrackingService = _module.ErrorTrackingService  # noqa: N806

    error_svc = ErrorTrackingService.get_instance(store=store)
    return error_svc.record_error(  # type: ignore[no-any-return]
        error_code=error_code,
        error_message=error_message,
        tick_id=tick_id,
        issue_number=issue_number,
        branch=branch,
        severity=severity,
    )


def record_dispatch_failure_if_unexpected(
    result: Any = None,
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
        from vibe3.clients import SQLiteClient
        from vibe3.exceptions import classify_error_hybrid

        # Detect test mock leaks - skip recording entirely
        exc_str = str(exception)
        if "MagicMock" in exc_str or "Mock" in type(exception).__name__:
            logger.bind(
                domain=f"{role}_dispatch",
                issue_number=issue_number,
            ).warning(f"Test mock leak detected, skipping error recording: {exception}")
            return

        # Classify exception to preserve real error types (API/MODEL/EXEC)
        error_code = classify_error_hybrid(exception)

        # Build error message with classification context
        error_message = (
            f"{dispatch_source} {role} dispatch failed [exception]: {exception}"
        )

        try:
            record_error(
                error_code=error_code,  # Use classified error code
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

    if reason_code in ("capacity_full", "duplicate_dispatch"):
        return

    # For launch_failed, check if bottom layer already recorded specific error
    # If yes, skip E_DISPATCH_FAILURE to avoid duplicate
    # If no, record E_DISPATCH_FAILURE for infrastructure visibility
    if reason_code == "launch_failed":
        from vibe3.clients import SQLiteClient

        _store = SQLiteClient()
        if has_recent_specific_error(
            issue_number=effective_issue_number,
            branch=branch,
            within_seconds=60,
            store=_store,
        ):
            # Bottom layer recorded specific error - skip duplicate
            return
        # else: fall through to record E_DISPATCH_FAILURE

    from vibe3.clients import SQLiteClient

    # Include dispatch_source marker and reason_code for disambiguation
    reason_detail = result.reason or "(no detail)"
    error_message = (
        f"{dispatch_source} {role} dispatch failed [{reason_code}]: {reason_detail}"
    )
    try:
        _store = SQLiteClient()
        record_error(
            error_code="E_DISPATCH_FAILURE",
            error_message=error_message,
            tick_id=tick_id or 0,
            issue_number=effective_issue_number,
            branch=branch,
            store=_store,
        )
    except Exception as exc:
        logger.bind(
            domain=f"{role}_dispatch",
            issue_number=issue_number,
        ).warning(f"Failed to record dispatch error: {exc}")


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
