"""Shared helpers for gh pr command error normalization."""

import subprocess

from vibe3.exceptions import GitHubError, UserError


def raise_gh_pr_error(
    error: subprocess.CalledProcessError,
    operation: str,
    user_tips: str | None = None,
) -> None:
    """Normalize gh pr command failure into unified error types."""
    error_msg = (error.stderr or error.stdout or f"Failed to {operation}").strip()
    lower_msg = error_msg.lower()

    recoverable_patterns = (
        "already exists",
        "no commits between",
        "must push the current branch",
        "head sha can't be blank",
        "already ready for review",
        "is in draft mode",
        "is not mergeable",
        "checks are failing",
        "no pull requests found",
    )
    if any(pattern in lower_msg for pattern in recoverable_patterns):
        tips = f"\nTips:\n{user_tips}" if user_tips else ""
        raise UserError(f"PR {operation} failed: {error_msg}{tips}") from error

    raise GitHubError(
        status_code=error.returncode,
        message=f"gh pr {operation} failed: {error_msg}",
    ) from error
