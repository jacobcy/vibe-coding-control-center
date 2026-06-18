"""Git transient error patterns and classification utilities.

This module centralizes known transient Git error patterns that are safe
to retry without full stack trace logging. Patterns are production-validated
and used across multiple modules (manager, flow_orchestrator_service).
"""

from __future__ import annotations

# Git transient error patterns (production-validated)
# These errors are known to be retry-safe and don't require full stack traces
TRANSIENT_GIT_ERROR_PATTERNS = (
    "cannot lock ref",  # Ref lock conflicts during concurrent operations
    "unable to update local ref",  # Remote update conflicts
    "ssh: connect to host",  # SSH connection failures (timeout, refused, etc.)
    "Could not read from remote repository",  # Git remote protocol failure
    "Operation timed out",  # Network timeout (SSH and HTTPS)
)


def is_transient_git_error(error_msg: str) -> bool:
    """Check if error message matches known transient Git error patterns.

    Args:
        error_msg: Error message string to check

    Returns:
        True if error matches known transient patterns, False otherwise
    """
    return any(pattern in error_msg for pattern in TRANSIENT_GIT_ERROR_PATTERNS)


__all__ = [
    "TRANSIENT_GIT_ERROR_PATTERNS",
    "is_transient_git_error",
]
