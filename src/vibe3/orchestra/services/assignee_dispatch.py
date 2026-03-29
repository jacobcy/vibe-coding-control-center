"""AssigneeDispatchService: dispatch manager when issue is assigned."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from vibe3.clients.github_client import GitHubClient
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
        self._dispatched_issues: set[int] = set()
        self._github = GitHubClient()

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

        await self._dispatch_if_ready(issue, source="webhook")

    async def on_tick(self) -> None:
        """Polling fallback: scan open issues for any missed assignments."""
        raw = await asyncio.get_event_loop().run_in_executor(
            self._executor,
            lambda: self._github.list_issues_with_assignees(
                limit=100, repo=self.config.repo
            ),
        )

        ready: list[IssueInfo] = []
        blocked: list[tuple[int, list[int]]] = []

        for item in raw:
            assignees = [a["login"] for a in item.get("assignees", [])]
            prev = self._assignee_cache.get(item["number"], frozenset())
            curr = frozenset(assignees)
            self._assignee_cache[item["number"]] = curr

            if not any(user in self.config.manager_usernames for user in curr):
                continue

            issue = IssueInfo(
                number=item["number"],
                title=item["title"],
                state=None,
                labels=[lb["name"] for lb in item.get("labels", [])],
                assignees=assignees,
                url=item.get("url"),
            )
            if self._has_flow(issue.number):
                continue

            resolved, blockers = self._dep_checker.check(issue.number)
            if not resolved:
                blocked.append((issue.number, blockers))
                continue

            newly_assigned = [
                u for u in (curr - prev) if u in self.config.manager_usernames
            ]
            if self._cold_start or newly_assigned:
                ready.append(issue)

        if blocked:
            logger.bind(domain="orchestra").info(
                "Tick summary: blocked issues "
                + ", ".join(f"#{n} by {deps}" for n, deps in blocked)
            )

        for issue in self._sort_by_priority(ready):
            await self._dispatch_if_ready(issue, source="tick")

        self._cold_start = False

    async def _dispatch_if_ready(self, issue: IssueInfo, source: str) -> None:
        log = logger.bind(domain="orchestra", issue=issue.number, source=source)

        if self._has_flow(issue.number):
            self._dispatched_issues.add(issue.number)
            log.debug("Skip dispatch: flow already exists")
            return

        resolved, blockers = self._dep_checker.check(issue.number)
        if not resolved:
            log.info(f"Deferred: blocked by {blockers}")
            return

        loop = asyncio.get_event_loop()
        dispatched = await loop.run_in_executor(
            self._executor, self._dispatcher.dispatch_manager, issue
        )
        if dispatched:
            self._dispatched_issues.add(issue.number)

    def _has_flow(self, issue_number: int) -> bool:
        try:
            flow = self._dispatcher.orchestrator.get_flow_for_issue(issue_number)
            return flow is not None
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Flow lookup failed for issue #{issue_number}: {exc}"
            )
            return False

    def _sort_by_priority(self, issues: list[IssueInfo]) -> list[IssueInfo]:
        priority_map = {
            "priority/urgent": 0,
            "priority/high": 1,
            "priority/medium": 2,
            "priority/low": 3,
        }

        def score(issue: IssueInfo) -> tuple[int, int]:
            values = [priority_map.get(lb.lower(), 2) for lb in issue.labels]
            best = min(values) if values else 2
            return (best, issue.number)

        return sorted(issues, key=score)

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
