"""Supervisor handoff service: consume governance issues and execute supervisors."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.github_client import GitHubClient
from vibe3.environment.worktree import WorktreeManager
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.runtime.agent_resolver import resolve_supervisor_agent_options
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase
from vibe3.services.orchestra_status_service import OrchestraStatusService

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
        from vibe3.manager.flow_manager import FlowManager

        flow_manager = FlowManager(config)
        self._status_service = status_service or OrchestraStatusService(
            config, github=self._github, orchestrator=flow_manager
        )
        self._manager = manager
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._backend = backend or CodeagentBackend()
        self._worktree_manager = WorktreeManager(
            config=config,
            repo_path=Path.cwd(),
            flow_manager=flow_manager,
        )

    async def handle_event(self, event: GitHubEvent) -> None:
        return

    def _list_handoff_issues(self) -> list[SupervisorHandoffIssue]:
        raw = self._github.list_issues(
            limit=100,
            state="open",
            assignee=None,
            repo=self.config.repo,
        )
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

    def build_handoff_payload(
        self, issue: SupervisorHandoffIssue
    ) -> tuple[str, Any, str]:
        """Build payload for handoff execution.

        Returns:
            Tuple of (prompt, agent_options, task_string).
        """
        supervisor_file = self.config.supervisor_handoff.supervisor_file
        log = logger.bind(
            domain="orchestra",
            action="supervisor_handoff",
            issue=issue.number,
            supervisor=supervisor_file,
        )
        log.info("Processing supervisor handoff issue")

        prompt = self._render_supervisor_prompt(supervisor_file)
        options = resolve_supervisor_agent_options(self.config)
        task = self._build_issue_task(issue)

        return prompt, options, task

    def _render_supervisor_prompt(self, supervisor_file: str) -> str:
        governance_cfg = self.config.governance.model_copy(
            update={
                "supervisor_file": supervisor_file,
                "prompt_template": self.config.supervisor_handoff.prompt_template,
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
