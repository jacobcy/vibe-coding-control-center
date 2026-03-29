"""PRReviewDispatchService: dispatch review when PR enters review workflow."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase


class PRReviewDispatchService(ServiceBase):
    """Dispatch `vibe3 review pr` based on PR reviewer-related events."""

    event_types = ["pull_request"]

    def __init__(self, config: OrchestraConfig) -> None:
        self.config = config
        self._executor = ThreadPoolExecutor(max_workers=config.max_concurrent_flows)
        self._dispatcher = Dispatcher(config, dry_run=config.dry_run)

    async def handle_event(self, event: GitHubEvent) -> None:
        action = event.action
        payload = event.payload
        pr_payload = payload.get("pull_request") or {}
        pr_number = pr_payload.get("number")
        if not isinstance(pr_number, int):
            return

        should_dispatch = False
        reason = ""

        if action == "review_requested":
            reviewer_login = (payload.get("requested_reviewer") or {}).get("login", "")
            if reviewer_login in self.config.manager_usernames:
                should_dispatch = True
                reason = f"requested_reviewer={reviewer_login}"
        elif action == "ready_for_review":
            reviewers = [
                r.get("login", "")
                for r in (pr_payload.get("requested_reviewers") or [])
            ]
            if any(r in self.config.manager_usernames for r in reviewers):
                should_dispatch = True
                reason = "ready_for_review_with_requested_manager"

        if not should_dispatch:
            return

        logger.bind(domain="orchestra", pr=pr_number).info(
            f"PR review dispatch triggered ({reason})"
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self._dispatcher.dispatch_pr_review,
            pr_number,
        )
