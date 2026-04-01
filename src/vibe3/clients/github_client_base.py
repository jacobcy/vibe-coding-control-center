"""GitHub client base functionality."""

import subprocess
from typing import NoReturn

from loguru import logger

from vibe3.exceptions import GitHubError, UserError


def raise_gh_pr_error(
    error: subprocess.CalledProcessError,
    operation: str,
    user_tips: str | None = None,
) -> NoReturn:
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


class GitHubClientBase:
    """Base class for GitHub client operations."""

    def check_auth(self) -> bool:
        """Check if authenticated to GitHub."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            logger.bind(
                external="github",
                operation="check_auth",
            ).error("Failed to check auth")
            return False

    def get_current_user(self) -> str:
        """Get current authenticated user login name."""
        try:
            result = subprocess.run(
                ["gh", "api", "user", "-q", ".login"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or str(e)).strip()
            raise GitHubError(
                status_code=e.returncode,
                message=f"Failed to get current GitHub user: {error_msg}",
            ) from e

    def _extract_pr_number(self, pr_url: str) -> int:
        """Extract PR number from URL."""
        # URL format: https://github.com/owner/repo/pull/123
        parts = pr_url.split("/")
        if len(parts) < 7 or parts[-2] != "pull":
            raise ValueError(f"Invalid PR URL: {pr_url}")
        return int(parts[-1])
