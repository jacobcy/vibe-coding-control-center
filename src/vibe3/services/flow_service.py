"""Flow service implementation."""

from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import (
    FlowEvent,
    FlowState,
    FlowStatusResponse,
    IssueLink,
    MainBranchProtectedError,
)
from vibe3.services.flow_auto_ensure_mixin import FlowAutoEnsureMixin
from vibe3.services.flow_lifecycle import FlowLifecycleMixin


class FlowService(FlowAutoEnsureMixin, FlowLifecycleMixin):
    """Service for managing flow state."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        config: VibeConfig | None = None,
    ) -> None:
        """Initialize flow service.

        Args:
            store: SQLiteClient instance for persistence
            git_client: GitClient instance for git operations
            config: VibeConfig instance for configuration
        """
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.config = config or VibeConfig.get_defaults()

    def get_current_branch(self) -> str:
        """Get current git branch.

        Returns:
            Current branch name
        """
        return self.git_client.get_current_branch()

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

        Raises:
            MainBranchProtectedError: If branch is main/master
        """
        # Guard against main branch
        if self._is_main_branch(branch):
            raise MainBranchProtectedError(
                f"Cannot create flow on protected branch '{branch}'. "
                "Switch to a feature branch first."
            )

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
        branch = f"task/{slug}"

        logger.bind(
            domain="flow",
            action="create_with_branch",
            slug=slug,
            branch=branch,
            start_ref=start_ref,
        ).info("Creating flow with branch")

        # Check if branch already exists
        if self.git_client.branch_exists(branch):
            raise RuntimeError(f"Branch '{branch}' already exists")

        # Check if worktree is dirty
        if self.git_client.has_uncommitted_changes() and not save_unstash:
            raise RuntimeError(
                "Worktree has uncommitted changes. "
                "Use --save-unstash to stash them automatically."
            )

        # Stash changes if requested
        stash_ref = None
        if save_unstash and self.git_client.has_uncommitted_changes():
            stash_ref = self.git_client.stash_push(message=f"vibe flow new {slug}")

        # Create and switch to new branch
        self.git_client.create_branch(branch, start_ref)

        # Create flow state
        flow = self.create_flow(slug, branch)

        # Restore stash if we stashed
        if stash_ref:
            self.git_client.stash_apply(stash_ref)

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
        if not self.git_client.branch_exists(target_flow.branch):
            raise RuntimeError(f"Branch '{target_flow.branch}' does not exist")

        # Stash current changes
        stash_ref = None
        if self.git_client.has_uncommitted_changes():
            stash_ref = self.git_client.stash_push(message=f"vibe flow switch {target}")

        # Switch to target branch
        self.git_client.switch_branch(target_flow.branch)

        # Restore stash if we stashed
        if stash_ref:
            self.git_client.stash_apply(stash_ref)

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
            planner_session_id=flow_data.get("planner_session_id"),
            executor_actor=flow_data.get("executor_actor"),
            executor_session_id=flow_data.get("executor_session_id"),
            reviewer_actor=flow_data.get("reviewer_actor"),
            reviewer_session_id=flow_data.get("reviewer_session_id"),
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

    def get_flow_timeline(self, branch: str) -> dict:
        state_data = self.store.get_flow_state(branch)
        if not state_data:
            return {"state": None, "events": []}
        events_data = self.store.get_events(branch, limit=100)
        events = [FlowEvent(**e) for e in events_data]
        return {"state": FlowState(**state_data), "events": events}

    def bind_task(
        self,
        branch: str,
        task_ref: str,
        actor: str = "system",
    ) -> int:
        """Bind a task to a flow.

        Args:
            branch: Branch name
            task_ref: Task reference (e.g., "123" or "#123" or "gh-123")
            actor: Actor performing the bind

        Returns:
            Issue number

        Raises:
            ValueError: If task_ref is invalid
        """
        from vibe3.models.project_item import LinkError
        from vibe3.services.task_service import TaskService

        digits = "".join(filter(str.isdigit, task_ref))
        if not digits:
            raise ValueError(f"Invalid task ID format: {task_ref}")
        issue_number = int(digits)

        self.store.add_issue_link(branch, issue_number, "task")
        self.store.update_flow_state(branch, task_issue_number=issue_number)
        self.store.add_event(
            branch, "task_bound", actor, detail=f"Task bound: {task_ref}"
        )

        logger.bind(branch=branch, task=task_ref).info("Task bound to flow")

        link_result = TaskService().auto_link_issue_to_project(branch, issue_number)
        if isinstance(link_result, LinkError):
            logger.bind(task=task_ref).warning(
                f"Auto project link skipped: {link_result.message}"
            )

        return issue_number

    def bind_spec(
        self,
        branch: str,
        spec_ref: str,
        actor: str = "system",
    ) -> None:
        """Bind a spec to a flow.

        Args:
            branch: Branch name
            spec_ref: Spec file reference
            actor: Actor performing the bind
        """
        self.store.update_flow_state(branch, spec_ref=spec_ref, latest_actor=actor)
        self.store.add_event(
            branch, "spec_bound", actor, detail=f"Spec bound: {spec_ref}"
        )
        logger.bind(branch=branch, spec=spec_ref).info("Spec bound to flow")

    def get_handoff_events(
        self, branch: str, event_type_prefix: str = "handoff_", limit: int | None = None
    ) -> list[FlowEvent]:
        """Get handoff events for branch.

        Args:
            branch: Branch name
            event_type_prefix: Event type filter prefix
            limit: Maximum number of events

        Returns:
            List of FlowEvent objects
        """
        events_data = self.store.get_events(
            branch, event_type_prefix=event_type_prefix, limit=limit
        )
        return [FlowEvent(**e) for e in events_data]

    def get_flow_state(self, branch: str) -> FlowState | None:
        """Get flow state for branch.

        Args:
            branch: Branch name

        Returns:
            FlowState or None if not found
        """
        state_data = self.store.get_flow_state(branch)
        if not state_data:
            return None
        return FlowState(**state_data)

    def get_git_common_dir(self) -> str:
        """Get git common directory path.

        Returns:
            Path to git common directory
        """
        return self.git_client.get_git_common_dir()
