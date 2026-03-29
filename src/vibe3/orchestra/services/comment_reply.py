"""CommentReplyService: respond to @mention comments on issues."""

from __future__ import annotations

import re

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase

_MENTION_RE = re.compile(r"@vibe-manager\b", re.IGNORECASE)


class CommentReplyService(ServiceBase):
    """Reply to @vibe-manager mentions in issue comments.

    Listens for issue_comment/created and issue_comment/edited events.
    When a comment mentions @vibe-manager, posts a lightweight acknowledgement
    or routes to an agent for a full reply (configurable).
    """

    event_types = ["issue_comment"]

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
    ) -> None:
        self.config = config
        self._github = github or GitHubClient()

    async def handle_event(self, event: GitHubEvent) -> None:
        if event.action not in ("created", "edited"):
            return

        comment_body = (event.payload.get("comment") or {}).get("body", "")
        issue_number = (event.payload.get("issue") or {}).get("number")

        if not issue_number or not _MENTION_RE.search(comment_body):
            return

        log = logger.bind(domain="orchestra", issue=issue_number)
        log.info(f"@vibe-manager mention detected in issue #{issue_number}")

        if self.config.dry_run:
            log.info("Dry run: skipping comment reply")
            return

        self._post_ack(issue_number)

    def _post_ack(self, issue_number: int) -> None:
        """Post a lightweight acknowledgement comment via GitHubClient."""
        body = (
            "> 👋 `@vibe-manager` received your message. "
            "The orchestra server will process this shortly."
        )
        success = self._github.add_comment(
            issue_number, body=body, repo=self.config.repo
        )
        if success:
            logger.bind(domain="orchestra").info(f"Ack posted on #{issue_number}")
        else:
            logger.bind(domain="orchestra").warning(
                f"Failed to post ack on #{issue_number}"
            )
