"""Unified execution management for Orchestra."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.manager.command_builder import CommandBuilder
from vibe3.manager.flow_manager import FlowManager
from vibe3.manager.result_handler import DispatchResultHandler
from vibe3.manager.worktree_manager import WorktreeManager
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.status_service import OrchestraStatusService
from vibe3.runtime.circuit_breaker import CircuitBreaker
from vibe3.runtime.executor import run_command

if TYPE_CHECKING:
    from vibe3.prompts.models import PromptRenderResult


class ManagerExecutor:
    """Unified manager for execution context.

    Handles flow creation, worktree preparation, agent launch,
    result handling, and recycling.
    """

    def __init__(
        self,
        config: OrchestraConfig,
        repo_path: Path | None = None,
        dry_run: bool = False,
        prompts_path: Path | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        dispatcher: Any | None = None,  # shim
    ):
        self.config = config
        self.repo_path = repo_path or Path.cwd()
        self.dry_run = dry_run

        # Core Components
        self._flow_manager = FlowManager(config)
        self.worktree_manager = WorktreeManager(
            config, self.repo_path, self._flow_manager
        )
        self.command_builder = CommandBuilder(config, prompts_path=prompts_path)
        self.result_handler = DispatchResultHandler(config, self._flow_manager)
        self.status_service = OrchestraStatusService(
            config, orchestrator=self._flow_manager
        )
        self._backend = CodeagentBackend()

        # Execution protection
        self._circuit_breaker = circuit_breaker
        if self._circuit_breaker is None and config.circuit_breaker.enabled:
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=config.circuit_breaker.failure_threshold,
                cooldown_seconds=config.circuit_breaker.cooldown_seconds,
                half_open_max_tests=config.circuit_breaker.half_open_max_tests,
            )

        self._last_error_category: str | None = None
        self._queued_issues: set[int] = set()

    @property
    def flow_manager(self) -> Any:
        """Core flow management component."""
        return self._flow_manager

    @flow_manager.setter
    def flow_manager(self, value: Any) -> None:
        self._flow_manager = value

    @property
    def orchestrator(self) -> Any:
        """Shim for backward compatibility with older Dispatcher interface.

        TODO: Remove after all call-sites migrate to flow_manager.
        """
        return self._flow_manager

    @orchestrator.setter
    def orchestrator(self, value: Any) -> None:
        self._flow_manager = value

    @property
    def queued_issues(self) -> set[int]:
        """Issues waiting for capacity."""
        return self._queued_issues

    @property
    def last_manager_render_result(self) -> "PromptRenderResult | None":
        """Proxy for CommandBuilder.last_manager_render_result."""
        return self.command_builder.last_manager_render_result

    def can_dispatch(self) -> bool:
        """Shim for backward compatibility in tests."""
        try:
            active_count = self.status_service.get_active_flow_count()
            capacity = self.config.max_concurrent_flows
            return active_count < capacity
        except Exception:
            return False

    def _run_command(self, cmd: list[str], cwd: Path, label: str) -> bool:
        """Execute a command via the dispatcher machinery."""
        success, category = run_command(
            cmd, cwd, label, circuit_breaker=self._circuit_breaker
        )
        self._last_error_category = category
        return success

    def dispatch_manager(self, issue: IssueInfo) -> bool:
        """Complete lifecycle for manager dispatch with queuing."""
        log = logger.bind(
            domain="orchestra",
            action="manager_dispatch",
            issue=issue.number,
        )

        active_count = self.status_service.get_active_flow_count()
        capacity = self.config.max_concurrent_flows

        if active_count >= capacity:
            log.warning(
                f"Throttled: Capacity reached ({active_count}/{capacity}). "
                f"Queueing #{issue.number}"
            )
            self._queued_issues.add(issue.number)
            return False

        # If it was in queue, remove it now that we are dispatching
        self._queued_issues.discard(issue.number)

        if self.dry_run:
            cmd = self.command_builder.build_manager_command(issue)
            log.info(f"Dry run: skipping flow/worktree/execution. Cmd: {' '.join(cmd)}")
            return True

        # 1. Flow creation
        try:
            flow = self._flow_manager.create_flow_for_issue(issue)
            flow_branch = str(flow.get("branch") or "").strip()
            if not flow_branch:
                log.error("Flow branch missing")
                return False
        except Exception as e:
            log.error(f"Flow creation failed: {e}")
            return False

        # 2. Worktree preparation
        # Use private method so subclasses can override for mock compatibility
        manager_cwd, is_temporary = self._resolve_manager_cwd(issue.number, flow_branch)
        if not manager_cwd:
            log.error("Unable to resolve worktree")
            return False

        log.info(f"Using worktree: {manager_cwd} (temp={is_temporary})")

        try:
            # 3. Label update
            self.result_handler.update_state_label(issue.number, IssueState.CLAIMED)

            # 4. Command execution
            cmd = [
                "uv",
                "run",
                "python",
                "src/vibe3/cli.py",
                "run",
                "--manager-issue",
                str(issue.number),
                "--sync",
            ]
            handle = self._backend.start_async_command(
                cmd,
                execution_name=f"vibe3-manager-{issue.number}",
                cwd=manager_cwd,
                env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            )
            log.info(
                f"Started manager async session: {handle.tmux_session} "
                f"(log: {handle.log_path})"
            )
            self._flow_manager.store.add_event(
                flow_branch,
                "manager_dispatched",
                "system",
                detail=(
                    f"Dispatched manager to tmux session: {handle.tmux_session}\n"
                    f"Log: {handle.log_path}"
                ),
                refs={
                    "tmux_session": handle.tmux_session,
                    "log_path": str(handle.log_path),
                    "issue": str(issue.number),
                },
            )
            # Async dispatch: only record launch here.
            # The child process records its own manager_started/completed/aborted
            # lifecycle events via pipeline.py, and run.py:_run_manager_issue_mode
            # handles final result handling.  Calling on_dispatch_success here
            # would prematurely mark the dispatch as successful before the child
            # has even started its work.
            return True
        finally:
            # 6. Maybe recycle
            if is_temporary and manager_cwd:
                if self._should_recycle(issue.number):
                    self.worktree_manager.recycle(manager_cwd)
                else:
                    log.info(
                        f"Preserving worktree at {manager_cwd} "
                        "(issue still in-progress)"
                    )

    def dispatch_pr_review(self, pr_number: int) -> bool:
        """Complete lifecycle for PR review dispatch with queuing."""
        log = logger.bind(
            domain="orchestra",
            action="review_dispatch",
            pr_number=pr_number,
        )

        active_count = self.status_service.get_active_flow_count()
        capacity = self.config.max_concurrent_flows

        if active_count >= capacity:
            log.warning(
                f"Throttled: Capacity reached ({active_count}/{capacity}). "
                f"Queueing review for #{pr_number}"
            )
            # Use negative numbers for PRs in queue
            self._queued_issues.add(-pr_number)
            return False

        self._queued_issues.discard(-pr_number)

        cmd = self.command_builder.build_pr_review_command(pr_number)

        # Resolve CWD
        # Use private method so subclasses can override
        review_cwd = self._resolve_review_cwd_for_dispatch(pr_number)

        log.info(f"Dispatching review: {' '.join(cmd)} (cwd={review_cwd})")

        if self.dry_run:
            log.info("Dry run, skipping execution")
            return True

        return self._run_command(cmd, review_cwd, "Review execution")

    def _resolve_review_cwd_for_dispatch(self, pr_number: int) -> Path:
        """Helper to resolve PR review cwd based on config."""
        if self.config.pr_review_dispatch.use_worktree:
            return self.repo_path
        return self._resolve_review_cwd(pr_number)

    def _should_recycle(self, issue_number: int) -> bool:
        """Decide if we should recycle the worktree now."""
        try:
            from vibe3.services.label_service import LabelService

            state = LabelService(repo=self.config.repo).get_state(issue_number)
            return state not in {
                IssueState.CLAIMED,
                IssueState.IN_PROGRESS,
                IssueState.HANDOFF,
                IssueState.REVIEW,
                IssueState.MERGE_READY,
            }
        except Exception:
            return False

    # --- Methods that delegate to worktree_manager, allowing subclass override ---

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
