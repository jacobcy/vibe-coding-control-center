"""AssigneeDispatchService: dispatch manager when issue is assigned."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dependency_checker import DependencyChecker
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase
from vibe3.orchestra.services.status_service import OrchestraStatusService

_PRIORITY_MAP: dict[str, int] = {
    "priority/urgent": 0,
    "priority/high": 1,
    "priority/medium": 2,
    "priority/low": 3,
}
_PRIORITY_DEFAULT = 2


class AssigneeDispatchService(ServiceBase):
    """Dispatch manager execution when an issue is assigned to a manager username."""

    event_types = ["issues"]

    def __init__(
        self,
        config: OrchestraConfig,
        dispatcher: Any | None = None,
        github: GitHubClient | None = None,
        executor: ThreadPoolExecutor | None = None,
        status_service: OrchestraStatusService | None = None,
        manager: ManagerExecutor | None = None,
    ) -> None:
        self.config = config
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        # Compatibility: prefer 'manager', fall back to 'dispatcher'
        self._manager = (
            manager or dispatcher or ManagerExecutor(config, dry_run=config.dry_run)
        )

        self._status_service = status_service or OrchestraStatusService(
            config, orchestrator=self._manager.flow_manager
        )
        self._dep_checker = DependencyChecker(
            repo=config.repo,
            github=github,
        )
        # Polling fallback state
        self._assignee_cache: dict[int, frozenset[str]] = {}
        self._cold_start = True
        self._dispatched_issues: set[int] = set()
        self._github = github or GitHubClient()

    @property
    def _dispatcher(self) -> Any:
        return self._manager

    @_dispatcher.setter
    def _dispatcher(self, value: Any) -> None:
        self._manager = value

    async def handle_event(self, event: GitHubEvent) -> None:
        """React to issues/assigned webhook event."""
        if event.action != "assigned":
            return

        assignee_login = (event.payload.get("assignee") or {}).get("login", "")

        if assignee_login not in self.config.manager_usernames:
            return

        issue_payload = event.payload.get("issue", {})
        issue = IssueInfo.from_github_payload(issue_payload)
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

        if self._cold_start:
            self._assignee_cache = {
                item["number"]: frozenset(a["login"] for a in item.get("assignees", []))
                for item in raw
                if "number" in item
            }
            self._dispatched_issues = {
                n for n in self._dispatched_issues if n in self._assignee_cache
            }
            self._cold_start = False
            logger.bind(domain="orchestra").info(
                f"Tick warm-up: cached assignees for {len(self._assignee_cache)} issues"
            )
            return

        ready: list[IssueInfo] = []
        blocked: list[tuple[int, list[int]]] = []

        for item in raw:
            assignees = [a["login"] for a in item.get("assignees", [])]
            prev = self._assignee_cache.get(item["number"], frozenset())
            curr = frozenset(assignees)
            self._assignee_cache[item["number"]] = curr

            if not any(user in self.config.manager_usernames for user in curr):
                continue

            issue = IssueInfo.from_github_payload(item)
            if issue is None:
                continue
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

        seen_numbers = {item["number"] for item in raw}
        self._assignee_cache = {
            k: v for k, v in self._assignee_cache.items() if k in seen_numbers
        }
        self._dispatched_issues = {
            n for n in self._dispatched_issues if n in seen_numbers
        }

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

        try:
            active_count = self._status_service.get_active_flow_count()
            capacity = self.config.max_concurrent_flows
            if active_count >= capacity:
                log.warning(f"Deferred: system at capacity ({active_count}/{capacity})")
                return
        except Exception as e:
            log.error(f"Capacity check failed: {e}")

        loop = asyncio.get_event_loop()
        dispatched = await loop.run_in_executor(
            self._executor, self._manager.dispatch_manager, issue
        )
        if dispatched:
            self._dispatched_issues.add(issue.number)

    def _has_flow(self, issue_number: int) -> bool:
        try:
            flow = self._manager.orchestrator.get_flow_for_issue(issue_number)
            return flow is not None
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Flow lookup failed for issue #{issue_number}: {exc}"
            )
            return False

    def _sort_by_priority(self, issues: list[IssueInfo]) -> list[IssueInfo]:
        def score(issue: IssueInfo) -> tuple[int, int]:
            priorities = [
                _PRIORITY_MAP.get(lb.lower(), _PRIORITY_DEFAULT) for lb in issue.labels
            ]
            best = min(priorities) if priorities else _PRIORITY_DEFAULT
            return (best, issue.number)

        return sorted(issues, key=score)
