"""StateLabelDispatchService: trigger dispatch based on state/ready label."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.config import OrchestraConfig
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.orchestra.services.status_service import OrchestraStatusService


class StateLabelDispatchService(ServiceBase):
    """Detects issues with 'state/ready' label and triggers manager dispatch."""

    event_types = ["issues"]

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
        executor: ThreadPoolExecutor | None = None,
        status_service: "OrchestraStatusService" | None = None,
        manager: ManagerExecutor | None = None,
        dispatcher: Any | None = None,  # shim
    ) -> None:
        self.config = config
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._manager = (
            manager or dispatcher or ManagerExecutor(config, dry_run=config.dry_run)
        )
        self._github = github or GitHubClient()
        self._status_service = status_service
        self._dispatched_issues: set[int] = set()
        self._in_flight_dispatches: set[int] = set()
        self._dispatch_guard = asyncio.Lock()

    @property
    def _dispatcher(self) -> Any:
        return self._manager

    @_dispatcher.setter
    def _dispatcher(self, value: Any) -> None:
        self._manager = value

    async def handle_event(self, event: GitHubEvent) -> None:
        """Mirror state/ready label events (no-op dispatch)."""
        if event.action != "labeled":
            return

        label_name = (event.payload.get("label") or {}).get("name", "")
        if label_name != "state/ready":
            return

        issue_payload = event.payload.get("issue", {})
        issue = IssueInfo.from_github_payload(issue_payload)
        if issue is None:
            return

        logger.bind(domain="orchestra", issue=issue.number).info(
            f"Observed state/ready label on #{issue.number} "
            "(triggering is now assignee-only)"
        )

    async def on_tick(self) -> None:
        """Periodic scan (no-op dispatch)."""
        pass

    def _list_ready_issues(self) -> list[dict[str, Any]]:
        import json
        import subprocess

        cmd = [
            "gh",
            "issue",
            "list",
            "--label",
            "state/ready",
            "--limit",
            "50",
            "--json",
            "number,title,state,updatedAt,labels,assignees",
        ]
        if self.config.repo:
            cmd.extend(["--repo", self.config.repo])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return cast(list[dict[str, Any]], json.loads(result.stdout))
        except Exception as exc:
            logger.bind(domain="orchestra").error(f"Failed to list ready issues: {exc}")
            return []

    async def _dispatch_if_needed(self, issue: IssueInfo) -> None:
        """Trigger dispatch if no flow exists and issue is not already in flight."""
        log = logger.bind(domain="orchestra", issue=issue.number)

        async with self._dispatch_guard:
            if issue.number in self._in_flight_dispatches:
                log.debug("Skip dispatch: issue already in flight")
                return
            if issue.number in self._dispatched_issues:
                log.debug("Skip dispatch: issue already dispatched")
                return
            self._in_flight_dispatches.add(issue.number)

        dispatched = False
        try:
            if self._status_service:
                active_count = self._status_service.get_active_flow_count()
                if active_count >= self.config.max_concurrent_flows:
                    limit = self.config.max_concurrent_flows
                    log.warning(f"Throttled: Capacity reached ({active_count}/{limit})")
                    return

            if self._has_flow(issue.number):
                log.debug("Skip dispatch: flow already exists")
                dispatched = True
                return

            log.info(f"Triggering manager dispatch for #{issue.number} (state/ready)")
            loop = asyncio.get_event_loop()
            dispatched = await loop.run_in_executor(
                self._executor,
                self._manager.dispatch_manager,
                issue,
            )
        finally:
            async with self._dispatch_guard:
                self._in_flight_dispatches.discard(issue.number)
                if dispatched:
                    self._dispatched_issues.add(issue.number)

    def _has_flow(self, issue_number: int) -> bool:
        """Check if a flow already exists for the issue."""
        try:
            flow = self._manager.orchestrator.get_flow_for_issue(issue_number)
            return flow is not None
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Flow lookup failed for issue #{issue_number}: {exc}"
            )
            return False
