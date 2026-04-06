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
        issue_payload: dict[str, object] | None = None,
    ) -> str:
        """Close a GitHub issue that is in state/ready.

        Args:
            issue_number: Issue number to close
            closing_comment: Optional comment explaining why the issue is closed
            issue_payload: Optional pre-fetched issue payload (avoids
                duplicate API call)

        Returns:
            Result string: "closed", "already_closed", or "failed"
        """
        logger.bind(
            domain="orchestra",
            operation="close_ready_issue",
            issue_number=issue_number,
        ).info("Closing ready issue")

        # Check if already closed (avoid unnecessary API call)
        if issue_payload is None:
            issue_payload_raw = self._github.view_issue(issue_number, repo=self._repo)
            if isinstance(issue_payload_raw, dict):
                issue_payload = issue_payload_raw

        if isinstance(issue_payload, dict) and issue_payload.get("state") == "closed":
            logger.bind(
                domain="orchestra",
                issue_number=issue_number,
            ).info("Issue already closed")
            return "already_closed"

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
