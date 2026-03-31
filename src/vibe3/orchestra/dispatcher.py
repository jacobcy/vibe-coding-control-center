"""Command dispatcher with flow orchestration."""

from pathlib import Path

from loguru import logger

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.circuit_breaker import CircuitBreaker
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher_worktree import WorktreeResolverMixin
from vibe3.orchestra.executor import run_command
from vibe3.orchestra.flow_orchestrator import FlowOrchestrator
from vibe3.orchestra.prompts import build_manager_command, render_manager_prompt
from vibe3.prompts.models import PromptRecipe, PromptRenderResult
from vibe3.prompts.template_loader import DEFAULT_PROMPTS_PATH


class Dispatcher(WorktreeResolverMixin):
    """Dispatches commands based on triggers with flow orchestration."""

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
        self._prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
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
        # Set after build_manager_command; used for dry-run provenance logging
        self.last_manager_render_result: PromptRenderResult | None = None

    def _run_command(self, cmd: list[str], cwd: Path, label: str) -> bool:
        """Execute a subprocess command with timeout and structured logging.

        Delegates to executor.run_command.
        """
        success, category = run_command(
            cmd, cwd, label, circuit_breaker=self._circuit_breaker
        )
        self._last_error_category = category
        return success

    def run_governance_command(self, cmd: list[str], label: str) -> bool:
        """Run a governance command through the shared dispatch machinery.

        Uses the same circuit breaker and error classification as manager
        dispatch, ensuring governance failures are tracked consistently.
        Executes in repo_path (not a specific worktree).
        """
        return self._run_command(cmd, self.repo_path, label)

    @property
    def circuit_breaker_state(self) -> str:
        """Get current circuit breaker state for status reporting."""
        if self._circuit_breaker:
            return self._circuit_breaker.state_value
        return "disabled"

    def dispatch_manager(self, issue: IssueInfo) -> bool:
        """Dispatch manager execution for an assignee-triggered issue."""
        log = logger.bind(
            domain="orchestra",
            action="manager_dispatch",
            issue=issue.number,
        )

        render_result = render_manager_prompt(
            self.config, issue, prompts_path=self._prompts_path
        )
        self.last_manager_render_result = render_result
        cmd = build_manager_command(self.config, render_result.rendered_text)

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

        # Step 1.5: resolve manager execution cwd without mutating the
        # serve process branch context.
        manager_cwd = self._resolve_manager_cwd(issue.number, flow_branch)
        if not manager_cwd:
            log.error(
                "Cannot dispatch manager: unable to resolve worktree "
                f"for #{issue.number}"
            )
            return False
        log.info(f"Manager dispatch using branch: {flow_branch} (cwd={manager_cwd})")

        # Step 2: update display label
        self._update_state_label(issue.number, IssueState.IN_PROGRESS)

        # Step 3: run manager execution
        cmd = self._normalize_manager_command(cmd, manager_cwd)
        log.info(f"Dispatching manager: {' '.join(cmd)}")

        success = self._run_command(cmd, manager_cwd, "Manager execution")

        # Step 4: feedback loop - update state based on result
        if success:
            self._on_dispatch_success(issue, flow_branch)
        else:
            self._on_dispatch_failure(issue, self._last_error_category or "unknown")

        return success

    def dispatch_pr_review(self, pr_number: int) -> bool:
        """Dispatch PR review command for reviewer-triggered events."""
        log = logger.bind(
            domain="orchestra",
            action="review_dispatch",
            pr_number=pr_number,
        )

        cmd, review_cwd = self.prepare_pr_review_dispatch(pr_number)
        log.info(f"Dispatching review: {' '.join(cmd)} (cwd={review_cwd})")

        if self.dry_run:
            log.info("Dry run, skipping execution")
            return True

        return self._run_command(cmd, review_cwd, "Review execution")

    def build_manager_command(self, issue: IssueInfo) -> list[str]:
        """Proxy for prompts.build_manager_command, used in tests."""
        render_result = render_manager_prompt(
            self.config, issue, prompts_path=self._prompts_path
        )
        self.last_manager_render_result = render_result
        return build_manager_command(self.config, render_result.rendered_text)

    def _build_manager_recipe(self) -> PromptRecipe:
        """Proxy for prompts.build_manager_recipe, used in tests."""
        from vibe3.orchestra.prompts import build_manager_recipe

        return build_manager_recipe(self.config)

    def prepare_pr_review_dispatch(self, pr_number: int) -> tuple[list[str], Path]:
        """Prepare executable PR review command and working directory."""
        cmd = ["uv", "run", "python", "-m", "vibe3", "review", "pr", str(pr_number)]
        if self.config.pr_review_dispatch.async_mode:
            cmd.append("--async")
        if self.config.pr_review_dispatch.use_worktree:
            cmd.append("--worktree")
            review_cwd = self.repo_path
        else:
            review_cwd = self._resolve_review_cwd(pr_number)
        return cmd, review_cwd

    def _update_state_label(self, issue_number: int, state: IssueState) -> None:
        """Update issue state label (display only, does not drive logic)."""
        try:
            from vibe3.services.label_service import LabelService

            LabelService(repo=self.config.repo).confirm_issue_state(
                issue_number,
                state,
                actor="orchestra:manager",
                force=True,
            )
        except Exception as e:
            logger.bind(domain="orchestra").warning(
                f"Failed to update label for #{issue_number}: {e}"
            )

    def _on_dispatch_success(self, issue: IssueInfo, flow_branch: str) -> None:
        """Handle successful dispatch: check PR and update state to review.

        Args:
            issue: Issue that was dispatched
            flow_branch: Flow branch name
        """
        log = logger.bind(
            domain="orchestra",
            action="dispatch_success",
            issue=issue.number,
        )

        # Check if PR exists
        pr_number = self.orchestrator.get_pr_for_issue(issue.number)
        if pr_number:
            # Update state to review
            self._update_state_label(issue.number, IssueState.REVIEW)
            log.info(
                f"Dispatch success, PR #{pr_number} exists, "
                f"advancing to state/review"
            )

            # Record event in flow history
            self._record_dispatch_event(
                flow_branch,
                success=True,
                issue_number=issue.number,
                pr_number=pr_number,
            )
        else:
            # No PR yet, keep in-progress state
            log.info("Dispatch success, no PR yet, keeping state/in-progress")

            # Record event in flow history
            self._record_dispatch_event(
                flow_branch,
                success=True,
                issue_number=issue.number,
                pr_number=None,
            )

    def _on_dispatch_failure(self, issue: IssueInfo, category: str) -> None:
        """Handle dispatch failure: update state and post comment.

        Args:
            issue: Issue that failed to dispatch
            category: Error category (api_error, timeout, business_error, etc.)
        """
        log = logger.bind(
            domain="orchestra",
            action="dispatch_failure",
            issue=issue.number,
            category=category,
        )

        # For api_error and timeout, block the issue
        if category in ("api_error", "timeout", "circuit_breaker"):
            self._update_state_label(issue.number, IssueState.BLOCKED)
            reason = f"Orchestra dispatch 失败（{category}），已暂停调度，等待恢复"
            self._post_failure_comment(issue.number, reason)
            log.warning(f"Issue blocked due to {category}")

            # Record event in flow history
            flow = self.orchestrator.get_flow_for_issue(issue.number)
            if flow and flow.get("branch"):
                self._record_dispatch_event(
                    flow["branch"],
                    success=False,
                    issue_number=issue.number,
                    category=category,
                    reason=reason,
                )
            else:
                log.warning(
                    f"Cannot record dispatch event: no flow branch for #{issue.number}"
                )
        else:
            # Business error - keep in-progress, don't auto-block
            log.warning("Business error, keeping state/in-progress")

            # Record event in flow history
            flow = self.orchestrator.get_flow_for_issue(issue.number)
            if flow and flow.get("branch"):
                self._record_dispatch_event(
                    flow["branch"],
                    success=False,
                    issue_number=issue.number,
                    category=category,
                    reason="Business logic error, manual intervention may be needed",
                )
            else:
                log.warning(
                    f"Cannot record dispatch event: no flow branch for #{issue.number}"
                )

    def _post_failure_comment(self, issue_number: int, reason: str) -> None:
        """Post failure comment on issue.

        Args:
            issue_number: Issue number
            reason: Failure reason
        """
        try:
            from vibe3.clients.github_client import GitHubClient

            GitHubClient().add_comment(
                issue_number,
                f"[Orchestra] {reason}",
                repo=self.config.repo,
            )
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to post failure comment for #{issue_number}: {exc}"
            )

    def _record_dispatch_event(
        self,
        flow_branch: str,
        success: bool,
        issue_number: int,
        pr_number: int | None = None,
        category: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Record dispatch result as flow event for traceability.

        Args:
            flow_branch: Flow branch name
            success: Whether dispatch succeeded
            issue_number: Issue number
            pr_number: PR number (if exists)
            category: Error category (if failed)
            reason: Failure reason (if failed)
        """
        try:
            from vibe3.clients import SQLiteClient

            store = SQLiteClient()
            event_data: dict[str, int | str | None] = {
                "success": success,
                "issue": issue_number,
            }
            if pr_number is not None:
                event_data["pr"] = pr_number
            if category is not None:
                event_data["category"] = category
            if reason is not None:
                event_data["reason"] = reason

            store.add_event(
                branch=flow_branch,
                event_type="dispatch_result",
                actor="orchestra:dispatcher",
                detail="success" if success else f"failed:{category}",
                refs=event_data,
            )
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to record dispatch event for #{issue_number}: {exc}"
            )
