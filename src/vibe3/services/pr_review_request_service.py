"""Service for requesting AI review via GitHub comment."""

from loguru import logger

from vibe3.clients.protocols import GitHubClientProtocol


class PRReviewRequestService:
    """Service to request AI review by posting mention comment."""

    def __init__(self, github_client: GitHubClientProtocol) -> None:
        """Initialize service with GitHub client."""
        self.github_client = github_client

    def request_review(self, pr_number: int, reviewers: list[str]) -> str | None:
        """
        Request AI review by posting mention comment.

        Args:
            pr_number: PR number
            reviewers: List of reviewer names (codex, copilot, auggie, claude)

        Returns:
            Comment URL if successful, None if failed
        """
        if not reviewers:
            logger.warning("No reviewers specified, skipping review request")
            return None

        body = self._generate_mention_body(reviewers)

        try:
            comment_url = self.github_client.create_pr_comment(pr_number, body)
            logger.info(f"Review request comment posted: {comment_url}")
            return comment_url
        except Exception as e:
            logger.error(f"Failed to post review request comment: {e}")
            return None

    def _generate_mention_body(self, reviewers: list[str]) -> str:
        """
        Generate mention comment body.

        Format:
        @codex
        @copilot

        Please review changes and fix bugs.
        Focus on code quality, test coverage, and potential issues.
        """
        lines = [f"@{r}" for r in reviewers]
        lines.append("")
        lines.append("Please review changes and fix bugs.")
        lines.append("Focus on code quality, test coverage, and potential issues.")
        return "\n".join(lines)
