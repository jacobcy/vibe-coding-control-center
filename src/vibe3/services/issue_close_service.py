"""Issue close service - low-level GitHub issue close primitive.

This service provides the basic issue close operation used by
AbandonFlowService for flow abandonment. It is a narrow primitive
without state-specific policy - the orchestration layer (AbandonFlowService)
enforces state requirements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient


class IssueCloseService:
    """Service for closing GitHub issues.

    This is a low-level primitive for closing issues via GitHub API.
    It does not enforce state-specific policy - orchestration services
    like AbandonFlowService handle state validation and semantic meaning.

    The close operation handles the "already closed" case gracefully
    to support abandonment flows where the issue may already be closed.
    """

    def __init__(self, github: GitHubClient, repo: str | None = None):
        """Initialize issue close service.

        Args:
            github: GitHub client for API operations
            repo: Optional repo override (owner/repo)
        """
        self._github = github
        self._repo = repo

    def close_issue(
        self,
        issue_number: int,
        closing_comment: str | None = None,
        issue_payload: dict[str, object] | None = None,
    ) -> str:
        """Close a GitHub issue.

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
            operation="close_issue",
            issue_number=issue_number,
        ).info("Closing issue")

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
            ).info("Issue closed successfully")
            return "closed"
        else:
            logger.bind(
                domain="orchestra",
                issue_number=issue_number,
            ).error("Failed to close issue")
            return "failed"
