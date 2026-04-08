"""CommentReplyService: respond to @mention comments on issues."""

from __future__ import annotations

import re

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase


def _build_mention_pattern(usernames: list[str]) -> re.Pattern[str]:
    """Build mention regex from configured manager usernames."""
    alts = "|".join(re.escape(u) for u in usernames)
    return re.compile(rf"@(?:{alts})\b", re.IGNORECASE)


class CommentReplyService(ServiceBase):
    """Reply to @vibe-manager-agent (or configured manager) mentions in issue comments.

    Listens for issue_comment/created and issue_comment/edited events.
    When a comment mentions a configured manager username, posts a lightweight
    acknowledgement or routes to an agent for a full reply (configurable).
    """

    event_types = ["issue_comment"]

    @property
    def is_dispatch_service(self) -> bool:
        """Comment replies do not initiate new automated work flows."""
        return False

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
    ) -> None:
        self.config = config
        self._github = github or GitHubClient()
        self._mention_re = _build_mention_pattern(config.manager_usernames)

    async def handle_event(self, event: GitHubEvent) -> None:
        if event.action not in ("created", "edited"):
            return

        comment = event.payload.get("comment") or {}
        comment_body = comment.get("body", "")
        author = (comment.get("user") or {}).get("login")
        issue_number = (event.payload.get("issue") or {}).get("number")

        if not issue_number or not self._mention_re.search(comment_body):
            return

        # Sentinel check AFTER mention check to allow mentions within regular comments.
        # This specifically catches comments containing our own 'received your message'
        # acknowledgement that would otherwise re-trigger the bot.
        if "<!-- vibe-ack -->" in comment_body:
            return

        # 2. Author check: skip if comment was posted by the bot itself
        if self.config.bot_username and author == self.config.bot_username:
            logger.bind(domain="orchestra").debug(
                f"Skipping self-mention by bot author {author}"
            )
            return

        log = logger.bind(domain="orchestra", issue=issue_number)
        usernames = ", ".join(f"@{u}" for u in self.config.manager_usernames)
        log.info(f"Manager mention ({usernames}) detected in issue #{issue_number}")

        if self.config.dry_run:
            log.info("Dry run: skipping comment reply")
            return

        self._post_ack(issue_number)

    def _post_ack(self, issue_number: int) -> None:
        """Post a lightweight acknowledgement comment via GitHubClient."""
        usernames_str = ", ".join(f"`@{u}`" for u in self.config.manager_usernames)
        body = (
            f"> 👋 {usernames_str} received your message. "
            "The orchestra server will process this shortly.\n"
            "<!-- vibe-ack -->"
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
