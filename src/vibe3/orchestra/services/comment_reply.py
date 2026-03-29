"""CommentReplyService: respond to @mention comments on issues."""

from __future__ import annotations

import re
import subprocess

from loguru import logger

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

    def __init__(self, config: OrchestraConfig) -> None:
        self.config = config

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
        """Post a lightweight acknowledgement comment."""
        body = (
            "> `@vibe-manager` received your message. "
            "The orchestra server will process this shortly."
        )
        cmd = [
            "gh",
            "issue",
            "comment",
            str(issue_number),
            "--body",
            body,
        ]
        if self.config.repo:
            cmd.extend(["--repo", self.config.repo])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                logger.bind(domain="orchestra").warning(
                    f"Failed to post ack on #{issue_number}: {result.stderr.strip()}"
                )
            else:
                logger.bind(domain="orchestra").info(f"Ack posted on #{issue_number}")
        except Exception as exc:
            logger.bind(domain="orchestra").error(
                f"Error posting ack on #{issue_number}: {exc}"
            )
