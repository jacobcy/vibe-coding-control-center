"""Flow service implementation."""

import re
from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.flow import (
    FlowState,
    FlowStatusResponse,
    IssueLink,
)


def parse_task_id(task_id: str) -> int:
    """Extract numeric part from task ID.

    Args:
        task_id: Task ID string (e.g., "TASK-123", "123", "task-456")

    Returns:
        Numeric part of task ID

    Raises:
        ValueError: If no numeric part found
    """
    # Extract digits from the task ID
    match = re.search(r"\d+", task_id)
    if not match:
        raise ValueError(f"Invalid task ID format: {task_id}")
    return int(match.group())


class FlowService:
    """Service for managing flow state."""

    def __init__(self, store: SQLiteClient | None = None) -> None:
        """Initialize flow service.

        Args:
            store: SQLiteClient instance for persistence
        """
        self.store = store or SQLiteClient()

    def create_flow(
        self,
        slug: str,
        branch: str,
        task_id: str | None = None,
        actor: str = "unknown",
    ) -> FlowState:
        """Create a new flow.

        Args:
            slug: Flow name/slug
            branch: Git branch name
            task_id: Optional task ID to bind
            actor: Actor creating the flow

        Returns:
            Created flow state
        """
        logger.bind(
            domain="flow",
            action="create",
            slug=slug,
            branch=branch,
            task_id=task_id,
            actor=actor,
        ).info("Creating flow")

        # Parse task_id if provided
        task_issue_number = None
        if task_id:
            task_issue_number = parse_task_id(task_id)

        # Update flow state
        self.store.update_flow_state(
            branch,
            flow_slug=slug,
            task_issue_number=task_issue_number,
            latest_actor=actor,
        )

        # Add issue link if task_id provided
        if task_id and task_issue_number is not None:
            self.store.add_issue_link(branch, task_issue_number, "task")

        # Add creation event
        self.store.add_event(
            branch,
            "flow_created",
            actor,
            f"Flow '{slug}' created",
        )

        # Get the created flow
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Failed to create flow for branch {branch}")

        return FlowState(**flow_data)

    def bind_flow(
        self,
        branch: str,
        task_id: str,
        actor: str = "unknown",
    ) -> FlowState:
        """Bind a task to a flow.

        Args:
            branch: Git branch name
            task_id: Task ID to bind
            actor: Actor binding the task

        Returns:
            Updated flow state
        """
        logger.bind(
            domain="flow",
            action="bind_task",
            branch=branch,
            task_id=task_id,
            actor=actor,
        ).info("Binding task to flow")

        # Parse task_id
        task_issue_number = parse_task_id(task_id)

        # Update flow state with task_issue_number
        self.store.update_flow_state(
            branch,
            task_issue_number=task_issue_number,
            latest_actor=actor,
        )

        # Add issue link
        self.store.add_issue_link(branch, task_issue_number, "task")

        # Add binding event
        self.store.add_event(
            branch,
            "flow_bind",
            actor,
            f"Task '{task_id}' bound",
        )

        # Get updated flow
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

        return FlowState(**flow_data)

    def get_flow_status(self, branch: str) -> FlowStatusResponse | None:
        """Get flow status.

        Args:
            branch: Git branch name

        Returns:
            Flow status response or None if not found
        """
        logger.bind(
            domain="flow",
            action="get_status",
            branch=branch,
        ).debug("Getting flow status")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return None

        # Get issue links
        issue_links = self.store.get_issue_links(branch)
        issues = [IssueLink(**link) for link in issue_links]

        return FlowStatusResponse(
            branch=flow_data["branch"],
            flow_slug=flow_data["flow_slug"],
            flow_status=flow_data["flow_status"],
            task_issue_number=flow_data.get("task_issue_number"),
            pr_number=flow_data.get("pr_number"),
            spec_ref=flow_data.get("spec_ref"),
            next_step=flow_data.get("next_step"),
            issues=issues,
        )

    def list_flows(
        self,
        status: Literal["active", "blocked", "done", "stale"] | None = None,
    ) -> list[FlowState]:
        """List flows.

        Args:
            status: Optional status filter

        Returns:
            List of flow states
        """
        logger.bind(
            domain="flow",
            action="list",
            status=status,
        ).debug("Listing flows")

        # Get all flows, not just active ones
        flows_data = self.store.get_all_flows()

        # Apply status filter if provided
        if status:
            flows_data = [f for f in flows_data if f.get("flow_status") == status]

        return [FlowState(**flow) for flow in flows_data]
