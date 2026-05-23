"""Runtime infrastructure errors - never trigger block_flow.

These errors represent failures in external dependencies or infrastructure:
- Model API calls (rate limits, timeouts, unavailable)
- Network requests
- GitHub API failures
- Database errors

Key principle: Runtime errors are handled by ERROR system only.
They should NEVER trigger business block (no blocked_reason, no label change).
"""

from __future__ import annotations

from vibe3.exceptions import VibeError


class RuntimeInfrastructureError(VibeError):
    """Base class for runtime infrastructure failures.

    These errors indicate external system failures, not business logic issues.
    They are handled by ERROR system and FailedGate, not BLOCK system.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, recoverable=False)


class APIError(RuntimeInfrastructureError):
    """External API failure (rate limit, timeout, unavailable).

    Examples:
    - GitHub API rate limit exceeded
    - GitHub API timeout
    - GitHub API service unavailable
    - Network connection error
    """


class ModelError(RuntimeInfrastructureError):
    """Model configuration or access error.

    Examples:
    - Model not found or unavailable
    - Permission denied for model access
    - Model configuration error
    """


class DatabaseError(RuntimeInfrastructureError):
    """Database infrastructure error.

    Examples:
    - SQLite connection failure
    - Missing column (migration not applied)
    - Database locked
    """


class GitHubAPIError(APIError):
    """GitHub API specific failure.

    Examples:
    - Issue not found
    - PR access denied
    - Rate limit exceeded
    """
