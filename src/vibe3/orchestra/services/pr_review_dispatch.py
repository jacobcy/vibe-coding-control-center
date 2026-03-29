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
        pr_number = self._extract_pr_number(payload)
        if pr_number is None:
            logger.bind(domain="orchestra", action="review_dispatch").debug(
                "Skip PR review dispatch: cannot parse pr_number from payload"
            )
            return

        should_dispatch, reason = self._should_dispatch(action, payload)

        if not should_dispatch:
            logger.bind(domain="orchestra", pr=pr_number).debug(
                f"Skip PR review dispatch ({reason})"
            )
            return

        cmd, review_cwd = self._dispatcher.prepare_pr_review_dispatch(pr_number)
        logger.bind(domain="orchestra", pr=pr_number).info(
            f"PR review dispatch triggered ({reason})"
        )
        logger.bind(domain="orchestra", pr=pr_number).info(
            f"Parsed webhook to command: {' '.join(cmd)} (cwd={review_cwd})"
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            self._dispatcher.dispatch_pr_review,
            pr_number,
        )

    def _extract_pr_number(self, payload: dict) -> int | None:
        value = payload.get("number")
        if isinstance(value, int):
            return value

        pr_payload = payload.get("pull_request") or {}
        nested = pr_payload.get("number")
        if isinstance(nested, int):
            return nested

        return None

    def _should_dispatch(self, action: str, payload: dict) -> tuple[bool, str]:
        pr_payload = payload.get("pull_request") or {}
        reviewers = [
            r.get("login", "") for r in (pr_payload.get("requested_reviewers") or [])
        ]

        if action == "review_requested":
            reviewer_login = (payload.get("requested_reviewer") or {}).get("login", "")
            if reviewer_login in self.config.manager_usernames:
                return True, f"requested_reviewer={reviewer_login}"
            if any(r in self.config.manager_usernames for r in reviewers):
                return True, "review_requested_with_requested_manager"
            return False, "review_requested_without_configured_manager"

        if action == "ready_for_review":
            if any(r in self.config.manager_usernames for r in reviewers):
                return True, "ready_for_review_with_requested_manager"
            return False, "ready_for_review_without_configured_manager"

        return False, f"unsupported_action={action}"
