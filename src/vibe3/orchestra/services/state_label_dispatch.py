"""StateLabelDispatchService: trigger dispatch based on state/ready label."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

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
    ) -> None:
        self.config = config
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._manager = manager or ManagerExecutor(config, dry_run=config.dry_run)
        self._github = github or GitHubClient()
        self._status_service = status_service
        self._dispatched_issues: set[int] = set()
        self._in_flight_dispatches: set[int] = set()
        self._dispatch_guard = asyncio.Lock()

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
