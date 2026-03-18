"""GitHub client base functionality."""

import json
import subprocess
from typing import Any

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

    def _run_gh_command(
        self, args: list[str], input_data: str | None = None
    ) -> dict[str, Any]:
        """Run a gh command and return JSON output.

        Args:
            args: Command arguments (without 'gh' prefix)
            input_data: Optional stdin input

        Returns:
            Parsed JSON output

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        cmd = ["gh"] + args
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            check=True,
        )

        if not result.stdout:
            return {}

        return json.loads(result.stdout)  # type: ignore[no-any-return]

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
