"""Supervisor handoff payload adapter for L2 supervisor execution."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.environment.worktree import WorktreeContext, WorktreeManager
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.runtime.agent_resolver import resolve_supervisor_agent_options
from vibe3.services.orchestra_status_service import OrchestraStatusService

if TYPE_CHECKING:
    from vibe3.services.orchestra_status_service import OrchestraStatusService


@dataclass(frozen=True)
class SupervisorHandoffIssue:
    """Minimal governance issue payload consumed by the handoff service."""

    number: int
    title: str


class SupervisorHandoffService:
    """Build supervisor prompt payload from orchestration context."""

    def __init__(
        self,
        config: OrchestraConfig,
        status_service: OrchestraStatusService | None = None,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self.config = config
        from vibe3.execution.flow_dispatch import FlowManager

        flow_manager = FlowManager(config)
        self._flow_manager = flow_manager
        self._status_service = status_service or OrchestraStatusService(
            config, orchestrator=flow_manager
        )
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )

    @classmethod
    def from_config(
        cls,
        config: OrchestraConfig,
        *,
        executor: ThreadPoolExecutor | None = None,
    ) -> SupervisorHandoffService:
        """Build a supervisor handoff adapter with default read-model dependencies."""
        return cls(config=config, executor=executor)

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

    def acquire_temporary_worktree(self, issue_number: int) -> WorktreeContext:
        """Acquire the isolated temporary worktree for supervisor apply."""
        return self._make_worktree_manager().acquire_temporary_worktree(
            issue_number=issue_number,
            base_branch="main",
        )

    def release_temporary_worktree(self, issue_number: int) -> None:
        """Release the isolated temporary worktree for supervisor apply."""
        wt_path = self._repo_root() / ".worktrees" / "tmp" / str(issue_number)
        context = WorktreeContext(
            path=wt_path,
            is_temporary=True,
            branch=None,
            issue_number=issue_number,
        )
        self._make_worktree_manager().release_temporary_worktree(context)

    def _make_worktree_manager(self) -> WorktreeManager:
        return WorktreeManager(self.config, self._repo_root(), self._flow_manager)

    @staticmethod
    def _repo_root() -> Path:
        git_common_dir = GitClient().get_git_common_dir()
        return Path(git_common_dir).parent if git_common_dir else Path.cwd()
