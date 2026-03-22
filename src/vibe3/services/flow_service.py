"""Flow service implementation."""

import re
from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.flow import (
    FlowState,
    FlowStatusResponse,
    IssueLink,
)
from vibe3.services.flow_close_service import FlowCloseService
from vibe3.services.flow_lifecycle_service import FlowLifecycleService

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient


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
    """Service for managing flow state.

    This service acts as a facade that coordinates between:
    - FlowLifecycleService: flow creation and switching
    - FlowCloseService: flow closure, blocking, and abortion
    """

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: "GitClient | None" = None,
    ) -> None:
        """Initialize flow service.

        Args:
            store: SQLiteClient instance for persistence
            git_client: GitClient instance for git operations
        """
        self.store = store or SQLiteClient()
        self._git_client = git_client

        # Initialize sub-services
        self._lifecycle_service: FlowLifecycleService | None = None
        self._close_service: FlowCloseService | None = None

    @property
    def git(self) -> "GitClient":
        """Get GitClient instance (lazy initialization)."""
        if self._git_client is None:
            from vibe3.clients.git_client import GitClient

            self._git_client = GitClient()
        return self._git_client

    @property
    def lifecycle_service(self) -> FlowLifecycleService:
        """Get FlowLifecycleService instance (lazy initialization)."""
        if self._lifecycle_service is None:
            self._lifecycle_service = FlowLifecycleService(
                store=self.store, git_client=self.git
            )
        return self._lifecycle_service

    @property
    def close_service(self) -> FlowCloseService:
        """Get FlowCloseService instance (lazy initialization)."""
        if self._close_service is None:
            self._close_service = FlowCloseService(
                store=self.store, git_client=self.git
            )
        return self._close_service

    def create_flow(
        self,
        slug: str,
        branch: str,
    ) -> FlowState:
        """Create a new flow.

        Args:
            slug: Flow name/slug
            branch: Git branch name

        Returns:
            Created flow state
        """
        logger.bind(
            domain="flow",
            action="create",
            slug=slug,
            branch=branch,
        ).info("Creating flow")

        self.store.update_flow_state(
            branch,
            flow_slug=slug,
        )

        self.store.add_event(
            branch,
            "flow_created",
            "system",
            f"Flow '{slug}' created",
        )

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Failed to create flow for branch {branch}")

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
            plan_ref=flow_data.get("plan_ref"),
            report_ref=flow_data.get("report_ref"),
            audit_ref=flow_data.get("audit_ref"),
            planner_actor=flow_data.get("planner_actor"),
            executor_actor=flow_data.get("executor_actor"),
            reviewer_actor=flow_data.get("reviewer_actor"),
            latest_actor=flow_data.get("latest_actor"),
            blocked_by=flow_data.get("blocked_by"),
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

    def create_flow_with_branch(
        self,
        slug: str,
        start_ref: str = "origin/main",
        save_unstash: bool = False,
    ) -> FlowState:
        """Create a new flow with a new branch.

        Delegates to FlowLifecycleService.

        Args:
            slug: Flow name/slug
            start_ref: Starting point for the new branch (default: origin/main)
            save_unstash: If True, stash current changes and restore them
                after branch creation

        Returns:
            Created flow state

        Raises:
            UserError: Branch already exists or dirty worktree without save_unstash
        """
        return self.lifecycle_service.create_flow_with_branch(
            slug=slug, start_ref=start_ref, save_unstash=save_unstash
        )

    def switch_flow(
        self,
        target: str,
    ) -> FlowState:
        """Switch to an existing flow.

        Delegates to FlowLifecycleService.

        Args:
            target: Branch name or flow slug

        Returns:
            Target flow state

        Raises:
            UserError: Target flow/branch not found
        """
        return self.lifecycle_service.switch_flow(target=target)

    def close_flow(
        self,
        branch: str,
        check_pr: bool = True,
    ) -> None:
        """Close a flow and delete its branch.

        Delegates to FlowCloseService.

        Args:
            branch: Branch name
            check_pr: If True, check if PR is merged before closing

        Raises:
            UserError: PR not merged and no review evidence
        """
        self.close_service.close_flow(branch=branch, check_pr=check_pr)

    def block_flow(
        self,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
    ) -> None:
        """Mark a flow as blocked.

        Delegates to FlowCloseService.

        Args:
            branch: Branch name
            reason: Optional blocker description
            blocked_by_issue: Optional issue number that is blocking this flow

        Raises:
            UserError: Flow not found
        """
        self.close_service.block_flow(
            branch=branch, reason=reason, blocked_by_issue=blocked_by_issue
        )

    def abort_flow(
        self,
        branch: str,
    ) -> None:
        """Abort a flow and delete its branch.

        Delegates to FlowCloseService.

        Args:
            branch: Branch name

        Raises:
            UserError: Flow not found
        """
        self.close_service.abort_flow(branch=branch)
