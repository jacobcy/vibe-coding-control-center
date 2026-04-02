"""Shim for Dispatcher - delegates to ManagerExecutor.

This file is maintained for backward compatibility during the refactor.
New code should use vibe3.manager.manager_executor.ManagerExecutor directly.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig

if TYPE_CHECKING:
    from vibe3.prompts.models import PromptRecipe


class Dispatcher(ManagerExecutor):
    """Shim for Dispatcher - inherits from ManagerExecutor for mock compatibility."""

    def __init__(
        self,
        config: OrchestraConfig,
        dry_run: bool = False,
        repo_path: Path | None = None,
        orchestrator: Any | None = None,
        circuit_breaker: Any | None = None,
        prompts_path: Path | None = None,
        status_service: Any | None = None,
    ):
        super().__init__(
            config=config,
            dry_run=dry_run,
            repo_path=repo_path,
            prompts_path=prompts_path,
            circuit_breaker=circuit_breaker,
        )
        # Set orchestrator if provided
        if orchestrator:
            self.orchestrator = orchestrator

        # Compatibility: expose attributes that might be accessed directly
        if status_service:
            self.status_service = status_service

    def run_governance_command(self, cmd: list[str], label: str) -> bool:
        return self._run_command(cmd, self.repo_path, label)

    # --- Backward Compatibility Proxies for Tests ---

    def build_manager_command(self, issue: IssueInfo) -> list[str]:
        return self.command_builder.build_manager_command(issue)

    def _build_manager_recipe(self) -> "PromptRecipe":
        return self.command_builder.build_manager_recipe()

    def prepare_pr_review_dispatch(self, pr_number: int) -> tuple[list[str], Path]:
        cmd = self.command_builder.build_pr_review_command(pr_number)
        cwd = self._resolve_review_cwd_for_dispatch(pr_number)
        return cmd, cwd

    def _resolve_review_cwd_for_dispatch(self, pr_number: int) -> Path:
        if self.config.pr_review_dispatch.use_worktree:
            return self.repo_path
        return self._resolve_review_cwd(pr_number)

    def _update_state_label(self, issue_number: int, state: IssueState) -> None:
        self.result_handler.update_state_label(issue_number, state)

    def _on_dispatch_success(self, issue: IssueInfo, flow_branch: str) -> None:
        self.result_handler.on_dispatch_success(issue, flow_branch)

    def _on_dispatch_failure(self, issue: IssueInfo, category: str) -> None:
        self.result_handler.on_dispatch_failure(issue, category)

    def _post_failure_comment(self, issue_number: int, reason: str) -> None:
        self.result_handler.post_failure_comment(issue_number, reason)

    def _record_dispatch_event(self, *args: Any, **kwargs: Any) -> None:
        self.result_handler.record_dispatch_event(*args, **kwargs)

    # --- Override ManagerExecutor methods to use the instance's own
    # methods (which might be patched) ---

    def _resolve_manager_cwd(
        self, issue_number: int, flow_branch: str
    ) -> tuple[Path | None, bool]:
        return self.worktree_manager._resolve_manager_cwd(issue_number, flow_branch)

    def _normalize_manager_command(self, cmd: list[str], cwd: Path) -> list[str]:
        return self.worktree_manager._normalize_manager_command(cmd, cwd)

    def _ensure_manager_worktree(
        self, issue_number: int, branch: str
    ) -> tuple[Path | None, bool]:
        return self.worktree_manager._ensure_manager_worktree(issue_number, branch)

    def _resolve_review_cwd(self, pr_number: int) -> Path:
        return self.worktree_manager._resolve_review_cwd(pr_number)

    def _is_current_branch(self, branch: str) -> bool:
        return self.worktree_manager._is_current_branch(branch)

    def _find_worktree_for_branch(self, branch: str) -> Path | None:
        return self.worktree_manager._find_worktree_for_branch(branch)

    def _supports_run_worktree_option(self, cwd: Path) -> bool:
        return self.worktree_manager._supports_run_worktree_option(cwd)
