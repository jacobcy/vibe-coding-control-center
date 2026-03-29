"""Command dispatcher with flow orchestration."""

import subprocess
from pathlib import Path

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.flow_orchestrator import FlowOrchestrator
from vibe3.orchestra.models import IssueInfo, Trigger


class Dispatcher:
    """Dispatches commands based on triggers with flow orchestration."""

    def __init__(
        self,
        config: OrchestraConfig,
        dry_run: bool = False,
        repo_path: Path | None = None,
    ):
        self.config = config
        self.dry_run = dry_run
        self.repo_path = repo_path or Path.cwd()
        self.orchestrator = FlowOrchestrator(config)

    def dispatch(self, trigger: Trigger) -> bool:
        """Execute command for trigger with proper flow orchestration.

        Args:
            trigger: Trigger to dispatch

        Returns:
            True if successful, False otherwise
        """
        log = logger.bind(
            domain="orchestra",
            action="dispatch",
            issue=trigger.issue.number,
            command=trigger.command,
        )

        cmd = self._build_command(trigger)
        if cmd is None:
            log.error("Failed to build command")
            return False

        log.info(f"Dispatching: {' '.join(cmd)}")

        if self.dry_run:
            log.info("Dry run, skipping execution")
            return True

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=3600,
            )

            if result.returncode != 0:
                log.error(f"Command failed: {result.stderr}")
                return False

            log.info("Command completed successfully")
            return True

        except subprocess.TimeoutExpired:
            log.error("Command timed out")
            return False
        except Exception as e:
            log.error(f"Command error: {e}")
            return False

    def _build_command(self, trigger: Trigger) -> list[str] | None:
        """Build command list from trigger with flow orchestration.

        Returns:
            Command list or None if build failed
        """
        issue = trigger.issue
        to_state = trigger.to_state

        cmd = ["uv", "run", "python", "-m", "vibe3"]
        cmd.append(trigger.command)
        cmd.extend(trigger.args)

        if trigger.command == "plan":
            return self._build_plan_command(cmd, issue, to_state)
        elif trigger.command == "run":
            return self._build_run_command(cmd, issue, to_state)
        elif trigger.command == "review":
            return self._build_review_command(cmd, issue, to_state)

        return None

    def _build_plan_command(
        self, cmd: list[str], issue: IssueInfo, to_state: IssueState
    ) -> list[str] | None:
        """Build plan command.

        For ready -> claimed:
        - Create flow with real git branch
        - Switch to the new branch
        - Run plan task <issue_number>
        """
        if to_state != IssueState.CLAIMED:
            return None

        try:
            flow = self.orchestrator.create_flow_for_issue(issue)
            log = logger.bind(domain="orchestra", issue=issue.number)
            log.info(f"Created flow with branch: {flow.get('branch')}")
        except Exception as e:
            logger.bind(domain="orchestra").error(
                f"Failed to create flow for issue #{issue.number}: {e}"
            )
            return None

        cmd.append(str(issue.number))
        return cmd

    def _build_run_command(
        self, cmd: list[str], issue: IssueInfo, to_state: IssueState
    ) -> list[str] | None:
        """Build run command.

        For claimed -> in_progress:
        - Switch to flow branch (required)
        - Run execute
        """
        if to_state != IssueState.IN_PROGRESS:
            return None

        branch = self.orchestrator.switch_to_flow_branch(issue.number)
        if not branch:
            logger.bind(domain="orchestra").error(
                f"Cannot run: no valid branch for issue #{issue.number}"
            )
            return None

        return cmd

    def dispatch_manager(self, issue: IssueInfo) -> bool:
        """Dispatch manager execution for an assignee-triggered issue.

        Full lifecycle:
        1. Create (or reuse) flow for the issue
        2. Update state label to in-progress (display only)
        3. Run vibe3 task execution for the issue

        Args:
            issue: Issue to execute

        Returns:
            True if execution completed successfully
        """
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
        if not self.dry_run:
            self._update_state_label(issue.number, IssueState.IN_PROGRESS)

        # Step 3: run manager execution
        cmd = self._normalize_manager_command(cmd, manager_cwd)
        log.info(f"Dispatching manager: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=manager_cwd,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if result.returncode != 0:
                log.error(f"Manager execution failed: {result.stderr}")
                return False
            log.info("Manager execution completed successfully")
            return True
        except subprocess.TimeoutExpired:
            log.error("Manager execution timed out")
            return False
        except Exception as e:
            log.error(f"Manager execution error: {e}")
            return False

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

        try:
            result = subprocess.run(
                cmd,
                cwd=review_cwd,
                capture_output=True,
                text=True,
                timeout=3600,
            )
            if result.returncode != 0:
                log.error(f"Review execution failed: {result.stderr}")
                return False
            log.info("Review execution completed successfully")
            return True
        except subprocess.TimeoutExpired:
            log.error("Review execution timed out")
            return False
        except Exception as e:
            log.error(f"Review execution error: {e}")
            return False

    def build_manager_command(self, issue: IssueInfo) -> list[str]:
        """Build executable manager command for an issue."""
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "vibe3",
            "run",
        ]
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

    def _resolve_manager_cwd(self, issue_number: int, flow_branch: str) -> Path | None:
        """Resolve stable cwd for manager execution on a flow branch.

        Priority:
        1. Current repo_path when already on flow branch
        2. Existing worktree that has the flow branch checked out
        3. Create a dedicated orchestra worktree for this issue branch
        """
        if self._is_current_branch(flow_branch):
            return self.repo_path

        existing = self._find_worktree_for_branch(flow_branch)
        if existing:
            return existing

        return self._ensure_manager_worktree(issue_number, flow_branch)

    def _normalize_manager_command(self, cmd: list[str], cwd: Path) -> list[str]:
        """Backwards-compatible manager command normalization.

        Some target branches may not yet support `vibe3 run --worktree`.
        In that case, drop the flag and continue execution to avoid hard fail.
        """
        if "--worktree" not in cmd:
            return cmd
        if self._supports_run_worktree_option(cwd):
            return cmd

        logger.bind(domain="orchestra", cwd=str(cwd)).warning(
            "Target worktree does not support `vibe3 run --worktree`; "
            "falling back without the flag"
        )
        return [arg for arg in cmd if arg != "--worktree"]

    def _supports_run_worktree_option(self, cwd: Path) -> bool:
        """Check whether `vibe3 run` in target cwd supports `--worktree`."""
        try:
            result = subprocess.run(
                ["uv", "run", "python", "-m", "vibe3", "run", "--help"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            return False

        if result.returncode != 0:
            return False
        return "--worktree" in result.stdout

    def _is_current_branch(self, branch: str) -> bool:
        """Check whether dispatcher repo_path currently points at the target branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return False
        if result.returncode != 0:
            return False
        return result.stdout.strip() == branch

    def _ensure_manager_worktree(self, issue_number: int, branch: str) -> Path | None:
        """Create dedicated manager worktree for issue flow branch when missing."""
        target = self.repo_path / ".worktrees" / f"issue-{issue_number}"

        if target.exists():
            logger.bind(
                domain="orchestra",
                issue=issue_number,
                branch=branch,
                worktree=str(target),
            ).warning("Manager worktree path already exists; cannot auto-create")
            return None

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                ["git", "worktree", "add", str(target), branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            logger.bind(
                domain="orchestra",
                issue=issue_number,
                branch=branch,
                worktree=str(target),
            ).warning(f"Failed to create manager worktree: {exc}")
            return None

        if result.returncode != 0:
            logger.bind(
                domain="orchestra",
                issue=issue_number,
                branch=branch,
                worktree=str(target),
            ).warning(f"Failed to create manager worktree: {result.stderr.strip()}")
            return None

        logger.bind(
            domain="orchestra",
            issue=issue_number,
            branch=branch,
            worktree=str(target),
        ).info("Created manager worktree for flow branch")
        return target

    def _resolve_review_cwd(self, pr_number: int) -> Path:
        """Resolve best worktree cwd for PR review execution.

        Priority:
        1. Worktree that currently has PR head branch checked out
        2. Dispatcher default repo_path
        """
        try:
            from vibe3.clients.github_client import GitHubClient

            pr = GitHubClient().get_pr(pr_number)
            if not pr or not pr.head_branch:
                return self.repo_path

            worktree = self._find_worktree_for_branch(pr.head_branch)
            if worktree:
                logger.bind(
                    domain="orchestra",
                    pr_number=pr_number,
                    branch=pr.head_branch,
                    worktree=str(worktree),
                ).info("Resolved PR review to matching worktree")
                return worktree
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to resolve PR worktree for #{pr_number}: {exc}"
            )

        return self.repo_path

    def _find_worktree_for_branch(self, branch: str) -> Path | None:
        """Find worktree path whose checked-out branch matches `branch`."""
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return None

        if result.returncode != 0:
            return None

        current_worktree: str | None = None
        current_branch: str | None = None

        def matched() -> Path | None:
            if current_worktree and current_branch == f"refs/heads/{branch}":
                return Path(current_worktree)
            return None

        for raw in result.stdout.splitlines():
            line = raw.strip()
            if not line:
                found = matched()
                if found:
                    return found
                current_worktree = None
                current_branch = None
                continue
            if line.startswith("worktree "):
                current_worktree = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                current_branch = line.split(" ", 1)[1]

        return matched()

    def _update_state_label(self, issue_number: int, state: IssueState) -> None:
        """Update issue state label (display only, does not drive logic).

        Adds the state label and removes any other state/* labels.
        """
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

    def _build_review_command(
        self, cmd: list[str], issue: IssueInfo, to_state: IssueState
    ) -> list[str] | None:
        """Build review command.

        For in_progress -> review:
        - Switch to flow branch
        - Get PR number for issue
        - Run review pr <pr_number>
        """
        if to_state != IssueState.REVIEW:
            return None

        branch = self.orchestrator.switch_to_flow_branch(issue.number)
        if not branch:
            logger.bind(domain="orchestra").warning(
                f"Could not switch to flow branch for issue #{issue.number}"
            )

        pr_number = self.orchestrator.get_pr_for_issue(issue.number)
        if not pr_number:
            logger.bind(domain="orchestra").error(
                f"No PR found for issue #{issue.number}, cannot review"
            )
            return None

        cmd.append(str(pr_number))
        return cmd
