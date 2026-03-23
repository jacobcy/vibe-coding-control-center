"""Flow service implementation."""

import re
from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.models.flow import (
    FlowState,
    FlowStatusResponse,
    IssueLink,
)
from vibe3.services.flow_lifecycle import FlowLifecycleMixin


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


class FlowService(FlowLifecycleMixin):
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

    def create_flow_with_branch(
        self,
        slug: str,
        start_ref: str = "origin/main",
        save_unstash: bool = False,
    ) -> FlowState:
        """Create a new flow and create branch.

        Args:
            slug: Flow name/slug
            start_ref: Starting reference for new branch
            save_unstash: Whether to stash and restore current changes

        Returns:
            Created flow state

        Raises:
            RuntimeError: If branch already exists or worktree is dirty
        """
        git = GitClient()
        branch = f"task/{slug}"

        logger.bind(
            domain="flow",
            action="create_with_branch",
            slug=slug,
            branch=branch,
            start_ref=start_ref,
        ).info("Creating flow with branch")

        # Check if branch already exists
        if git.branch_exists(branch):
            raise RuntimeError(f"Branch '{branch}' already exists")

        # Check if worktree is dirty
        if git.has_uncommitted_changes() and not save_unstash:
            raise RuntimeError(
                "Worktree has uncommitted changes. "
                "Use --save-unstash to stash them automatically."
            )

        # Stash changes if requested
        stash_ref = None
        if save_unstash and git.has_uncommitted_changes():
            stash_ref = git.stash_push(message=f"vibe flow new {slug}")

        # Create and switch to new branch
        git.create_branch(branch, start_ref)

        # Create flow state
        flow = self.create_flow(slug, branch)

        # Restore stash if we stashed
        if stash_ref:
            git.stash_apply(stash_ref)

        return flow

    def switch_flow(
        self,
        target: str,
    ) -> FlowState:
        """Switch to existing flow.

        Args:
            target: Flow slug or branch name to switch to

        Returns:
            Flow state of the target flow

        Raises:
            RuntimeError: If flow not found
        """
        git = GitClient()

        logger.bind(
            domain="flow",
            action="switch",
            target=target,
        ).info("Switching to flow")

        # Find the flow - try by slug first, then by branch
        flows = self.list_flows()
        target_flow = None
        for flow in flows:
            if flow.flow_slug == target or flow.branch == target:
                target_flow = flow
                break

        if not target_flow:
            raise RuntimeError(f"Flow '{target}' not found")

        # Check if branch exists
        if not git.branch_exists(target_flow.branch):
            raise RuntimeError(f"Branch '{target_flow.branch}' does not exist")

        # Stash current changes
        stash_ref = None
        if git.has_uncommitted_changes():
            stash_ref = git.stash_push(message=f"vibe flow switch {target}")

        # Switch to target branch
        git.switch_branch(target_flow.branch)

        # Restore stash if we stashed
        if stash_ref:
            git.stash_apply(stash_ref)

        return target_flow

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
