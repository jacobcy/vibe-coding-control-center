"""GitHub client base functionality."""

import subprocess

from loguru import logger


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
            from vibe3.exceptions import GitHubError

            error_msg = (e.stderr or str(e)).strip()
            raise GitHubError(
                status_code=e.returncode,
                message=f"Failed to get current GitHub user: {error_msg}",
            ) from e

    def _extract_pr_number(self, pr_url: str) -> int:
        """Extract PR number from URL.

        Args:
            pr_url: GitHub PR URL

        Returns:
            PR number

        Raises:
            ValueError: If URL is invalid
        """
        # URL format: https://github.com/owner/repo/pull/123
        parts = pr_url.split("/")
        if len(parts) < 7 or parts[-2] != "pull":
            raise ValueError(f"Invalid PR URL: {pr_url}")
        return int(parts[-1])
