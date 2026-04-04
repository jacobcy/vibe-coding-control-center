"""Supervisor handoff service: consume governance issues and execute supervisors."""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.runner import CodeagentExecutionService
from vibe3.clients.github_client import GitHubClient
from vibe3.config.settings import VibeConfig
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.status_service import OrchestraStatusService
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.manager.manager_executor import ManagerExecutor


@dataclass(frozen=True)
class SupervisorHandoffIssue:
    """Minimal governance issue payload consumed by the handoff service."""

    number: int
    title: str


def _normalize_labels(raw_labels: object) -> list[str]:
    labels: list[str] = []
    if not isinstance(raw_labels, list):
        return labels
    for item in raw_labels:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name:
                labels.append(name)
        elif isinstance(item, str) and item:
            labels.append(item)
    return labels


class SupervisorHandoffService(ServiceBase):
    """Consume governance handoff issues and recycle them after execution."""

    event_types: list[str] = []

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient | None = None,
        status_service: OrchestraStatusService | None = None,
        manager: ManagerExecutor | None = None,
        executor: ThreadPoolExecutor | None = None,
        backend: CodeagentBackend | None = None,
    ) -> None:
        self.config = config
        self._github = github or GitHubClient()
        self._status_service = status_service or OrchestraStatusService(
            config, github=self._github
        )
        self._manager = manager
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._backend = backend or CodeagentBackend()
        self._in_flight: set[int] = set()

    async def handle_event(self, event: GitHubEvent) -> None:
        return

    async def on_tick(self) -> None:
        candidates = await asyncio.get_event_loop().run_in_executor(
            self._executor,
            self._list_handoff_issues,
        )
        if not candidates:
            self._in_flight.clear()
            return

        active_issue_numbers = {issue.number for issue in candidates}
        self._in_flight.intersection_update(active_issue_numbers)

        for issue in candidates:
            if issue.number in self._in_flight:
                continue
            self._in_flight.add(issue.number)
            try:
                await asyncio.get_event_loop().run_in_executor(
                    self._executor,
                    self._process_issue,
                    issue,
                )
            except Exception:
                self._in_flight.discard(issue.number)
                raise

    def _list_handoff_issues(self) -> list[SupervisorHandoffIssue]:
        raw = self._github.list_issues(limit=100, state="open", assignee=None)
        issue_label = self.config.supervisor_handoff.issue_label
        handoff_label = self.config.supervisor_handoff.handoff_state_label

        candidates: list[SupervisorHandoffIssue] = []
        for item in raw:
            number = item.get("number")
            title = item.get("title")
            if not isinstance(number, int) or not isinstance(title, str):
                continue
            labels = _normalize_labels(item.get("labels"))
            if issue_label not in labels or handoff_label not in labels:
                continue
            candidates.append(
                SupervisorHandoffIssue(
                    number=number,
                    title=title,
                )
            )
        return candidates

    def _process_issue(self, issue: SupervisorHandoffIssue) -> None:
        supervisor_file = self.config.supervisor_handoff.supervisor_file
        log = logger.bind(
            domain="orchestra",
            action="supervisor_handoff",
            issue=issue.number,
            supervisor=supervisor_file,
        )
        log.info("Processing supervisor handoff issue")

        prompt = self._render_supervisor_prompt(supervisor_file)

        if self.config.dry_run:
            log.info("Dry run enabled; skipping supervisor handoff dispatch")
            return

        self._dispatch_supervisor_prompt(issue, prompt)
        log.info(
            "Dispatched supervisor handoff issue",
            issue_number=issue.number,
            supervisor_file=supervisor_file,
        )

    def _render_supervisor_prompt(self, supervisor_file: str) -> str:
        governance_cfg = self.config.governance.model_copy(
            update={
                "supervisor_file": supervisor_file,
                "include_supervisor_content": True,
                "dry_run": False,
            }
        )
        config = self.config.model_copy(update={"governance": governance_cfg})
        service = GovernanceService(
            config=config,
            status_service=self._status_service,
            manager=self._manager,
            executor=self._executor,
        )
        return service.render_current_plan()

    def _dispatch_supervisor_prompt(
        self,
        issue: SupervisorHandoffIssue,
        prompt: str,
    ) -> None:
        runtime_config = VibeConfig.get_defaults()
        options = CodeagentExecutionService(runtime_config).resolve_agent_options("run")
        self._backend.start_async(
            prompt=prompt,
            options=options,
            task=self._build_issue_task(issue),
            execution_name=f"vibe3-supervisor-issue-{issue.number}",
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        )

    def _build_issue_task(self, issue: SupervisorHandoffIssue) -> str:
        repo_hint = f" in repo {self.config.repo}" if self.config.repo else ""
        supervisor_file = self.config.supervisor_handoff.supervisor_file
        return (
            f"Process governance issue #{issue.number}{repo_hint}: {issue.title}\n"
            f"This issue has already been handed to {supervisor_file} by the "
            "trigger layer.\n"
            "Read the issue directly, verify the findings, perform the "
            "allowed actions, "
            "comment the outcome on the same issue, and close it when complete."
        )
