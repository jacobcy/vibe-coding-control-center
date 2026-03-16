"""Task service implementation."""
import sys
from pathlib import Path
from typing import Literal

from loguru import logger

# Add lib to path for Vibe3Store
lib_path = Path(__file__).parent.parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))
from store import Vibe3Store  # noqa: E402

from vibe3.models.flow import FlowState, IssueLink  # noqa: E402


class TaskService:
    """Service for managing task state."""

    def __init__(self, store: Vibe3Store | None = None) -> None:
        """Initialize task service.

        Args:
            store: Vibe3Store instance for persistence
        """
        self.store = store or Vibe3Store()

    def link_issue(
        self,
        branch: str,
        issue_number: int,
        role: Literal["task", "related"] = "related",
        actor: str = "unknown",
    ) -> IssueLink:
        """Link an issue to a flow.

        Args:
            branch: Git branch name
            issue_number: GitHub issue number
            role: Issue role (task for primary, related for secondary)
            actor: Actor linking the issue

        Returns:
            Created issue link
        """
        logger.info(
            "Linking issue to flow",
            branch=branch,
            issue_number=issue_number,
            role=role,
            actor=actor,
        )

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

    def update_task_status(
        self,
        branch: str,
        status: Literal["active", "idle", "missing", "stale"],
        actor: str = "unknown",
    ) -> FlowState:
        """Update task status (flow_status in flow_state).

        Args:
            branch: Git branch name
            status: New status
            actor: Actor updating the status

        Returns:
            Updated flow state
        """
        logger.info(
            "Updating task status",
            branch=branch,
            status=status,
            actor=actor,
        )

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

    def get_task(self, branch: str) -> FlowState | None:
        """Get task (flow) details.

        Args:
            branch: Git branch name

        Returns:
            Flow state or None if not found
        """
        logger.debug("Getting task", branch=branch)

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
        logger.info(
            "Setting next step",
            branch=branch,
            next_step=next_step,
            actor=actor,
        )

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
