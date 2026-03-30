"""GitHub client review operations."""

import subprocess
from typing import Any

from loguru import logger

from vibe3.exceptions import GitHubError, UserError


class ReviewMixin:
    """Mixin for review-related operations."""

    def get_pr_diff(self: Any, pr_number: int) -> str:
        """Get PR diff.

        Args:
            pr_number: PR number

        Returns:
            PR diff content

        Raises:
            UserError: If PR has too many files (>300) for GitHub API
            GitHubError: If gh command fails for other reasons
        """
        logger.bind(
            external="github",
            operation="get_diff",
            pr_number=pr_number,
        ).debug("Calling GitHub API: get_pr_diff")
        try:
            result = subprocess.run(
                ["gh", "pr", "diff", str(pr_number)],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Failed to get PR diff"
            # Check for GitHub's 300 file limit
            if "diff exceeded the maximum number of files" in error_msg:
                raise UserError(
                    f"PR #{pr_number} has too many files (GitHub limit: 300).\n"
                    f"  Cannot analyze PRs with >300 files via GitHub API.\n"
                    f"  Alternatives:\n"
                    f"    1. Checkout the PR locally and use 'vibe inspect branch'\n"
                    f"    2. View file list at: https://github.com/.../pull/{pr_number}/files"
                ) from e
            raise GitHubError(
                status_code=e.returncode,
                message=error_msg,
            ) from e

    def get_pr_files(self: Any, pr_number: int) -> list[str]:
        """Get list of files changed in PR.

        Args:
            pr_number: PR number

        Returns:
            List of changed file paths

        Raises:
            UserError: If PR has too many files (>300) for GitHub API
            GitHubError: If gh command fails for other reasons
        """
        logger.bind(
            external="github",
            operation="get_pr_files",
            pr_number=pr_number,
        ).debug("Calling GitHub API: get_pr_files")
        try:
            result = subprocess.run(
                ["gh", "pr", "diff", str(pr_number), "--name-only"],
                capture_output=True,
                text=True,
                check=True,
            )
            return [f for f in result.stdout.splitlines() if f.strip()]
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Failed to get PR files"
            # Check for GitHub's 300 file limit
            if "diff exceeded the maximum number of files" in error_msg:
                raise UserError(
                    f"PR #{pr_number} has too many files (GitHub limit: 300).\n"
                    f"  Cannot analyze PRs with >300 files via GitHub API.\n"
                    f"  Alternatives:\n"
                    f"    1. Checkout the PR locally and use 'vibe inspect branch'\n"
                    f"    2. View file list at: https://github.com/.../pull/{pr_number}/files"
                ) from e
            raise GitHubError(
                status_code=e.returncode,
                message=error_msg,
            ) from e
