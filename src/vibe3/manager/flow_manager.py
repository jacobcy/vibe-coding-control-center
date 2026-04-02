"""Flow management utilities for orchestra manager."""

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.config import OrchestraConfig
from vibe3.services.flow_service import FlowService
from vibe3.services.task_service import TaskService


class FlowManager:
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

    def get_active_flow_count(self) -> int:
        """Get count of active flows across the whole system."""
        return self.store.get_active_flow_count()

    def create_flow_for_issue(self, issue: IssueInfo) -> dict:
        """Create (or reuse) a flow for an issue.

        Uses FlowService.create_flow() so lifecycle events are recorded
        and the flow is visible via `vibe3 flow show`.

        Args:
            issue: Issue to create flow for

        Returns:
            Flow state dict

        Raises:
            RuntimeError: If flow creation fails or capacity is reached
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

        # Capacity Check: Before creating a NEW flow, verify global capacity
        active_count = self.get_active_flow_count()
        if active_count >= self.config.max_concurrent_flows:
            limit = self.config.max_concurrent_flows
            raise RuntimeError(
                f"Global capacity reached ({active_count}/{limit}). "
                "Deferred flow creation."
            )

        slug = f"issue-{issue.number}"
        branch = f"task/{slug}"

        # Ensure branch exists (create_branch_ref: no checkout, no worktree mutation)
        if not self.git.branch_exists(branch):
            try:
                self.git.create_branch_ref(branch, start_ref="origin/main")
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to create branch '{branch}': {exc}"
                ) from exc

        # Register flow via FlowService (lifecycle events, proper recording)
        # Use orchestra tag only if it's a managed issue-specific branch
        from vibe3.services.signature_service import SignatureService

        initiator = SignatureService.resolve_initiator(branch)
        try:
            flow_state = self.flow_service.create_flow(
                slug=slug,
                branch=branch,
                actor=None,
                initiated_by=initiator,
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
            self.task_service.link_issue(branch, issue.number, "task", actor=None)
        except Exception as exc:
            log.warning(f"Failed to link issue #{issue.number} to flow: {exc}")

        log.info(f"Created flow '{slug}' on branch '{branch}'")
        return flow_state.model_dump()

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
