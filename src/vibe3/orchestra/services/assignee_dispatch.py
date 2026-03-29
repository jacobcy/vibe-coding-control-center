"""AssigneeDispatchService: dispatch manager when issue is assigned."""

from __future__ import annotations

import asyncio
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dependency_checker import DependencyChecker
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase
from vibe3.orchestra.models import IssueInfo


class AssigneeDispatchService(ServiceBase):
    """Dispatch manager execution when an issue is assigned to a manager username.

    Primary path: GitHub webhook `issues/assigned` event.
    Fallback: polling tick scans all open issues for missed assignments.
    """

    event_types = ["issues"]

    def __init__(self, config: OrchestraConfig) -> None:
        self.config = config
        self._executor = ThreadPoolExecutor(max_workers=config.max_concurrent_flows)
        self._dispatcher = Dispatcher(config, dry_run=config.dry_run)
        self._dep_checker = DependencyChecker(repo=config.repo)
        # Polling fallback state
        self._assignee_cache: dict[int, frozenset[str]] = {}
        self._cold_start = True

    async def handle_event(self, event: GitHubEvent) -> None:
        """React to issues/assigned webhook event."""
        if event.action != "assigned":
            return

        assignee_login = (event.payload.get("assignee") or {}).get("login", "")

        if assignee_login not in self.config.manager_usernames:
            return

        issue_payload = event.payload.get("issue", {})
        issue = self._parse_issue_payload(issue_payload)
        if issue is None:
            return

        log = logger.bind(domain="orchestra", issue=issue.number)
        log.info(f"Webhook: #{issue.number} assigned to {assignee_login!r} (manager)")

        resolved, blockers = self._dep_checker.check(issue.number)
        if not resolved:
            log.info(f"Deferred: blocked by {blockers}")
            return

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor, self._dispatcher.dispatch_manager, issue
        )

    async def on_tick(self) -> None:
        """Polling fallback: scan open issues for any missed assignments."""
        cmd = [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,labels,assignees,url",
            "--limit",
            "100",
        ]
        if self.config.repo:
            cmd.extend(["--repo", self.config.repo])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception as exc:
            logger.bind(domain="orchestra").error(f"Polling failed: {exc}")
            return

        if result.returncode != 0:
            logger.bind(domain="orchestra").error(
                f"gh issue list failed: {result.stderr.strip()}"
            )
            return

        items: list[dict] = json.loads(result.stdout)

        for item in items:
            assignees = [a["login"] for a in item.get("assignees", [])]
            prev = self._assignee_cache.get(item["number"], frozenset())
            curr = frozenset(assignees)
            self._assignee_cache[item["number"]] = curr

            if self._cold_start:
                continue

            newly_assigned = [
                u for u in (curr - prev) if u in self.config.manager_usernames
            ]
            if not newly_assigned:
                continue

            issue = IssueInfo(
                number=item["number"],
                title=item["title"],
                state=None,
                labels=[lb["name"] for lb in item.get("labels", [])],
                assignees=assignees,
                url=item.get("url"),
            )

            resolved, blockers = self._dep_checker.check(issue.number)
            if not resolved:
                logger.bind(domain="orchestra").info(
                    f"Tick: #{issue.number} blocked by {blockers}, deferring"
                )
                continue

            logger.bind(domain="orchestra").info(
                f"Tick: dispatching #{issue.number} (newly assigned {newly_assigned})"
            )
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._executor, self._dispatcher.dispatch_manager, issue
            )

        self._cold_start = False

    def _parse_issue_payload(self, payload: dict) -> IssueInfo | None:
        try:
            return IssueInfo(
                number=int(payload["number"]),
                title=str(payload.get("title", "")),
                state=None,
                labels=[lb["name"] for lb in payload.get("labels", [])],
                assignees=[a["login"] for a in payload.get("assignees", [])],
                url=payload.get("html_url"),
            )
        except (KeyError, ValueError) as exc:
            logger.bind(domain="orchestra").warning(
                f"Cannot parse issue payload: {exc}"
            )
            return None
