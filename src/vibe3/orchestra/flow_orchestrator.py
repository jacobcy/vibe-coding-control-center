"""Flow orchestration utilities for orchestra dispatcher."""

import subprocess

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.models import IssueInfo
from vibe3.services.flow_service import FlowService
from vibe3.services.task_service import TaskService


class FlowOrchestrator:
    """Manages issue-to-flow mapping and command execution.

    Uses FlowService and TaskService for all state mutations so that
    orchestra-created flows participate in the standard flow lifecycle
    (events recorded, vibe3 flow show works, etc.).

    Git branch creation is handled directly via GitClient because
    FlowService.create_flow_with_branch() has an uncommitted-changes
    guard that is inappropriate for a background server context.
    """

    def __init__(self, config: OrchestraConfig) -> None:
        self.config = config
        self.store = SQLiteClient()
        self.git = GitClient()
        self.flow_service = FlowService(store=self.store, git_client=self.git)
        self.task_service = TaskService(store=self.store)
        self.github = GitHubClient()

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Get flow linked to an issue."""
        flows = self.store.get_flows_by_issue(issue_number, role="task")
        return flows[0] if flows else None

    def create_flow_for_issue(self, issue: IssueInfo) -> dict:
        """Create (or reuse) a flow for an issue.

        Uses FlowService.create_flow() so lifecycle events are recorded
        and the flow is visible via `vibe3 flow show`.

        Args:
            issue: Issue to create flow for

        Returns:
            Flow state dict

        Raises:
            RuntimeError: If flow creation fails
        """
        log = logger.bind(
            domain="orchestra",
            action="create_flow",
            issue=issue.number,
        )

        existing = self.get_flow_for_issue(issue.number)
        if existing:
            log.info(f"Flow already exists for issue #{issue.number}")
            return existing

        slug = f"issue-{issue.number}"
        branch = f"task/{slug}"

        # Ensure branch exists (GitClient, no uncommitted-changes guard)
        if not self.git.branch_exists(branch):
            try:
                self._create_branch_ref(branch, start_ref="origin/main")
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to create branch '{branch}': {exc}"
                ) from exc

        # Register flow via FlowService (lifecycle events, proper recording)
        try:
            flow_state = self.flow_service.create_flow(
                slug=slug,
                branch=branch,
                actor="orchestra",
            )
        except Exception as exc:
            # Guard against race condition: re-check if flow was created concurrently
            existing = self.store.get_flow_state(branch)
            if existing:
                log.warning(
                    f"Flow created concurrently for #{issue.number}, using existing"
                )
                return existing
            raise RuntimeError(
                f"Failed to create flow for issue #{issue.number}: {exc}"
            ) from exc

        # Bind issue via TaskService
        try:
            self.task_service.link_issue(
                branch, issue.number, "task", actor="orchestra"
            )
        except Exception as exc:
            log.warning(f"Failed to link issue #{issue.number} to flow: {exc}")

        log.info(f"Created flow '{slug}' on branch '{branch}'")
        return flow_state.model_dump()

    def _create_branch_ref(self, branch: str, start_ref: str) -> None:
        """Create branch ref from start_ref without checkout.

        Orchestra must avoid mutating the serve process worktree state.
        """
        result = subprocess.run(
            ["git", "branch", branch, start_ref],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "already exists" in stderr.lower():
                return
            raise RuntimeError(stderr or "unknown git branch error")

        logger.bind(
            domain="orchestra",
            action="create_branch_ref",
            branch=branch,
            start_ref=start_ref,
        ).info("Created branch ref for orchestra flow")

    def get_pr_for_issue(self, issue_number: int) -> int | None:
        """Get PR number for an issue.

        Priority:
        1. PR stored in flow state
        2. GitHub API lookup via GitHubClient
        """
        flow = self.get_flow_for_issue(issue_number)
        if flow and flow.get("pr_number"):
            return int(flow["pr_number"])

        return self.github.get_pr_for_issue(issue_number, repo=self.config.repo)

    def switch_to_flow_branch(self, issue_number: int) -> str | None:
        """Switch to the branch for a flow.

        Returns:
            Branch name if successful, None otherwise
        """
        flow = self.get_flow_for_issue(issue_number)
        if not flow:
            logger.bind(domain="orchestra").warning(
                f"No flow found for issue #{issue_number}"
            )
            return None

        branch: str | None = flow.get("branch")
        if not branch:
            logger.bind(domain="orchestra").warning(
                f"Flow for issue #{issue_number} has no branch"
            )
            return None

        if not self.git.branch_exists(branch):
            logger.bind(domain="orchestra").error(
                f"Branch '{branch}' does not exist for issue #{issue_number}"
            )
            return None

        current = self.git.get_current_branch()
        if current == branch:
            return str(branch)

        try:
            self.git.switch_branch(branch)
            logger.bind(domain="orchestra").info(
                f"Switched to branch '{branch}' for issue #{issue_number}"
            )
            return str(branch)
        except Exception as exc:
            logger.bind(domain="orchestra").error(
                f"Failed to switch to branch '{branch}': {exc}"
            )
            return None
