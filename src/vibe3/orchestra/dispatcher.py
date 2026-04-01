"""Command dispatcher with flow orchestration."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.circuit_breaker import CircuitBreaker
from vibe3.orchestra.command_builder import CommandBuilder
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher_worktree import WorktreeResolverMixin
from vibe3.orchestra.executor import run_command
from vibe3.orchestra.flow_orchestrator import FlowOrchestrator
from vibe3.orchestra.result_handler import DispatchResultHandler

if TYPE_CHECKING:
    from vibe3.prompts.models import PromptRecipe, PromptRenderResult


class Dispatcher(WorktreeResolverMixin):
    """Dispatches commands based on triggers with flow orchestration.

    Refactored to delegate command construction to CommandBuilder and
    post-dispatch logic to DispatchResultHandler.
    """

    def __init__(
        self,
        config: OrchestraConfig,
        dry_run: bool = False,
        repo_path: Path | None = None,
        orchestrator: FlowOrchestrator | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        prompts_path: Path | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.repo_path = repo_path or Path.cwd()
        self.orchestrator = orchestrator or FlowOrchestrator(config)

        # Components
        self.command_builder = CommandBuilder(config, prompts_path=prompts_path)
        self.result_handler = DispatchResultHandler(config, self.orchestrator)

        # Initialize circuit breaker if enabled
        self._circuit_breaker = circuit_breaker
        if self._circuit_breaker is None and config.circuit_breaker.enabled:
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=config.circuit_breaker.failure_threshold,
                cooldown_seconds=config.circuit_breaker.cooldown_seconds,
                half_open_max_tests=config.circuit_breaker.half_open_max_tests,
            )

        # Track last error category for feedback loop
        self._last_error_category: str | None = None

    @property
    def last_manager_render_result(self) -> "PromptRenderResult | None":
        """Proxy for CommandBuilder.last_manager_render_result for compatibility."""
        return self.command_builder.last_manager_render_result

    def _run_command(self, cmd: list[str], cwd: Path, label: str) -> bool:
        """Execute a subprocess command with timeout and structured logging."""
        success, category = run_command(
            cmd, cwd, label, circuit_breaker=self._circuit_breaker
        )
        self._last_error_category = category
        return success

    def run_governance_command(self, cmd: list[str], label: str) -> bool:
        """Run a governance command through the shared dispatch machinery."""
        return self._run_command(cmd, self.repo_path, label)

    @property
    def circuit_breaker_state(self) -> str:
        """Get current circuit breaker state for status reporting."""
        if self._circuit_breaker:
            return self._circuit_breaker.state_value
        return "disabled"

    def dispatch_manager(self, issue: IssueInfo) -> bool:
        """Dispatch manager execution for an issue."""
        log = logger.bind(
            domain="orchestra",
            action="manager_dispatch",
            issue=issue.number,
        )

        cmd = self.command_builder.build_manager_command(issue)

        if self.dry_run:
            log.info("Dry run: skipping flow creation/label updates")
            log.info(f"Dispatching manager: {' '.join(cmd)}")
            log.info("Dry run, skipping execution")
            return True

        # Step 1: ensure flow exists
        try:
            flow = self.orchestrator.create_flow_for_issue(issue)
            log.info(f"Flow ready: branch={flow.get('branch')}")
        except RuntimeError as e:
            log.error(f"Flow creation failed: {e}")
            return False

        flow_branch = str(flow.get("branch") or "").strip()
        if not flow_branch:
            log.error(
                "Cannot dispatch manager: flow branch missing " f"for #{issue.number}"
            )
            return False

        # Step 1.5: resolve manager execution cwd
        manager_cwd, is_temporary = self._resolve_manager_cwd(issue.number, flow_branch)
        if not manager_cwd:
            log.error(
                "Cannot dispatch manager: unable to resolve worktree "
                f"for #{issue.number}"
            )
            return False
        log.info(
            f"Manager dispatch using branch: {flow_branch} "
            f"(cwd={manager_cwd}, temp={is_temporary})"
        )

        try:
            # Step 2: update display label to in-progress (occupancy signal)
            self.result_handler.update_state_label(issue.number, IssueState.IN_PROGRESS)

            # Step 3: run manager execution
            cmd = self._normalize_manager_command(cmd, manager_cwd)
            log.info(f"Dispatching manager: {' '.join(cmd)}")

            success = self._run_command(cmd, manager_cwd, "Manager execution")

            # Step 4: feedback loop - update state based on result
            if success:
                self.result_handler.on_dispatch_success(issue, flow_branch)
            else:
                self.result_handler.on_dispatch_failure(
                    issue, self._last_error_category or "unknown"
                )

            return success
        finally:
            if is_temporary and manager_cwd:
                log.info(f"Recycling temporary worktree: {manager_cwd}")
                try:
                    from vibe3.clients.git_client import GitClient

                    GitClient().remove_worktree(manager_cwd, force=True)
                except Exception as e:
                    log.warning(f"Failed to recycle worktree {manager_cwd}: {e}")

    def dispatch_pr_review(self, pr_number: int) -> bool:
        """Dispatch PR review command."""
        log = logger.bind(
            domain="orchestra",
            action="review_dispatch",
            pr_number=pr_number,
        )

        cmd = self.command_builder.build_pr_review_command(pr_number)
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

    # --- Backward Compatibility Proxies for Tests ---

    def build_manager_command(self, issue: IssueInfo) -> list[str]:
        """Proxy for tests."""
        return self.command_builder.build_manager_command(issue)

    def _build_manager_recipe(self) -> "PromptRecipe":
        """Proxy for tests."""
        return self.command_builder.build_manager_recipe()

    def prepare_pr_review_dispatch(self, pr_number: int) -> tuple[list[str], Path]:
        """Proxy for tests."""
        cmd = self.command_builder.build_pr_review_command(pr_number)
        cwd = self._resolve_review_cwd_for_dispatch(pr_number)
        return cmd, cwd

    def _update_state_label(self, issue_number: int, state: IssueState) -> None:
        """Proxy for tests."""
        self.result_handler.update_state_label(issue_number, state)

    def _on_dispatch_success(self, issue: IssueInfo, flow_branch: str) -> None:
        """Proxy for tests."""
        self.result_handler.on_dispatch_success(issue, flow_branch)

    def _on_dispatch_failure(self, issue: IssueInfo, category: str) -> None:
        """Proxy for tests."""
        self.result_handler.on_dispatch_failure(issue, category)

    def _post_failure_comment(self, issue_number: int, reason: str) -> None:
        """Proxy for tests."""
        self.result_handler.post_failure_comment(issue_number, reason)

    def _record_dispatch_event(self, *args: Any, **kwargs: Any) -> None:
        """Proxy for tests."""
        self.result_handler.record_dispatch_event(*args, **kwargs)
