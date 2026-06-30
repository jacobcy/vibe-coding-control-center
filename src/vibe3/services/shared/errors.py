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

    Thin-reexport shell delegating to ErrorTrackingService.
    Preserves backward compatibility for callers importing from shared.

    Args:
        issue_number: Issue number to check
        branch: Branch name to check
        within_seconds: Time window in seconds (default 60)
        store: SQLiteClient instance

    Returns:
        True if a non-E_DISPATCH_FAILURE error exists in the time window
    """
    from vibe3.clients import SQLiteClient
    from vibe3.services.orchestra import ErrorTrackingService

    if store is None:
        store = SQLiteClient()

    try:
        return ErrorTrackingService.get_instance(store=store).has_recent_specific_error(
            issue_number=issue_number,
            branch=branch,
            within_seconds=within_seconds,
        )
    except Exception:
        # Boundary defense: swallow get_instance()/SQLiteClient() failures and
        # conservatively return False (same contract as before).
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
