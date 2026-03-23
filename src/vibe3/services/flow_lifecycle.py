"""Flow lifecycle operations - close, block, abort."""

from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient


class FlowLifecycleMixin:
    """Mixin providing flow lifecycle operations."""

    store: Any

    def close_flow(
        self: Any,
        branch: str,
        check_pr: bool = True,
    ) -> None:
        """Close flow and delete branch.

        Args:
            branch: Branch name
            check_pr: Whether to check PR merge status

        Raises:
            RuntimeError: If PR not merged and check_pr is True
        """
        git = GitClient()

        logger.bind(
            domain="flow",
            action="close",
            branch=branch,
            check_pr=check_pr,
        ).info("Closing flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

        if git.branch_exists(branch):
            git.delete_branch(branch, force=True)

        try:
            git.delete_remote_branch(branch)
        except Exception:
            logger.bind(
                domain="flow",
                action="close",
                branch=branch,
            ).warning("Failed to delete remote branch, continuing")

        self.store.update_flow_state(branch, flow_status="done")

        self.store.add_event(
            branch,
            "flow_closed",
            "system",
            f"Flow closed, branch '{branch}' deleted",
        )

    def block_flow(
        self: Any,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
    ) -> None:
        """Mark flow as blocked.

        Args:
            branch: Branch name
            reason: Optional blocking reason
            blocked_by_issue: Optional issue number that blocks this flow
        """
        logger.bind(
            domain="flow",
            action="block",
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
        ).info("Blocking flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

        if blocked_by_issue:
            from vibe3.services.task_service import TaskService

            TaskService().link_issue(branch, blocked_by_issue, role="dependency")

        blocked_by = reason or (
            f"Blocked by issue #{blocked_by_issue}" if blocked_by_issue else None
        )

        self.store.update_flow_state(
            branch,
            flow_status="blocked",
            blocked_by=blocked_by,
        )

        self.store.add_event(
            branch,
            "flow_blocked",
            "system",
            f"Flow blocked{': ' + reason if reason else ''}",
        )

    def abort_flow(
        self: Any,
        branch: str,
    ) -> None:
        """Abort flow and delete branch.

        Args:
            branch: Branch name
        """
        git = GitClient()

        logger.bind(
            domain="flow",
            action="abort",
            branch=branch,
        ).info("Aborting flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

        if git.branch_exists(branch):
            git.delete_branch(branch, force=True)

        try:
            git.delete_remote_branch(branch)
        except Exception:
            logger.bind(
                domain="flow",
                action="abort",
                branch=branch,
            ).warning("Failed to delete remote branch, continuing")

        self.store.update_flow_state(branch, flow_status="aborted")

        self.store.add_event(
            branch,
            "flow_aborted",
            "system",
            f"Flow aborted, branch '{branch}' deleted",
        )
