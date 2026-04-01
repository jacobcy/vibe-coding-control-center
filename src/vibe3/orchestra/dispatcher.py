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
from vibe3.orchestra.services.status_service import OrchestraStatusService

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
        status_service: OrchestraStatusService | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.repo_path = repo_path or Path.cwd()
        self.orchestrator = orchestrator or FlowOrchestrator(config)
        self._status_service = status_service or OrchestraStatusService(
            config, orchestrator=self.orchestrator
        )

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

        if not self.can_dispatch():
            log.warning(
                f"Dispatch skipped for #{issue.number}: system at capacity "
                f"({self.config.max_concurrent_flows} flows)"
            )
            return False

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
                # Worktree recycling is now handled by GovernanceService based on
                # Flow completion. We no longer delete worktrees immediately upon
                # manager process exit to protect ongoing asynchronous tasks
                # (e.g. vibe3 run --async) and preserve state.
                log.info(
                    f"Flow environment preserved at: {manager_cwd}. "
                    "Recycling managed by governance policy."
                )

    def dispatch_pr_review(self, pr_number: int) -> bool:
        """Dispatch PR review command."""
        log = logger.bind(
            domain="orchestra",
            action="review_dispatch",
            pr_number=pr_number,
        )

        if not self.can_dispatch():
            log.warning(f"Review dispatch skipped for #{pr_number}: system at capacity")
            return False

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

    def _should_skip_cleanup(self, issue_number: int) -> bool:
        """Helper to decide if we should skip recycling a worktree.

        Returns True if the issue state label is still 'in-progress'.
        """
        try:
            from vibe3.models.orchestration import IssueState
            from vibe3.services.label_service import LabelService

            state = LabelService(repo=self.config.repo).get_state(issue_number)
            return state == IssueState.IN_PROGRESS
        except Exception:
            # On error, play it safe and skip cleanup
            return True

    def can_dispatch(self) -> bool:
        """Unified check: is the system allowed to take on more work?

        Checks global active flow count via status_service.
        """
        if not self._status_service:
            return True

        try:
            active_count = self._status_service.get_active_flow_count()
            capacity = self.config.max_concurrent_flows
            if active_count >= capacity:
                logger.bind(domain="orchestra").warning(
                    f"Throttled: Capacity reached ({active_count}/{capacity})"
                )
                return False
            return True
        except Exception as e:
            logger.bind(domain="orchestra").error(f"Capacity check failed: {e}")
            return False
