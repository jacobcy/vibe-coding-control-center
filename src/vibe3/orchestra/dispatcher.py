"""Command dispatcher with flow orchestration."""

import subprocess
from pathlib import Path

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher_worktree import WorktreeResolverMixin
from vibe3.orchestra.flow_orchestrator import FlowOrchestrator
from vibe3.orchestra.models import IssueInfo

_DISPATCH_TIMEOUT = 3600


class Dispatcher(WorktreeResolverMixin):
    """Dispatches commands based on triggers with flow orchestration."""

    def __init__(
        self,
        config: OrchestraConfig,
        dry_run: bool = False,
        repo_path: Path | None = None,
        orchestrator: FlowOrchestrator | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.repo_path = repo_path or Path.cwd()
        self.orchestrator = orchestrator or FlowOrchestrator(config)

    @staticmethod
    def _run_command(cmd: list[str], cwd: Path, label: str) -> bool:
        """Execute a subprocess command with timeout and structured logging.

        Returns True on success, False on failure/timeout.
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=_DISPATCH_TIMEOUT,
            )
            if result.returncode != 0:
                logger.bind(domain="orchestra").error(
                    f"{label} failed: {result.stderr}"
                )
                return False
            logger.bind(domain="orchestra").info(f"{label} completed successfully")
            return True
        except subprocess.TimeoutExpired:
            logger.bind(domain="orchestra").error(f"{label} timed out")
            return False
        except Exception as e:
            logger.bind(domain="orchestra").error(f"{label} error: {e}")
            return False

    def dispatch_manager(self, issue: IssueInfo) -> bool:
        """Dispatch manager execution for an assignee-triggered issue."""
        log = logger.bind(
            domain="orchestra",
            action="manager_dispatch",
            issue=issue.number,
        )

        cmd = self.build_manager_command(issue)
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

        return self._run_command(cmd, manager_cwd, "Manager execution")

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
        """Build executable manager command for an issue."""
        cmd = ["uv", "run", "python", "-m", "vibe3", "run"]
        if self.config.assignee_dispatch.use_worktree:
            cmd.append("--worktree")
        cmd.append(f"Implement issue #{issue.number}: {issue.title}")
        return cmd

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
