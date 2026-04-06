"""Ready-close service for closing issues in state/ready."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient


class ReadyCloseService:
    """Service for closing GitHub issues that should not be executed.

    This service provides a controlled path for managers to close issues
    in state/ready when the task is determined to be invalid, deprecated,
    or otherwise unsuitable for execution.

    The close operation is only legal for issues in state/ready.
    state/done is reserved for normal delivery completion flows.
    """

    def __init__(self, github: GitHubClient, repo: str | None = None):
        """Initialize ready-close service.

        Args:
            github: GitHub client for API operations
            repo: Optional repo override (owner/repo)
        """
        self._github = github
        self._repo = repo

    def close_ready_issue(
        self,
        issue_number: int,
        closing_comment: str | None = None,
    ) -> str:
        """Close a GitHub issue that is in state/ready.

        Args:
            issue_number: Issue number to close
            closing_comment: Optional comment explaining why the issue is closed

        Returns:
            Result string: "closed", "already_closed", or "failed"
        """
        logger.bind(
            domain="orchestra",
            operation="close_ready_issue",
            issue_number=issue_number,
        ).info("Closing ready issue")

        # Call GitHub close API
        success = self._github.close_issue(
            issue_number=issue_number,
            comment=closing_comment,
            repo=self._repo,
        )

        if success:
            logger.bind(
                domain="orchestra",
                issue_number=issue_number,
            ).info("Ready issue closed successfully")
            return "closed"
        else:
            logger.bind(
                domain="orchestra",
                issue_number=issue_number,
            ).error("Failed to close ready issue")
            return "failed"
