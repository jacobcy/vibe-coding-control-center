"""StateLabelDispatchService: trigger dispatch based on state/ready label."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    pass


class StateLabelDispatchService(ServiceBase):
    """Detects issues with 'state/ready' label and triggers manager dispatch.

    This service implements the 'label-driven' orchestration flow:
    1. Orchestra agent (AI) or Human adds 'state/ready' label to an issue.
    2. This service detects the label via:
       - GitHub webhook `issues/labeled` event (real-time)
       - Periodic on_tick() scan (polling fallback)
    3. It triggers Dispatcher.dispatch_manager(issue) if not already running.
    """

    # Subscribe to issues events to catch label changes in real-time
    event_types = ["issues"]

    def __init__(
        self,
        config: OrchestraConfig,
        dispatcher: Dispatcher | None = None,
        github: GitHubClient | None = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self.config = config
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._dispatcher = dispatcher or Dispatcher(config, dry_run=config.dry_run)
        self._github = github or GitHubClient()
        self._dispatched_issues: set[int] = set()

    async def handle_event(self, event: GitHubEvent) -> None:
        """React to issues/labeled webhook event."""
        if event.action != "labeled":
            return

        label_name = (event.payload.get("label") or {}).get("name", "")
        if label_name != "state/ready":
            return

        issue_payload = event.payload.get("issue", {})
        issue = IssueInfo.from_github_payload(issue_payload)
        if issue is None:
            return

        # Double check: ensure it doesn't also have in-progress
        # (webhook payload 'issue' reflects state AFTER the action)
        labels = [lb.get("name", "") for lb in issue_payload.get("labels", [])]
        if "state/in-progress" in labels:
            return

        log = logger.bind(domain="orchestra", issue=issue.number, source="webhook")
        log.info(f"Webhook: #{issue.number} labeled with {label_name!r}")

        await self._dispatch_if_needed(issue)

    async def on_tick(self) -> None:
        """Scan for issues with state/ready label and no state/in-progress."""
        log = logger.bind(domain="orchestra", service="StateLabelDispatch")

        # Query issues with state/ready label
        # Note: 'gh issue list --label state/ready'
        raw = await asyncio.get_running_loop().run_in_executor(
            self._executor,
            self._list_ready_issues,
        )

        if not raw:
            return

        ready_issues: list[IssueInfo] = []
        for item in raw:
            issue_number = item.get("number")
            if not issue_number:
                continue

            labels = [lb.get("name", "") for lb in item.get("labels", [])]
            # Skip if it's already in-progress (occupancy signal)
            if "state/in-progress" in labels:
                continue

            issue = IssueInfo.from_github_payload(item)
            if issue:
                ready_issues.append(issue)

        if ready_issues:
            log.info(f"Found {len(ready_issues)} issues ready for dispatch")

        for issue in ready_issues:
            await self._dispatch_if_needed(issue)

    def _list_ready_issues(self) -> list[dict[str, Any]]:
        """Synchronous wrapper for gh issue list --label state/ready."""
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
        """Trigger dispatch if no flow exists and not already dispatched this tick."""
        log = logger.bind(domain="orchestra", issue=issue.number)

        # Skip if flow already exists
        if self._has_flow(issue.number):
            self._dispatched_issues.add(issue.number)
            log.debug("Skip dispatch: flow already exists")
            return

        # Trigger dispatcher
        log.info(f"Triggering manager dispatch for #{issue.number} (state/ready)")
        loop = asyncio.get_running_loop()
        dispatched = await loop.run_in_executor(
            self._executor,
            self._dispatcher.dispatch_manager,
            issue,
        )
        if dispatched:
            self._dispatched_issues.add(issue.number)

    def _has_flow(self, issue_number: int) -> bool:
        """Check if a flow already exists for the issue."""
        try:
            flow = self._dispatcher.orchestrator.get_flow_for_issue(issue_number)
            return flow is not None
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Flow lookup failed for issue #{issue_number}: {exc}"
            )
            return False
