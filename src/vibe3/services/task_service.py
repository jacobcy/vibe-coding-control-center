"""Task service implementation."""

from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.flow import FlowState, IssueLink


class TaskService:
    """Service for managing task state."""

    def __init__(self, store: SQLiteClient | None = None) -> None:
        """Initialize task service.

        Args:
            store: SQLiteClient instance for persistence
        """
        self.store = store or SQLiteClient()

    def link_issue(
        self,
        branch: str,
        issue_number: int,
        role: Literal["task", "repo"] = "repo",
        actor: str = "unknown",
    ) -> IssueLink:
        """Link an issue to a flow.

        Args:
            branch: Git branch name
            issue_number: GitHub issue number
            role: Issue role (task for primary, repo for related issue)
            actor: Actor linking the issue

        Returns:
            Created issue link
        """
        logger.bind(
            domain="task",
            action="link_issue",
            branch=branch,
            issue_number=issue_number,
            role=role,
            actor=actor,
        ).info("Linking issue to flow")

        # Add issue link
        self.store.add_issue_link(branch, issue_number, role)

        # Update flow state if this is a task issue
        if role == "task":
            self.store.update_flow_state(
                branch,
                task_issue_number=issue_number,
                latest_actor=actor,
            )

        # Add event
        self.store.add_event(
            branch,
            "issue_linked",
            actor,
            f"Issue #{issue_number} linked as {role}",
        )

        return IssueLink(
            branch=branch,
            issue_number=issue_number,
            issue_role=role,
        )

    def update_flow_status(
        self,
        branch: str,
        status: Literal["active", "blocked", "done", "stale"],
        actor: str = "unknown",
    ) -> FlowState:
        """Update local flow scene status in flow_state.

        Args:
            branch: Git branch name
            status: New local flow scene status
            actor: Actor updating the status

        Returns:
            Updated flow state
        """
        logger.bind(
            domain="task",
            action="update_flow_status",
            branch=branch,
            status=status,
            actor=actor,
        ).info("Updating local flow scene status")

        # Verify flow exists before updating
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

        # Update flow state
        self.store.update_flow_state(
            branch,
            flow_status=status,
            latest_actor=actor,
        )

        # Add event
        self.store.add_event(
            branch,
            "status_updated",
            actor,
            f"Status changed to {status}",
        )

        # Get updated flow
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

        return FlowState(**flow_data)

    def update_task_status(
        self,
        branch: str,
        status: Literal["active", "blocked", "done", "stale"],
        actor: str = "unknown",
    ) -> FlowState:
        """Compatibility wrapper for updating local flow scene status.

        This remains for older callers, but it only updates the local
        flow scene state stored in flow_state. It is not a GitHub Project
        task truth write path.
        """
        return self.update_flow_status(branch=branch, status=status, actor=actor)

    def get_task(self, branch: str) -> FlowState | None:
        """Get task (flow) details.

        Args:
            branch: Git branch name

        Returns:
            Flow state or None if not found
        """
        logger.bind(
            domain="task",
            action="get",
            branch=branch,
        ).debug("Getting task")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return None

        return FlowState(**flow_data)

    def set_next_step(
        self,
        branch: str,
        next_step: str,
        actor: str = "unknown",
    ) -> FlowState:
        """Set next step for a task.

        Args:
            branch: Git branch name
            next_step: Next step description
            actor: Actor setting the next step

        Returns:
            Updated flow state
        """
        logger.bind(
            domain="task",
            action="set_next_step",
            branch=branch,
            next_step=next_step,
            actor=actor,
        ).info("Setting next step")

        # Update flow state
        self.store.update_flow_state(
            branch,
            next_step=next_step,
            latest_actor=actor,
        )

        # Add event
        self.store.add_event(
            branch,
            "next_step_set",
            actor,
            f"Next step: {next_step}",
        )

        # Get updated flow
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

        return FlowState(**flow_data)
