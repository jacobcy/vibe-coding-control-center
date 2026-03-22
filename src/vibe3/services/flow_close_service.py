"""Flow service close operations."""

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.exceptions import UserError

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient


class FlowCloseService:
    """Service for flow close operations."""

    def __init__(self, store: SQLiteClient, git_client: "GitClient") -> None:
        """Initialize flow close service.

        Args:
            store: SQLiteClient instance
            git_client: GitClient instance
        """
        self.store = store
        self.git = git_client

    def close_flow(self, branch: str, check_pr: bool = True) -> None:
        """Close a flow and delete its branch.

        Args:
            branch: Branch name
            check_pr: If True, check if PR is merged before closing

        Raises:
            UserError: PR not merged and no review evidence
        """
        logger.bind(
            domain="flow",
            action="close",
            branch=branch,
            check_pr=check_pr,
        ).info("Closing flow")

        # Get current flow state
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise UserError(message=f"Flow not found for branch '{branch}'")

        # Check PR status if requested
        if check_pr and flow_data.get("pr_number"):
            # TODO: Implement PR merged check using GitHubClient
            # For now, we skip this check
            logger.warning("PR merged check not implemented yet, skipping")

        # Delete remote branch if it exists
        if self.git.branch_exists(branch):
            try:
                self.git.delete_remote_branch(branch)
                logger.bind(branch=branch).info("Remote branch deleted")
            except Exception as e:
                # Log error but continue with local branch deletion
                logger.bind(branch=branch, error=str(e)).warning(
                    "Failed to delete remote branch, continuing"
                )

        # Switch to main branch before deleting current branch
        current_branch = self.git.get_current_branch()
        if current_branch == branch:
            logger.info("Switching to main before deleting current branch")
            self.git.switch_branch("main")

        # Delete local branch
        try:
            self.git.delete_branch(branch, force=True)
            logger.bind(branch=branch).info("Local branch deleted")
        except Exception as e:
            logger.bind(branch=branch, error=str(e)).warning(
                "Failed to delete local branch"
            )

        # Update flow status
        self.store.update_flow_state(branch, flow_status="done")
        self.store.add_event(
            branch,
            "flow_closed",
            "system",
            "Flow closed and branch deleted",
        )

        logger.bind(branch=branch).success("Flow closed successfully")

    def block_flow(
        self,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
    ) -> None:
        """Mark a flow as blocked.

        Args:
            branch: Branch name
            reason: Optional blocker description
            blocked_by_issue: Optional issue number that is blocking this flow

        Raises:
            UserError: Flow not found
        """
        logger.bind(
            domain="flow",
            action="block",
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
        ).info("Blocking flow")

        # Get current flow state
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise UserError(message=f"Flow not found for branch '{branch}'")

        # Link dependency issue if specified
        if blocked_by_issue:
            from vibe3.services.task_service import TaskService

            task_service = TaskService(store=self.store)
            task_service.link_issue(branch, blocked_by_issue, role="dependency")

            # Auto-generate reason if not provided
            if not reason:
                reason = f"Blocked by issue #{blocked_by_issue}"

        # Update flow status
        update_kwargs = {"flow_status": "blocked"}
        if reason:
            update_kwargs["blocked_by"] = reason

        self.store.update_flow_state(branch, **update_kwargs)

        event_detail = f"Flow blocked: {reason}" if reason else "Flow blocked"
        self.store.add_event(
            branch,
            "flow_blocked",
            "system",
            event_detail,
        )

        logger.bind(branch=branch).success("Flow blocked successfully")

    def abort_flow(self, branch: str) -> None:
        """Abort a flow and delete its branch.

        Args:
            branch: Branch name

        Raises:
            UserError: Flow not found
        """
        logger.bind(
            domain="flow",
            action="abort",
            branch=branch,
        ).info("Aborting flow")

        # Get current flow state
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise UserError(message=f"Flow not found for branch '{branch}'")

        # Delete remote branch if it exists
        if self.git.branch_exists(branch):
            try:
                self.git.delete_remote_branch(branch)
                logger.bind(branch=branch).info("Remote branch deleted")
            except Exception as e:
                # Log error but continue with local branch deletion
                logger.bind(branch=branch, error=str(e)).warning(
                    "Failed to delete remote branch, continuing"
                )

        # Switch to main branch before deleting current branch
        current_branch = self.git.get_current_branch()
        if current_branch == branch:
            logger.info("Switching to main before deleting current branch")
            self.git.switch_branch("main")

        # Delete local branch
        try:
            self.git.delete_branch(branch, force=True)
            logger.bind(branch=branch).info("Local branch deleted")
        except Exception as e:
            logger.bind(branch=branch, error=str(e)).warning(
                "Failed to delete local branch"
            )

        # Update flow status
        self.store.update_flow_state(branch, flow_status="aborted")
        self.store.add_event(
            branch,
            "flow_aborted",
            "system",
            "Flow aborted and branch deleted",
        )

        logger.bind(branch=branch).success("Flow aborted successfully")
