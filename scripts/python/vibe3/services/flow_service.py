"""Flow service implementation."""
import sys
from pathlib import Path

# Add lib to path for Vibe3Store
lib_path = Path(__file__).parent.parent.parent / "lib"
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

from datetime import datetime
from typing import Literal

from loguru import logger

from vibe3.models.flow import (
    CreateFlowRequest,
    FlowState,
    FlowStatusResponse,
    IssueLink,
)
from store import Vibe3Store


class FlowService:
    """Service for managing flow state."""

    def __init__(self, store: Vibe3Store | None = None) -> None:
        """Initialize flow service.

        Args:
            store: Vibe3Store instance for persistence
        """
        self.store = store or Vibe3Store()

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
        logger.info(
            "Creating flow",
            slug=slug,
            branch=branch,
            task_id=task_id,
            actor=actor,
        )

        # Update flow state
        self.store.update_flow_state(
            branch,
            flow_slug=slug,
            latest_actor=actor,
        )

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
        logger.info(
            "Binding task to flow",
            branch=branch,
            task_id=task_id,
            actor=actor,
        )

        # Update flow state
        self.store.update_flow_state(
            branch,
            latest_actor=actor,
        )

        # Add binding event
        self.store.add_event(
            branch,
            "task_bound",
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
        logger.debug("Getting flow status", branch=branch)

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
        status: Literal["active", "idle", "missing", "stale"] | None = None,
    ) -> list[FlowState]:
        """List flows.

        Args:
            status: Optional status filter

        Returns:
            List of flow states
        """
        logger.debug("Listing flows", status=status)

        flows_data = self.store.get_active_flows()

        if status:
            flows_data = [f for f in flows_data if f.get("flow_status") == status]

        return [FlowState(**flow) for flow in flows_data]